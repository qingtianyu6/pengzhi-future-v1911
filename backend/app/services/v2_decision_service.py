from __future__ import annotations

from datetime import UTC, datetime, timedelta
import math
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (CropBatch, DecisionPlan, FarmTask, Greenhouse, GreenhouseProfile, RiskEvent,
                        SensorData, SimulationRecord, TreatmentEvaluation)
from app.schemas.task import SourceTaskCreate
from app.schemas.v2_decision import SimulationData, SimulationRequest
from app.services import task_service
from app.services.errors import ServiceError
from app.services.risk_engine import DiseaseRiskEngine
from app.services.sensor_service import VALID_BUSINESS_SOURCES


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _latest_records(db: Session, greenhouse_id: int, hours: int = 24) -> list[SensorData]:
    latest = db.scalar(select(SensorData.recorded_at).where(
        SensorData.greenhouse_id == greenhouse_id,
        SensorData.source.in_(VALID_BUSINESS_SOURCES),
    ).order_by(SensorData.recorded_at.desc()).limit(1))
    if latest is None:
        return []
    return list(db.scalars(select(SensorData).where(
        SensorData.greenhouse_id == greenhouse_id,
        SensorData.source.in_(VALID_BUSINESS_SOURCES),
        SensorData.recorded_at >= latest - timedelta(hours=hours),
        SensorData.recorded_at <= latest,
    ).order_by(SensorData.recorded_at.asc())))


def _active_batch(db: Session, greenhouse_id: int) -> CropBatch | None:
    return db.scalar(select(CropBatch).where(CropBatch.greenhouse_id == greenhouse_id, CropBatch.status == "growing").limit(1))


def _snapshot_from_sensor(sensor: SensorData | None, risk_score: float | None = None) -> dict[str, Any]:
    if sensor is None:
        return {"status": "insufficient_data", "risk_score": risk_score}
    return {
        "sensor_record_id": sensor.id,
        "recorded_at": sensor.recorded_at.isoformat(),
        "temperature": sensor.temperature,
        "humidity": sensor.air_humidity,
        "soil_moisture": sensor.soil_moisture,
        "co2": sensor.co2_concentration,
        "light": sensor.light_intensity,
        "risk_score": risk_score,
    }


def greenhouse_risk(db: Session, greenhouse_id: int, *, persist: bool = False,
                    crop_type: str | None = None, growth_stage: str | None = None) -> dict[str, Any]:
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    batch = _active_batch(db, greenhouse_id)
    records = _latest_records(db, greenhouse_id, 24)
    resolved_crop = batch.crop_type if batch else "unknown"
    if crop_type and crop_type != resolved_crop:
        raise ServiceError(422, "作物类型必须与当前种植批次一致")
    resolved_stage = growth_stage or (batch.growth_stage if batch else None)
    current = _snapshot_from_sensor(records[-1] if records else None)
    records = [r for r in records if r.temperature is not None and r.air_humidity is not None and r.quality_flag != "suspect"]
    supported = resolved_crop in {"tomato", "melon", "muskmelon"}
    covered_hours = (records[-1].recorded_at - records[0].recorded_at).total_seconds()/3600 if len(records)>1 else 0
    if not supported or not resolved_stage or len(records) < 6 or covered_hours < 5:
        return {
            "greenhouse_id": greenhouse_id,
            "crop_type": resolved_crop,
            "growth_stage": resolved_stage,
            "data_status": "insufficient_data",
            "current_environment": current,
            "risks": [],
            "top_event": None,
        }
    risks = DiseaseRiskEngine().evaluate_all(records, resolved_stage, crop_type=resolved_crop)
    top = max(risks, key=lambda item: item["risk_72h"])
    top_event = db.scalar(select(RiskEvent).where(RiskEvent.greenhouse_id == greenhouse_id,
        RiskEvent.crop_type == resolved_crop, RiskEvent.growth_stage == resolved_stage).order_by(RiskEvent.created_at.desc()).limit(1))
    if persist:
        top_event = RiskEvent(
            greenhouse_id=greenhouse_id,
            crop_batch_id=batch.id if batch else None,
            disease_type=top["disease_type"],
            crop_type=resolved_crop,
            growth_stage=resolved_stage,
            current_score=top["current_score"],
            risk_24h=top["risk_24h"],
            risk_48h=top["risk_48h"],
            risk_72h=top["risk_72h"],
            risk_level=top["risk_level"],
            trend=top["trend"],
            factors_json=top["factors"],
            explanation=top["explanation"],
        )
        db.add(top_event)
        db.commit()
        db.refresh(top_event)
    return {
        "greenhouse_id": greenhouse_id,
        "crop_type": resolved_crop,
        "growth_stage": resolved_stage,
        "data_status": "sufficient",
        "current_environment": current,
        "risks": risks,
        "top_event": top_event,
    }


