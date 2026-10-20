"""Explainable investigation rules. Scores are uncalibrated, never probabilities."""
from datetime import UTC, datetime, timedelta
from itertools import combinations
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError
from app.models import DiseaseRecognitionRecord, WarningEvent, SensorData, FarmTask
from app.models.agronomist import AgronomyRecord
from app.models.community import ContentAsset
from app.services import agronomist_service as research
from app.services.access import actor
from app.services.errors import ServiceError
from app.services.investigation_vision import VisualResult

VERSION = "investigation-rules-1.0"
ZONES = ["东侧", "中央", "西侧", "北侧", "南侧"]
SOURCES = [
    {"title": "UConn：番茄叶霉病鉴别", "url": "https://ipm.cahnr.uconn.edu/tomato-leaf-mold/"},
    {"title": "UC IPM：叶螨、叶面点状失绿与叶背蛛网", "url": "https://ipm.ucanr.edu/home-and-landscape/spider-mites/"},
    {"title": "UC IPM：番茄病虫害鉴别索引", "url": "https://ipm.ucanr.edu/agriculture/tomato/"},
]
# Feature effects are authored investigation heuristics, not trained likelihoods.
CAUSES = [
    ("microclimate", "局部潮湿或通风差异", {"local_humid": 4, "humidity_gap": 5, "poor_ventilation": 2, "localized": 1, "webbing": -2}, [0]),
    ("leaf_mold", "叶霉等叶部病害待鉴别", {"mold": 6, "local_humid": 2, "spreading": 2, "webbing": -3, "stippling": -1}, [0]),
    ("mites", "叶螨等刺吸危害待鉴别", {"webbing": 7, "stippling": 4, "mold": -3, "local_humid": -1}, [1]),
    ("water_stress", "灌溉或根区水分异常", {"irrigation_changed": 4, "wilting": 4, "mold": -2, "webbing": -3}, []),
    ("unknown", "其他原因 / 证据不足", {}, []),
]
FEATURE_LABELS = {"local_humid": "异常区湿度偏高（调查阈值85%）", "humidity_gap": "同时间不同区域湿度差≥10个百分点",
    "poor_ventilation": "近期通风不畅", "localized": "症状集中于局部", "mold": "叶背可见霉层",
    "spreading": "相邻植株也有症状", "webbing": "叶背可见细蛛网或活动小点", "stippling": "叶面密集点状失绿",
    "irrigation_changed": "近期灌溉发生异常变化", "wilting": "整株萎蔫"}
ACTIONS = [
    ("front", "拍摄异常叶片正面", ["stippling"], 2, "记录失绿、斑点及边缘，并选择实际可见特征"),
    ("back", "拍摄异常叶片背面", ["mold", "webbing"], 3, "同一叶片叶背近照，查找霉层、蛛网或活动小点"),
    ("plant", "拍摄完整植株", ["wilting"], 4, "包含顶部、基部和邻株，判断是否整株萎蔫"),
    ("neighbors", "检查同一区域其他植株", ["spreading", "localized"], 3, "记录是否相邻多株发生、是否局限一侧"),
    ("local", "测量异常区域温湿度", ["local_humid", "humidity_gap"], 4, "在异常叶片附近同高度补测并标记位置"),
    ("normal", "测量附近正常区域温湿度", ["humidity_gap"], 4, "在正常区域补测，尽量与异常区同时间、同高度"),
    ("irrigation", "查询近期灌溉记录", ["irrigation_changed"], 2, "核对最近灌溉时间、堵塞或异常变化"),
    ("ventilation", "查询近期通风记录", ["poor_ventilation"], 2, "核对开窗、风机及局部遮挡的实际记录"),
    ("symptom", "补充叶片症状描述", ["stippling", "mold", "webbing", "wilting"], 1, "只选择亲眼观察到的特征，不把未检查当作没有"),
    ("history", "查看历史环境异常记录", ["local_humid", "poor_ventilation"], 2, "结合下方带时间和来源的历史采样/预警核查，历史高湿不代表当前局部高湿"),
]
ACTION_MAP = {a[0]: a for a in ACTIONS}

class Start(BaseModel):
    greenhouse_id: int = Field(gt=0)
    question: str = Field(min_length=4, max_length=2000)
    zone: Literal["东侧", "中央", "西侧", "北侧", "南侧"] = "东侧"
    budget: int = Field(default=3, ge=0, le=10)
    unavailable_actions: list[str] = Field(default_factory=list, max_length=10)

