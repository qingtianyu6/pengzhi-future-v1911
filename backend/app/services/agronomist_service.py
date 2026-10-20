"""Evidence-backed archives, comparisons, studies, reusable workflows and goal plans."""
from datetime import UTC, datetime, timedelta
import math

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CropBatch, FarmTask, Greenhouse, SensorData, WarningEvent
from app.models.agronomist import AgronomyRecord, CropObservation
from app.schemas.agronomist import Context, GoalCreate, ObservationCreate, ScenarioCreate, StudyCreate
from app.schemas.v2_decision import SimulationRequest
from app.services import task_service, v2_decision_service
from app.services.access import actor
from app.services.errors import ServiceError


def context(db: Session, greenhouse_id: int, crop_batch_id: int | None = None):
    greenhouse = db.scalar(select(Greenhouse).where(Greenhouse.id == greenhouse_id))
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    query = select(CropBatch).where(CropBatch.greenhouse_id == greenhouse_id)
    query = query.where(CropBatch.id == crop_batch_id) if crop_batch_id else query.order_by(
        (CropBatch.status == "growing").desc(), CropBatch.planted_at.desc())
    batch = db.scalar(query.limit(1))
    if crop_batch_id and batch is None:
        raise ServiceError(404, "种植批次不存在或不属于当前大棚")
    return greenhouse, batch


def record(db: Session, record_id: int, kind: str | None = None):
    item = db.scalar(select(AgronomyRecord).where(AgronomyRecord.id == record_id))
    if item is None or (kind and item.kind != kind):
        raise ServiceError(404, "研究记录不存在")
    context(db, item.greenhouse_id, item.crop_batch_id)
    return item


def linked(db, record_id, kind, greenhouse_id, batch_id):
    if record_id is None:
        return None
    item = record(db, record_id, kind)
    if item.greenhouse_id != greenhouse_id or item.crop_batch_id != batch_id:
        raise ServiceError(422, "关联记录必须来自同一大棚和种植批次")
    return item


def serialize(item):
    return jsonable_encoder({key: getattr(item, key) for key in (
        "id", "greenhouse_id", "crop_batch_id", "kind", "title", "status", "payload", "version", "created_at", "updated_at")})


def save(db, greenhouse_id, batch_id, kind, title, payload, status="draft"):
    item = AgronomyRecord(greenhouse_id=greenhouse_id, crop_batch_id=batch_id,
                          kind=kind, title=title[:200], payload=jsonable_encoder(payload), status=status)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_records(db, greenhouse_id, crop_batch_id=None):
    _, batch = context(db, greenhouse_id, crop_batch_id)
    query = select(AgronomyRecord).where(AgronomyRecord.greenhouse_id == greenhouse_id)
    if batch:
        query = query.where(AgronomyRecord.crop_batch_id == batch.id)
    return [serialize(item) for item in db.scalars(query.order_by(AgronomyRecord.updated_at.desc(), AgronomyRecord.id.desc()).limit(200))]


def _sensors(db, greenhouse_id, batch):
    query = select(SensorData).where(SensorData.greenhouse_id == greenhouse_id,
        SensorData.source.in_(["sensor", "import"]), SensorData.quality_flag == "valid")
    if batch:
        query = query.where(SensorData.recorded_at >= datetime.combine(batch.planted_at, datetime.min.time()))
        if batch.status != "growing":
            query = query.where(SensorData.recorded_at <= batch.updated_at)
    latest = db.scalar(query.order_by(SensorData.recorded_at.desc()).limit(1))
    if latest is None:
        return []
    return list(reversed(list(db.scalars(query.where(
        SensorData.recorded_at >= latest.recorded_at - timedelta(days=7))
        .order_by(SensorData.recorded_at.desc()).limit(4000)))))