def recalculate_risk(db: Session, greenhouse_id: int, *, crop_type: str | None = None,
                     growth_stage: str | None = None) -> RiskEvent:
    result = greenhouse_risk(db, greenhouse_id, persist=True, crop_type=crop_type, growth_stage=growth_stage)
    if result["top_event"] is None:
        raise ServiceError(422, "环境数据不足，无法生成风险事件")
    return result["top_event"]


def list_risk_events(db: Session, greenhouse_id: int | None = None, limit: int = 20) -> list[RiskEvent]:
    query = select(RiskEvent)
    if greenhouse_id:
        query = query.where(RiskEvent.greenhouse_id == greenhouse_id)
    return list(db.scalars(query.order_by(RiskEvent.created_at.desc()).limit(limit)))


def generate_decision_plans(db: Session, risk_event_id: int) -> list[DecisionPlan]:
    event = db.get(RiskEvent, risk_event_id)
    if event is None:
        raise ServiceError(404, "风险事件不存在")
    existing = list(db.scalars(select(DecisionPlan).where(DecisionPlan.risk_event_id == event.id).order_by(DecisionPlan.score.desc())))
    if existing:
        return existing
    profile = get_or_update_profile(db, event.greenhouse_id, commit=False)
    base = max(event.current_score, event.risk_72h)
    humidity_bonus = min(12.0, profile.humidity_response * 1.4)
    templates = [
        ("提前通风30分钟", [{"type": "ventilation", "intensity": 30, "duration_minutes": 30, "operation": "上午提前通风30分钟"}], 23 + humidity_bonus, 86, "操作简单，适合先降低棚内高湿持续时间。"),
        ("侧窗开启40%", [{"type": "ventilation", "intensity": 40, "duration_minutes": 30, "operation": "侧窗开启40%并观察温降"}], 29 + humidity_bonus, 78, "降湿更快，但需注意降温速度和作物冷刺激。"),
        ("通风+控制灌溉", [{"type": "ventilation", "intensity": 35, "duration_minutes": 40, "operation": "通风35%"}, {"type": "irrigation", "intensity": 0, "duration_minutes": 40, "operation": "暂停非必要灌溉"}], 35 + humidity_bonus, 91, "同步减少新增湿源，适合连续高湿和灰霉病上升场景。"),
    ]
    plans: list[DecisionPlan] = []
    for name, actions, reduction, score, rationale in templates:
        expected = {
            "risk_before": round(base, 2),
            "risk_after": max(0, round(base - reduction, 2)),
            "estimated_reduction": round(reduction, 2),
            "basis": "规则启发式；未完成现场效果校准",
            "sample_count": profile.sample_count,
            "estimate_status": "exploratory",
            "score_kind": "rule_index",
        }
        plan = DecisionPlan(
            risk_event_id=event.id,
            greenhouse_id=event.greenhouse_id,
            plan_name=name,
            actions_json=actions,
            expected_result_json=expected,
            score=score,
            rationale=rationale,
        )
        db.add(plan)
        plans.append(plan)
    db.commit()
    for plan in plans:
        db.refresh(plan)
    return sorted(plans, key=lambda item: item.score, reverse=True)


def get_decision_plan(db: Session, plan_id: int) -> DecisionPlan:
    plan = db.get(DecisionPlan, plan_id)
    if plan is None:
        raise ServiceError(404, "决策方案不存在")
    return plan