class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    zone: Literal["东侧", "中央", "西侧", "北侧", "南侧"]
    note: str = Field(default="", max_length=2000)
    features: dict[str, bool] = Field(default_factory=dict, max_length=10)
    temperature: float | None = Field(default=None, ge=-20, le=60, allow_inf_nan=False)
    humidity: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    asset_id: int | None = Field(default=None, gt=0)
    sensor_id: int | None = Field(default=None, gt=0)
    visual: VisualResult | None = None
    visual_review: dict[str, bool | None] = Field(default_factory=dict, max_length=7)
    reject_classifier: bool = False
    height_cm: float | None = Field(default=None, ge=0, le=500, allow_inf_nan=False)
    duration_seconds: float | None = Field(default=None, ge=0, le=36000, allow_inf_nan=False)
    data_source: Literal["manual", "sensor", "import"] = "manual"

    @field_validator("observed_at")
    @classmethod
    def utc_time(cls, value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

class Update(BaseModel):
    version: int = Field(ge=1)
    evidence: Evidence

class Finish(BaseModel):
    version: int = Field(ge=1)
    note: str = Field(min_length=4, max_length=2000)

class Demo(BaseModel):
    question: str = Field(default="东侧番茄叶片异常，中央传感器湿度正常", min_length=4, max_length=2000)
    zone: Literal["东侧", "中央", "西侧", "北侧", "南侧"] = "东侧"
    budget: int = Field(default=3, ge=0, le=10)
    unavailable_actions: list[str] = Field(default_factory=list, max_length=10)
    evidence: list[Evidence] = Field(default_factory=list, max_length=10)

def evaluate_v1(evidence, question="", zone="东侧", budget=3, context=None):
    facts, evidence_meta = {}, {}
    for i, e in enumerate(evidence):
        for key, value in e.get("features", {}).items():
            facts[key] = value
            evidence_meta[key] = f"观察#{i+1} · {e['zone']} · {e['observed_at']}"
        if e["action"] == "local" and e.get("humidity") is not None:
            facts["local_humid"] = e["humidity"] >= 85
            evidence_meta["local_humid"] = f"观察#{i+1} · {e['zone']}湿度{e['humidity']}%"
    local = next((e for e in reversed(evidence) if e["action"] == "local" and e.get("humidity") is not None), None)
    normal = next((e for e in reversed(evidence) if e["action"] == "normal" and e.get("humidity") is not None), None)
    if local and normal and local["zone"] != normal["zone"]:
        t1, t2 = (datetime.fromisoformat(e["observed_at"]) for e in (local, normal))
        if abs((t1-t2).total_seconds()) <= 3600:
            facts["humidity_gap"] = local["humidity"]-normal["humidity"] >= 10
            evidence_meta["humidity_gap"] = "一小时内、不同标记区域的两次人工补测；未校准仪器误差"
    candidates = []
    for key, name, effects, sources in CAUSES:
        score = 1 if key == "microclimate" and any(w in question for w in ["局部", "东侧", "西侧", "一侧"]) else 0
        support, conflict = [], []
        if score:
            support.append("问题描述提示空间差异（弱线索，不是实测证据）")
        samples = (context or {}).get("history", [])
        humid_history = any((s.get("air_humidity") or 0) >= 85 for s in samples)
        if humid_history and key in ("microclimate", "leaf_mold"):
            score += 1
            support.append("现有历史采样有高湿线索（+1）；时间和位置可能不同，不能代替局部实测")
        for feature, weight in effects.items():
            if feature not in facts: continue
            delta = weight if facts[feature] else -weight
            reason = f"{FEATURE_LABELS[feature]}：{'有' if facts[feature] else '未见/否'}（{evidence_meta[feature]}；分值{delta:+}）"
            (support if delta > 0 else conflict).append(reason)
            score += delta
        candidates.append({"id": key, "name": name, "score": score, "support": support, "conflict": conflict,
            "missing": [FEATURE_LABELS[k] for k in effects if k not in facts], "key_features": [FEATURE_LABELS[k] for k in effects],
            "sources": [SOURCES[i] for i in sources], "state": "待核实"})
    candidates.sort(key=lambda c: (-c["score"], c["id"]))
    completed = {e["action"] for e in evidence}
    remaining = max(0, budget-len(evidence)) if budget else 10-len(evidence)
    rankings = []
    top = candidates[0]["score"]
    weights = {c["id"]: 1/(1+top-c["score"]) for c in candidates if c["id"] != "unknown"}
    cost_penalty = {1: .65, 2: .3, 3: .16, 0: .08}[budget]
    for key, name, features, cost, target in ACTIONS:
        if key in completed: continue
        missing = [f for f in features if f not in facts]
        discrimination = 0.0
        separated = set()
        for a, b in combinations(CAUSES[:-1], 2):
            difference = sum(abs(a[2].get(f, 0)-b[2].get(f, 0)) for f in missing)
            discrimination += difference*weights[a[0]]*weights[b[0]]
            if difference: separated.update([a[1], b[1]])
        missing_ratio = len(missing)/len(features)
        value = round(discrimination*missing_ratio-cost_penalty*cost, 4)
        rankings.append({"id": key, "name": name, "target": target, "features": features, "cost_minutes": cost,
            "discrimination": round(discrimination, 4), "missing_ratio": missing_ratio, "cost_penalty": cost_penalty,
            "score": value, "distinguishes": sorted(separated),
            "reason": f"尚缺{len(missing)}项特征，可区分{len(separated)}类解释；预计{cost}分钟，预算成本系数{cost_penalty}。未检查不视为阴性。"})
    rankings.sort(key=lambda a: (-a["score"], a["cost_minutes"], a["id"]))
    recommendations = [a for a in rankings if a["missing_ratio"] > 0]
    lead = candidates[0]
    status = "budget_exhausted" if remaining <= 0 else "investigating" if recommendations else "review_required"
    summary = ("检查预算已用完，请人工复核或新建后续调查。" if remaining <= 0 else "证据仍不足，优先获取可区分原因的新观察。")
    if len(lead["support"]) >= 2 and lead["score"] >= 6:
        summary = f"当前优先调查：{lead['name']}；属于排查线索，尚未确诊，需人工复核。"
    return {"rule_version": VERSION, "candidates": candidates, "rankings": rankings, "plan": recommendations[:remaining],
        "next": recommendations[0] if recommendations and remaining > 0 else None,
        "remaining": remaining, "status": status, "summary": summary, "facts": facts,
        "score_note": "规则支持分和观察价值均为启发式评分，不是病害概率或严格信息增益；人工复核后才能形成农艺处置。"}

def evaluate(evidence, question="", zone="东侧", budget=3, context=None):
    from app.services.investigation_policy import infer
    return infer(evidence, question, zone, budget, context)


def validate_evidence(e, previous, zone):
    if e.action not in ACTION_MAP: raise ServiceError(422, "未知观察动作")
    duplicates = [p for p in previous if p["action"] == e.action]
    if duplicates:
        old = duplicates[-1].get("visual")
        if not (e.visual and old and old["quality"].get("retake") and e.visual.image_hash != old["image_hash"]):
            raise ServiceError(409, "该观察已完成；仅允许质量不足时换照片重拍")
    from app.services.investigation_policy import actions
    allowed = set(next(a[2] for a in actions() if a[0] == e.action)) | set(ACTION_MAP[e.action][2])
    if set(e.features)-set(allowed): raise ServiceError(422, "特征不属于该观察动作")
    if set(e.features) & {"local_humid", "humidity_gap"}: raise ServiceError(422, "湿度特征须由实际测量计算")
    if e.action == "local" and e.zone != zone: raise ServiceError(422, "异常区补测位置应与调查位置一致")
    if e.action == "normal" and e.zone == zone: raise ServiceError(422, "正常区补测需选择另一位置")
    if e.action in ("local", "normal") and e.humidity is None and e.sensor_id is None: raise ServiceError(422, "请填写湿度或关联有效采样")
    if e.action not in ("local", "normal") and (e.humidity is not None or e.temperature is not None or e.sensor_id):
        raise ServiceError(422, "数值补测应使用温湿度测量动作")
    if not (e.features or e.note.strip() or e.asset_id or e.visual or e.humidity is not None or e.sensor_id): raise ServiceError(422, "请提交实际证据")
    if e.observed_at.astimezone(UTC).replace(tzinfo=None) > datetime.now(UTC).replace(tzinfo=None)+timedelta(minutes=5):
        raise ServiceError(422, "观察时间不能在未来")

def append(payload, e):
    previous = payload["evidence"]
    if payload["budget"] and len(previous) >= payload["budget"]: raise ServiceError(409, "检查预算已用完")
    if len(previous) >= 10: raise ServiceError(409, "V1每次调查最多10项不同检查")
    validate_evidence(e, previous, payload["zone"])
    old = payload["analysis"]
    payload["evidence"] = [*previous, jsonable_encoder(e)]
    current = evaluate(payload["evidence"], payload["question"], payload["zone"], payload["budget"], payload["context"])
    changes = [{"name": c["name"], "before": next((p["score"] for p in old["candidates"] if p["id"] == c["id"]), 0),
        "after": c["score"]} for c in current["candidates"]]
    payload["analysis"] = current
    payload["history"] = [*payload["history"], {"round": len(payload["history"]), "at": datetime.now(UTC).isoformat(),
        "added": jsonable_encoder(e), "previous_leader": old["candidates"][0]["name"], "leader": current["candidates"][0]["name"],
        "changes": changes, "analysis": current}]
    return payload

def initial(question, zone, budget, context):
    analysis = evaluate([], question, zone, budget, context)
    return {"question": question, "zone": zone, "budget": budget, "context": context, "evidence": [], "analysis": analysis,
        "history": [{"round": 0, "at": datetime.now(UTC).isoformat(), "leader": analysis["candidates"][0]["name"],
                     "changes": [], "analysis": analysis}], "final_note": None}

def snapshot(db, gid):
    from app.services.knowledge_service import search_knowledge
    from app.services.investigation_experience import active_policy
    gh, batch = research.context(db, gid)
    archive = research.archive(db, gid)
    diseases = db.scalars(select(DiseaseRecognitionRecord).where(DiseaseRecognitionRecord.greenhouse_id == gid,
        DiseaseRecognitionRecord.crop_type == "tomato").order_by(DiseaseRecognitionRecord.created_at.desc()).limit(10))
    warnings = db.scalars(select(WarningEvent).where(WarningEvent.greenhouse_id == gid, WarningEvent.status.in_(["open", "acknowledged"])).limit(10))
    return jsonable_encoder({"source": "正式账号现有记录快照（非全棚空间实测）", "greenhouse": archive["greenhouse"],
        "crop": batch.crop_type if batch else None, "batch": archive["batch"], "latest": archive["latest"], "fresh": archive["fresh"],
        "history": archive["history"], "gaps": archive["gaps"],
        "warnings": [{"id": w.id, "title": w.title, "severity": w.severity, "status": w.status} for w in warnings],
        "operations": [{"id": t.id, "title": t.title, "type": t.action_type, "status": t.status, "updated_at": t.updated_at}
            for t in db.scalars(select(FarmTask).where(FarmTask.greenhouse_id == gid, FarmTask.action_type.in_(["irrigation", "ventilation"])).order_by(FarmTask.updated_at.desc()).limit(20))],
        "diseases": [{"id": d.id, "label": d.predicted_class_name, "class_key":d.predicted_class,"reviewed_class":d.reviewed_class, "status": d.recognition_status, "review": d.review_status,
                      "created_at": d.created_at} for d in diseases],
        "knowledge": search_knowledge("番茄叶片湿度叶霉病", db=db, crop="tomato", limit=4),
        "learned_policy":active_policy(db),
        "sensor_position": None, "position_note": "当前传感器表无坐标，不能默认位于中央；需人工标记补测位置。"})

def get(db, record_id):
    row = research.record(db, record_id, "investigation")
    return row

def create(db, request):
    gh, batch = research.context(db, request.greenhouse_id)
    if batch and batch.crop_type != "tomato": raise ServiceError(422, "V1只支持番茄叶片和局部环境排查")
    row = research.save(db, gh.id, batch.id if batch else None, "investigation", request.question,
        initial(request.question, request.zone, request.budget, {**snapshot(db, gh.id), "unavailable_actions":request.unavailable_actions}), "investigating")
    return research.serialize(row)

def update(db, record_id, request):
    import copy
    row = get(db, record_id)
    if row.version != request.version: raise ServiceError(409, "调查已更新，请刷新")
    if row.status in ("completed", "archived"): raise ServiceError(409, "调查已归档")
    e = request.evidence.model_copy(update={"data_source":"manual"})
    if e.visual or e.visual_review or e.reject_classifier: raise ServiceError(422, "正式图片分析与修正请使用专用接口，不能提交自造视觉结果")
    if e.sensor_id:
        sample = db.scalar(select(SensorData).where(SensorData.id == e.sensor_id, SensorData.greenhouse_id == row.greenhouse_id, SensorData.quality_flag == "valid"))
        if sample is None: raise ServiceError(404, "采样不存在或不属于本棚")
        e = e.model_copy(update={"humidity": sample.air_humidity, "temperature": sample.temperature, "observed_at": sample.recorded_at.replace(tzinfo=UTC),
            "data_source":sample.source, "note": e.note+"；关联采样仅记录人工标记位置，传感器原始记录无坐标"})
    if e.asset_id:
        asset = db.get(ContentAsset, e.asset_id)
        if not asset or asset.owner_id != actor().id or asset.post_id is not None or not asset.media_type.startswith("image/"):
            raise ServiceError(422, "只能关联本人尚未公开的图片附件")
    row.payload = append(copy.deepcopy(row.payload), e)
    row.status = row.payload["analysis"]["status"]
    commit(db)
    return research.serialize(row)

def commit(db):
    try: db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise ServiceError(409, "调查已被更新，请刷新") from exc

def demo(request):
    payload = initial(request.question, request.zone, request.budget, {"source": "游客示例，非真实监测", "crop": "tomato",
        "latest": None, "history": [], "warnings": [], "diseases": [], "knowledge": [], "sensor_position": None,
        "unavailable_actions":request.unavailable_actions})
    for e in request.evidence:
        if e.sensor_id or e.asset_id: raise ServiceError(422, "游客不能关联正式记录")
        payload = append(payload, e)
    return {"id": 0, "version": len(request.evidence)+1, "status": payload["analysis"]["status"], "payload": payload}


class Refresh(BaseModel):
    version: int = Field(ge=1)


def refresh_context(db, record_id, request):
    """Read existing scoped sources and rerank; never fabricate field observations."""
    import copy
    row = get(db, record_id)
    if row.version != request.version:
        raise ServiceError(409, "调查已更新，请刷新")
    if row.status in ("completed", "archived"):
        raise ServiceError(409, "调查已归档")
    payload = copy.deepcopy(row.payload)
    old = payload["analysis"]
    context = snapshot(db, row.greenhouse_id)
    context["unavailable_actions"] = payload["context"].get("unavailable_actions", [])
    analysis = evaluate(payload["evidence"], payload["question"], payload["zone"], payload["budget"], context)
    at = datetime.now(UTC).isoformat()
    steps = [
        {"name": "环境与历史", "count": len(context.get("history", [])), "detail": "已读取现有采样" if context.get("latest") else "尚无可用采样"},
        {"name": "预警与农事记录", "count": len(context.get("warnings", [])) + len(context.get("operations", [])), "detail": "已查询本棚记录"},
        {"name": "病害识别记录", "count": len(context.get("diseases", [])), "detail": "已读取历史识别，保留人工复核状态"},
        {"name": "相关知识", "count": len(context.get("knowledge", [])), "detail": "已执行番茄知识检索"},
        {"name": "候选解释与观察排序", "count": len(analysis["candidates"]), "detail": "已重新计算规则支持分与观察价值"},
    ]
    # Context-only runs are separate from actual field observation rounds.
    changes = [{"name": c["name"], "before": next((p["score"] for p in old["candidates"] if p["id"] == c["id"]), 0), "after": c["score"]} for c in analysis["candidates"]]
    if any(c["before"] != c["after"] for c in changes):
        payload["history"].append({"round": len(payload["history"]), "at": at, "trigger": "context_refresh",
            "leader": analysis["candidates"][0]["name"], "previous_leader": old["candidates"][0]["name"], "changes": changes, "analysis": analysis})
    payload.update(context=context, analysis=analysis)
    runs = payload.get("autonomy_runs", [])
    payload["autonomy_runs"] = [*runs[-19:], {"at": at, "steps": steps,
        "state": "waiting_for_evidence" if analysis.get("next") else "review_required"}]
    row.payload = payload
    row.status = analysis["status"]
    commit(db)
    return research.serialize(row)