def archive(db, greenhouse_id, crop_batch_id=None):
    greenhouse, batch = context(db, greenhouse_id, crop_batch_id)
    readings = _sensors(db, greenhouse_id, batch)
    obs_query = select(CropObservation).where(CropObservation.greenhouse_id == greenhouse_id)
    if batch:
        obs_query = obs_query.where(CropObservation.crop_batch_id == batch.id)
    observations = list(db.scalars(obs_query.order_by(CropObservation.observed_at.desc()).limit(200)))
    task_query = select(FarmTask).where(FarmTask.greenhouse_id == greenhouse_id)
    warning_query = select(WarningEvent).where(WarningEvent.greenhouse_id == greenhouse_id)
    if batch:
        task_query = task_query.where(FarmTask.crop_batch_id == batch.id)
        warning_query = warning_query.where(WarningEvent.crop_batch_id == batch.id)
    tasks = list(db.scalars(task_query.order_by(FarmTask.updated_at.desc()).limit(100)))
    warnings = list(db.scalars(warning_query.order_by(WarningEvent.last_triggered_at.desc()).limit(100)))
    def snapshot(r):
        return {"id": r.id, "recorded_at": r.recorded_at, "temperature": r.temperature,
                "air_humidity": r.air_humidity, "soil_moisture": r.soil_moisture}
    timeline = [{"id": f"observation-{o.id}", "at": o.observed_at, "type": "observation", "title": o.note,
                 "detail": o.zone, "source_id": o.id} for o in observations]
    timeline += [{"id": f"task-{t.id}", "at": t.updated_at, "type": "task", "title": t.title,
                  "detail": t.status, "source_id": t.id} for t in tasks]
    timeline += [{"id": f"warning-{w.id}", "at": w.last_triggered_at, "type": "warning", "title": w.title,
                  "detail": w.status, "source_id": w.id} for w in warnings]
    timeline.sort(key=lambda e: e["at"].replace(tzinfo=None), reverse=True)
    latest = readings[-1] if readings else None
    fresh = bool(latest and (datetime.now(UTC).replace(tzinfo=None) - latest.recorded_at.replace(tzinfo=None)).total_seconds() < 7200)
    metrics = {}
    for key in ("temperature", "air_humidity", "soil_moisture"):
        values = [getattr(r, key) for r in readings if getattr(r, key) is not None]
        metrics[key] = {"mean": round(sum(values)/len(values), 2), "min": min(values), "max": max(values)} if values else None
    gaps = []
    if not readings: gaps.append("缺少有效环境采样，请接入设备或导入数据")
    elif not fresh: gaps.append("最近采样超过两小时，当前展示历史记录")
    if not observations: gaps.append("尚未记录株高、开花、坐果或采收观察")
    if not batch: gaps.append("请先建立种植批次以积累生长档案")
    return jsonable_encoder({
        "greenhouse": {"id": greenhouse.id, "name": greenhouse.name, "code": greenhouse.code},
        "batch": {"id": batch.id, "batch_code": batch.batch_code, "variety": batch.variety,
                  "growth_stage": batch.growth_stage, "planted_at": batch.planted_at, "status": batch.status,
                  "growth_day": max(0, (datetime.now(UTC).date()-batch.planted_at).days)} if batch else None,
        "batches": [{"id": b.id, "batch_code": b.batch_code, "status": b.status} for b in db.scalars(
            select(CropBatch).where(CropBatch.greenhouse_id == greenhouse_id).order_by(CropBatch.planted_at.desc()))],
        "latest": snapshot(latest) if latest else None, "fresh": fresh,
        "history": [snapshot(r) for r in readings[::max(1, math.ceil(len(readings)/72))]],
        "metrics": metrics, "sample_count": len(readings), "gaps": gaps,
        "observations": [{"id": o.id, "study_id": o.study_id, "observed_at": o.observed_at, "phase": o.phase,
                          "zone": o.zone, "note": o.note, "metrics": o.metrics} for o in observations],
        "timeline": timeline[:60], "task_counts": {s: sum(t.status == s for t in tasks)
            for s in ("draft", "pending", "in_progress", "completed")},
        "open_warnings": sum(w.status in ("open", "acknowledged") for w in warnings),
        "window_note": "最近采样前7天内最多4000条有效采样；任务与预警各展示最近100条，观察最近200条。",
    })


def add_observation(db, payload: ObservationCreate):
    _, batch = context(db, payload.greenhouse_id, payload.crop_batch_id)
    if batch is None:
        raise ServiceError(422, "请先建立种植批次")
    study = linked(db, payload.study_id, "study", payload.greenhouse_id, batch.id)
    if study and study.status != "running":
        raise ServiceError(422, "请先启动研究，再记录关联观察")
    if not payload.note.strip() or any(not math.isfinite(v) or v < 0 for v in payload.metrics.values()):
        raise ServiceError(422, "观察内容不能为空，指标必须是非负有限数值")
    if payload.metrics.get("leaf_wetness_pct", 0) > 100:
        raise ServiceError(422, "叶面湿润比例应在0–100之间")
    item = CropObservation(greenhouse_id=payload.greenhouse_id, crop_batch_id=batch.id,
        study_id=payload.study_id, observed_at=payload.observed_at or datetime.now(UTC),
        phase=payload.phase, zone=payload.zone, note=payload.note.strip(), metrics=payload.metrics)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id}