def _profile_coefficients(db: Session, greenhouse_id: int) -> dict[str, float]:
    profile = get_or_update_profile(db, greenhouse_id, commit=False)
    return {
        "cooling": profile.cooling_response if profile.sample_count else 2.4,
        "humidity": profile.humidity_response if profile.sample_count else 5.8,
        "ventilation": profile.ventilation_response if profile.sample_count else 1.0,
    }


def run_simulation(db: Session, payload: SimulationRequest, *, persist: bool = True,
                   baseline_record: SensorData | None = None) -> SimulationData:
    records = _latest_records(db, payload.greenhouse_id, 24) if baseline_record is None else []
    latest = baseline_record if baseline_record is not None else (records[-1] if records else None)
    if latest is None:
        raise ServiceError(422, "暂无环境数据，无法推演")
    coeff = _profile_coefficients(db, payload.greenhouse_id)
    steps = max(1, payload.duration_minutes // 10)
    timeline = []
    if latest.temperature is None or latest.air_humidity is None or latest.quality_flag == "suspect":
        raise ServiceError(422, "缺少有效温湿度，无法模拟")
    temp = float(latest.temperature)
    humidity = float(latest.air_humidity)
    for index in range(1, steps + 1):
        ratio = (1 - math.exp(-index * 10 / 30)) / (1 - math.exp(-1))
        if payload.action_type == "ventilation":
            temp_delta = coeff["cooling"] * payload.intensity / 30 * ratio
            hum_delta = coeff["humidity"] * payload.intensity / 30 * ratio
        elif payload.action_type == "dehumidify":
            temp_delta = 0.4 * payload.intensity / 30 * ratio
            hum_delta = (coeff["humidity"] + 2.0) * payload.intensity / 30 * ratio
        elif payload.action_type == "shading":
            temp_delta = 1.6 * payload.intensity / 30 * ratio
            hum_delta = -0.6 * payload.intensity / 30 * ratio
        else:
            temp_delta = -0.2 * payload.intensity / 30 * ratio
            hum_delta = -2.0 * payload.intensity / 30 * ratio
        timeline.append({
            "minute": index * 10,
            "temperature": round(max(-20, min(60, temp - temp_delta)), 1),
            "humidity": round(max(0.0, min(100.0, humidity - hum_delta)), 1),
            "co2": latest.co2_concentration,
        })
    baseline = _snapshot_from_sensor(latest)
    estimated_risk_after = None
    if payload.decision_plan_id:
        plan = db.get(DecisionPlan, payload.decision_plan_id)
        if plan and plan.greenhouse_id != payload.greenhouse_id:
            raise ServiceError(422, "模拟方案不属于目标大棚")
        if plan:
            estimated_risk_after = plan.expected_result_json.get("risk_after")
    data = SimulationData(
        greenhouse_id=payload.greenhouse_id,
        action_type=payload.action_type,
        intensity=payload.intensity,
        duration_minutes=payload.duration_minutes,
        baseline=baseline,
        timeline=timeline,
        estimated_risk_after=estimated_risk_after,
        note="探索性模拟：按30分钟响应系数和持续时间推演，未完成现场校准；仅供人工比较。",
    )
    if persist:
        record = SimulationRecord(
            greenhouse_id=payload.greenhouse_id,
            decision_plan_id=payload.decision_plan_id,
            input_json=payload.model_dump(),
            result_json=data.model_dump(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        data.id = record.id
    return data


def execute_decision_plan(db: Session, plan_id: int, operator: str) -> tuple[DecisionPlan, Any]:
    plan = get_decision_plan(db, plan_id)
    if plan.task_id is not None:
        task = db.get(FarmTask, plan.task_id)
        if task is not None:
            return plan, task_service.get_task_detail(db, task.id)
    event = db.get(RiskEvent, plan.risk_event_id)
    if event is None:
        raise ServiceError(404, "风险事件不存在")
    greenhouse = db.get(Greenhouse, plan.greenhouse_id)
    batch = _active_batch(db, plan.greenhouse_id)
    if greenhouse is None or batch is None:
        raise ServiceError(404, "方案关联的大棚或种植批次不存在")
    first_action = plan.actions_json[0] if plan.actions_json else {}
    duration = int(first_action.get("duration_minutes", 30))
    action_text = "；".join(item.get("operation", item.get("type", "环境调控")) for item in plan.actions_json)
    task = task_service._create(  # reuse the existing audited task lifecycle.
        db,
        greenhouse=greenhouse,
        batch=batch,
        source_type="recommendation",
        source_id=plan.id,
        source_warning_id=None,
        source_disease_record_id=None,
        source_recommendation_id=None,
        title=f"{greenhouse.name}{event.risk_level}风险现场检查",
        description=f"{action_text}；来源：{event.disease_type}规则风险事件；需人工确认后执行，效果以复测为准。",
        action_type="humidity_control",
        priority="urgent" if event.risk_level in {"高", "极高"} else "high",
        planned_start_at=_now_naive(),
        due_at=_now_naive() + timedelta(minutes=duration),
        created_by=operator,
        safety_note="系统仅生成农事任务建议，需人工确认现场天气、设备与作物状态后执行。",
        commit=False,
    )
    task.evidence_snapshot_json = {**(task.evidence_snapshot_json or {}),
        "risk_event": jsonable_encoder({"id": event.id, "created_at": event.created_at, "disease_type": event.disease_type,
            "risk_72h": event.risk_72h, "explanation": event.explanation}),
        "decision_plan": jsonable_encoder({"id": plan.id, "created_at": plan.created_at, "plan_name": plan.plan_name,
            "actions": plan.actions_json, "rationale": plan.rationale})}
    plan.task_id = task.id
    plan.status = "executed"
    db.commit()
    db.refresh(plan)
    return plan, task_service.get_task_detail(db, task.id)


def evaluate_task(db: Session, task_id: int) -> TreatmentEvaluation:
    task = db.get(FarmTask, task_id)
    if task is None:
        raise ServiceError(404, "农事任务不存在")
    plan = db.scalar(select(DecisionPlan).where(DecisionPlan.task_id == task.id))
    event = db.get(RiskEvent, plan.risk_event_id) if plan else None
    if task.status != "completed":
        raise ServiceError(409, "任务完成后才能进行处置效果评估")
    existing = db.scalar(select(TreatmentEvaluation).where(TreatmentEvaluation.task_id == task_id).order_by(TreatmentEvaluation.id.desc()).limit(1))
    if existing and existing.environment_change_json.get("basis") == "measured":
        return existing
    before = (task.evidence_snapshot_json or {}).get("latest_sensor_data") or {}
    after = (task.result_snapshot_json or {}).get("latest_sensor_data") or {}
    before_assessment = (task.evidence_snapshot_json or {}).get("current_risk") or {}
    after_assessment = (task.result_snapshot_json or {}).get("current_risk") or {}
    before_score, after_score = before_assessment.get("overall_score"), after_assessment.get("overall_score")
    required=("temperature", "air_humidity", "recorded_at")
    if any(before.get(k) is None or after.get(k) is None for k in required) or before_score is None or after_score is None:
        raise ServiceError(422, "缺少有效前后实测或同口径风险分，不能评估处置效果")
    def timestamp(value):
        dt=datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    if timestamp(after["recorded_at"]) <= timestamp(before["recorded_at"]):
        raise ServiceError(422, "完成快照必须包含较创建快照更新的实测记录")
    if before_assessment.get("rule_version") != after_assessment.get("rule_version"):
        raise ServiceError(422, "前后风险规则版本不同，不能直接比较")
    before_risk, after_risk = float(before_score), float(after_score)
    temp_delta = after["temperature"] - before["temperature"]
    humidity_delta = after["air_humidity"] - before["air_humidity"]
    risk_change = round(after_risk - before_risk, 2)
    improvement = -risk_change + max(0, -humidity_delta) * 1.5 + max(0, -temp_delta) * 0.6
    if improvement >= 35:
        level, recommendation = "有效", "本次复测观察到风险下降；前后变化不代表已验证因果效果。"
    elif improvement >= 15:
        level, recommendation = "效果有限", "风险有所下降，下一次可适当提高通风比例或延长持续时间。"
    elif improvement >= -5:
        level, recommendation = "无明显效果", "环境改善不明显，建议复核设备、风口和湿源。"
    else:
        level, recommendation = "可能产生负面影响", "执行后风险未下降或环境恶化，建议暂停复用该方案并人工复盘。"
    evaluation = TreatmentEvaluation(
        task_id=task.id,
        greenhouse_id=task.greenhouse_id,
        risk_event_id=event.id if event else None,
        decision_plan_id=plan.id if plan else None,
        before_snapshot_json=jsonable_encoder(before),
        after_snapshot_json=jsonable_encoder(after),
        environment_change_json={"temperature": round(temp_delta, 2), "humidity": round(humidity_delta, 2), "basis": "measured"},
        risk_change=risk_change,
        effect_score=round(max(0, min(100, improvement + 55)), 2),
        effect_level=level,
        recommendation=recommendation,
    )
    db.add(evaluation)
    if event:
        event.status = "evaluated"
    update_profile_from_evaluations(db, task.greenhouse_id, commit=False)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def get_task_evaluation(db: Session, task_id: int) -> TreatmentEvaluation | None:
    return db.scalar(select(TreatmentEvaluation).where(TreatmentEvaluation.task_id == task_id).order_by(TreatmentEvaluation.id.desc()).limit(1))


def get_or_update_profile(db: Session, greenhouse_id: int, *, commit: bool = True) -> GreenhouseProfile:
    profile = db.scalar(select(GreenhouseProfile).where(GreenhouseProfile.greenhouse_id == greenhouse_id))
    if profile is None:
        profile = GreenhouseProfile(greenhouse_id=greenhouse_id, traits_json={
            "cooling_label": "待积累",
            "humidity_label": "待积累",
            "ventilation_label": "待积累",
        })
        db.add(profile)
        db.flush()
    update_profile_from_evaluations(db, greenhouse_id, profile=profile, commit=False)
    if commit:
        db.commit()
        db.refresh(profile)
    return profile


def update_profile_from_evaluations(db: Session, greenhouse_id: int, *, profile: GreenhouseProfile | None = None,
                                    commit: bool = True) -> GreenhouseProfile:
    profile = profile or db.scalar(select(GreenhouseProfile).where(GreenhouseProfile.greenhouse_id == greenhouse_id))
    if profile is None:
        profile = GreenhouseProfile(greenhouse_id=greenhouse_id)
        db.add(profile)
        db.flush()
    evaluations = list(db.scalars(select(TreatmentEvaluation).where(TreatmentEvaluation.greenhouse_id == greenhouse_id).order_by(TreatmentEvaluation.id.desc()).limit(20)))
    evaluations = [e for e in evaluations if e.environment_change_json.get("basis") == "measured"]
    profile.sample_count = len(evaluations)
    if evaluations:
        temp_drops = [-(item.environment_change_json.get("temperature") or 0) for item in evaluations]
        humidity_drops = [-(item.environment_change_json.get("humidity") or 0) for item in evaluations]
        risk_drops = [-(item.risk_change or 0) for item in evaluations]
        profile.sample_count = len(evaluations)
        profile.cooling_response = round(sum(temp_drops) / len(temp_drops), 2)
        profile.humidity_response = round(sum(humidity_drops) / len(humidity_drops), 2)
        profile.ventilation_response = round(max(0.4, min(1.8, profile.humidity_response / 7.0)), 2)
        profile.heat_response = round(max(0.0, 3.0 - profile.cooling_response), 2)
        profile.risk_sensitivity = round(max(0.7, min(1.4, (sum(risk_drops) / len(risk_drops)) / 24)), 2)
        profile.traits_json = {
            "cooling_label": "较快" if profile.cooling_response >= 3 else "中等" if profile.cooling_response >= 1.5 else "偏慢",
            "humidity_label": "良好" if profile.humidity_response >= 7 else "中等" if profile.humidity_response >= 3 else "偏弱",
            "ventilation_label": "良好" if profile.ventilation_response >= 1 else "需增强",
            "basis": f"过去{profile.sample_count}次处置评估统计",
        }
    if not evaluations:
        profile.cooling_response = profile.humidity_response = profile.ventilation_response = profile.heat_response = 0.0
        profile.risk_sensitivity = 1.0
        profile.traits_json = {"basis": "暂无实测处置评估；推演采用探索性默认参数"}
    if commit:
        db.commit()
        db.refresh(profile)
    return profile