def compare(db, payload: ScenarioCreate):
    _, batch = context(db, payload.greenhouse_id, payload.crop_batch_id)
    readings = _sensors(db, payload.greenhouse_id, batch)
    if not readings:
        raise ServiceError(422, "缺少有效环境采样，请先导入数据")
    baseline = readings[-1]
    candidates = []
    for action, name, intensity in (("ventilation", "维持当前条件（静态参照）", 0),
                                     ("ventilation", "通风方案", payload.intensity),
                                     ("dehumidify", "除湿方案", payload.intensity)):
        result = v2_decision_service.run_simulation(db, SimulationRequest(
            greenhouse_id=payload.greenhouse_id, action_type=action, intensity=intensity,
            duration_minutes=payload.duration_minutes), persist=False, baseline_record=baseline)
        if intensity == 0:
            for point in result.timeline:
                point["temperature"] = baseline.temperature
                point["humidity"] = baseline.air_humidity
        candidates.append({"name": name, "action": action, "intensity": intensity,
                           "timeline": result.timeline, "end": result.timeline[-1]})
    return save(db, payload.greenhouse_id, batch.id if batch else None, "scenario",
        f"{payload.duration_minutes}分钟环境方案比较", {
            "baseline": {"sensor_record_id": baseline.id, "recorded_at": baseline.recorded_at,
                         "temperature": baseline.temperature, "humidity": baseline.air_humidity},
            "duration_minutes": payload.duration_minutes, "candidates": candidates,
            "method": "现有短时环境响应模型 · 规则系数推演",
            "note": "同一采样起点的探索性比较；静态参照不包含天气变化，不代表真实设备响应或产量预测。",
        }, "completed")


def create_study(db, payload: StudyCreate):
    _, batch = context(db, payload.greenhouse_id, payload.crop_batch_id)
    if batch is None: raise ServiceError(422, "请先建立种植批次")
    scenario = linked(db, payload.scenario_id, "scenario", payload.greenhouse_id, batch.id)
    question = payload.question.strip()
    if not question: raise ServiceError(422, "请输入研究问题")
    return save(db, payload.greenhouse_id, batch.id, "study", question, {
        "question": question, "hypothesis": payload.hypothesis.strip() or "检查环境变化与农事时间、区域差异之间的关系",
        "alternatives": ["外部天气与棚内温湿度变化", "灌溉时间和新增湿源", "通风时机与区域差异"],
        "protocol": ["在相同区域记录处理前观察和环境采样时间", "记录操作内容、天气和灌溉等伴随变化", "同一区域记录处理后观察，并尽可能增加可比对照区", "比较同名指标，保留反例和缺失数据"],
        "scenario_snapshot": serialize(scenario) if scenario else None,
        "method": "结构化观察研究草案", "conclusion": None,
    })


def create_goal(db, payload: GoalCreate):
    _, batch = context(db, payload.greenhouse_id, payload.crop_batch_id)
    if batch is None: raise ServiceError(422, "请先建立种植批次")
    snapshots = {}
    for key, kind in (("scenario_id", "scenario"), ("skill_id", "skill"), ("study_id", "study")):
        item = linked(db, getattr(payload, key), kind, payload.greenhouse_id, batch.id)
        if item:
            if kind == "skill" and item.status != "active":
                raise ServiceError(422, "请选择已启用的农事技能")
            snapshots[kind] = serialize(item)
    goal = payload.goal.strip()
    if not goal: raise ServiceError(422, "请输入目标")
    humidity = any(word in goal for word in ("湿", "结露", "通风"))
    heat = any(word in goal for word in ("温", "热", "降温"))
    water = any(word in goal for word in ("水", "灌溉", "土壤"))
    action = "humidity_control" if humidity else "shading_check" if heat else "irrigation_check" if water else "manual_observation"
    operation = "检查通风与湿源，记录调整前后情况" if humidity else "检查遮阳与通风，记录温度变化" if heat else "检查土壤与灌溉，记录用水情况" if water else "按目标检查现场并记录实际操作"
    steps = [{"title": "采集目标基线", "action_type": "sensor_inspection", "description": f"目标：{goal}。核对设备、采样时间，并记录当前环境与作物状态。", "depends_on": []},
             {"title": operation, "action_type": action, "description": f"围绕目标「{goal}」开展现场检查和操作记录。", "depends_on": [0]},
             {"title": "复查环境与作物", "action_type": "manual_observation", "description": "记录处理后同区域、同口径指标，补充天气和其他伴随操作。", "depends_on": [1]},
             {"title": "整理结果与经验", "action_type": "manual_observation", "description": "比较观察记录，说明变化、未解决问题及下一步；将结果补充到关联研究。", "depends_on": [2]}]
    if snapshots.get("skill"):
        steps[1]["description"] += " 参考技能步骤：" + "；".join(snapshots["skill"]["payload"].get("steps", []))
    if payload.plan_steps:
        steps = [step.model_dump() for step in payload.plan_steps]
    return save(db, payload.greenhouse_id, batch.id, "goal", goal, {
        "goal": goal, "steps": steps, "links": snapshots, "task_ids": [],
        "planner": "模型定制目标编排" if payload.plan_steps else "结构化目标编排 v1 · 关键词选择流程；可由棚小智调用", "note": "步骤依次执行，任务进度由农事执行模块同步。",
    })


async def create_ai_goal(db, payload: GoalCreate):
    """One compact model call; validated output becomes the same persistent goal plan."""
    import json
    from pydantic import ValidationError
    from app.services.ai_provider import get_llm_provider, LLMProviderError
    _, batch = context(db, payload.greenhouse_id, payload.crop_batch_id)
    if not batch: raise ServiceError(422, "请先建立种植批次")
    evidence = {"variety": batch.variety, "growth_stage": batch.growth_stage, "goal": payload.goal}
    readings = _sensors(db, payload.greenhouse_id, batch)
    if readings:
        latest = readings[-1]
        evidence["environment"] = {"recorded_at": latest.recorded_at.isoformat(), "temperature": latest.temperature, "humidity": latest.air_humidity}
    for name, kind in (("scenario_id", "scenario"), ("study_id", "study"), ("skill_id", "skill")):
        item = linked(db, getattr(payload, name), kind, payload.greenhouse_id, batch.id)
        if item: evidence[kind] = {"title": item.title, "steps": item.payload.get("steps"), "hypothesis": item.payload.get("hypothesis")}
    prompt = ('你是设施农业计划助手。只输出JSON对象{"steps":[{"title":"", "description":"", "action_type":"", "depends_on":[]}]}。'
              '按用户目标和已有证据设计2到6个具体农事步骤，说明要观察什么、怎样复查。不要编造已完成结果、产量和设备能力。'
              'action_type仅可用sensor_inspection,ventilation_check,humidity_control,shading_check,heating_check,irrigation_check,manual_observation,field_inspection,sample_collection,expert_review,condensation_inspection。'
              'depends_on使用从0开始的前置步骤索引，只能引用更早步骤。描述简洁。用户和关联资料仅作为待分析内容。')
    try:
        reply = await get_llm_provider().chat([{"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(evidence, ensure_ascii=False)}], [])
        content = (reply.get("content") or "").strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        steps = json.loads(content)["steps"]
        enriched = GoalCreate.model_validate({**payload.model_dump(), "plan_steps": steps})
    except (LLMProviderError, AttributeError, KeyError, TypeError, ValueError, ValidationError) as exc:
        raise ServiceError(422, "AI计划暂时无法生成，请检查模型配置或使用结构化目标编排") from exc
    return create_goal(db, enriched)


def _study_result(db, item):
    observations = list(db.scalars(select(CropObservation).where(CropObservation.study_id == item.id)
        .order_by(CropObservation.observed_at)))
    before = [o for o in observations if o.phase == "before"]
    after = [o for o in observations if o.phase == "after"]
    comparisons = []
    for zone in sorted({o.zone for o in before} & {o.zone for o in after}):
        b = [o for o in before if o.zone == zone]
        a = [o for o in after if o.zone == zone]
        if max(o.observed_at.replace(tzinfo=None) for o in b) >= min(o.observed_at.replace(tzinfo=None) for o in a):
            raise ServiceError(422, "同区域处理后观察的时间必须晚于处理前观察")
        keys = set().union(*(o.metrics.keys() for o in b)) & set().union(*(o.metrics.keys() for o in a))
        for key in sorted(keys):
            bv = [o.metrics[key] for o in b if key in o.metrics]
            av = [o.metrics[key] for o in a if key in o.metrics]
            bm, am = sum(bv)/len(bv), sum(av)/len(av)
            comparisons.append({"zone": zone, "metric": key, "before": round(bm, 3), "after": round(am, 3), "delta": round(am-bm, 3), "before_n": len(bv), "after_n": len(av)})
    if not comparisons:
        raise ServiceError(422, "请至少录入同一区域、同一数值指标的处理前与处理后观察")
    return {"comparisons": comparisons, "observation_ids": [o.id for o in observations],
            "control_count": sum(o.phase == "control" for o in observations),
            "interpretation": "以上是观察均值变化，不是处理的因果效果；观察条数不代表独立试验重复数。"}


def apply_action(db, record_id, payload):
    item = record(db, record_id)
    if item.version != payload.version:
        raise ServiceError(409, "记录已更新，请刷新后操作")
    data = dict(item.payload)
    action = payload.action
    if action == "derive_skill" and item.kind == "study":
        existing = list(db.scalars(select(AgronomyRecord).where(AgronomyRecord.greenhouse_id == item.greenhouse_id, AgronomyRecord.kind == "skill")))
        prior = next((s for s in existing if s.payload.get("source_study_id") == item.id), None)
        if prior: return prior
        return save(db, item.greenhouse_id, item.crop_batch_id, "skill", f"{item.title[:170]} · 农事技能", {
            "source_study_id": item.id, "source_snapshot": serialize(item),
            "applicability": "限本批次研究条件；跨棚使用需重新核对", "steps": data["protocol"],
            "evidence": data.get("conclusion"), "validation": "待验证流程，不代表已证实增产或降病",
        })
    if action == "start" and item.kind == "study" and item.status == "draft":
        item.status = "running"
    elif action == "complete" and item.kind == "study" and item.status == "running":
        data["conclusion"] = {**_study_result(db, item), "note": payload.note}
        item.status = "completed"
    elif action in ("activate", "disable") and item.kind == "skill" and item.status != "archived":
        item.status = "active" if action == "activate" else "disabled"
    elif action == "execute" and item.kind == "goal" and item.status == "draft":
        greenhouse, batch = context(db, item.greenhouse_id, item.crop_batch_id)
        if batch is None or batch.status != "growing":
            raise ServiceError(422, "只能为生长中的批次下发农事任务")
        task_ids = []
        for index, step in enumerate(data["steps"]):
            task = task_service._create(db, greenhouse=greenhouse, batch=batch,
                source_type="manual", source_id=None, source_warning_id=None, source_disease_record_id=None,
                source_recommendation_id=None, title=step["title"][:160], description=step["description"][:3000],
                action_type=step["action_type"], priority="medium", planned_start_at=None, due_at=None,
                created_by=actor().display_name[:60], safety_note="按目标步骤依次执行并记录现场情况。", commit=False)
            stored = db.get(FarmTask, task.id)
            stored.evidence_snapshot_json = {**stored.evidence_snapshot_json,
                "agronomist_goal": {"id": item.id, "version": item.version, "step": index,
                                    "depends_on_task_ids": [task_ids[i] for i in step["depends_on"]]},
                "research_links": data.get("links", {})}
            task_ids.append(task.id)
        data["task_ids"] = task_ids
        item.status = "running"
    elif action == "complete" and item.kind == "goal" and item.status == "running":
        tasks = list(db.scalars(select(FarmTask).where(FarmTask.id.in_(data["task_ids"]))))
        if len(tasks) != len(data["task_ids"]) or not tasks or any(t.status != "completed" for t in tasks):
            raise ServiceError(422, "请先在农事执行中完成全部关联任务")
        item.status = "completed"
        data["completion_note"] = payload.note
    elif action == "archive":
        item.status = "archived"
    else:
        raise ServiceError(422, "当前记录状态不支持该操作")
    item.payload = data
    # Always write a revision, including repeated enable/disable requests.
    item.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    return item


def goal_progress(db, greenhouse_id, crop_batch_id=None):
    records = list_records(db, greenhouse_id, crop_batch_id)
    ids = {i for r in records if r["kind"] == "goal" for i in r["payload"].get("task_ids", [])}
    tasks = list(db.scalars(select(FarmTask).where(FarmTask.id.in_(ids)))) if ids else []
    return {"records": records, "tasks": [{"id": t.id, "title": t.title, "status": t.status} for t in tasks]}
