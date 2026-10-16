"""Human selected, auditable tomato heat/humidity intervention workflow."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (ActionCandidate, CropBatch, DecisionRecommendation,
                        FarmTask, Intervention, OutcomeObservation, SensorData, WarningEvent)
from app.schemas.intervention import (CandidateData, InterventionData, ObservationData,
                                      ObservationRequest)
from app.schemas.task import SourceTaskCreate
from app.services.access import actor
from app.services.errors import ServiceError
from app.services.risk_service import assess_current_risk
from app.services.sensor_service import to_sensor_view
from app.services.sensor_service import VALID_BUSINESS_SOURCES
from app.services import task_service


ACTION_OPTIONS = (
    ("roof_vent", "人工检查并调整顶窗", "ventilation_check", "现场确认顶窗及天气条件后，由人员调整通风。", "low", "medium"),
    ("fan_check", "人工检查风机运行", "ventilation_check", "现场检查风机、供电和通风状态，由人员决定是否运行。", "medium", "medium"),
    ("vent_and_fan", "顶窗与风机联合检查", "humidity_control", "现场检查顶窗与风机的可用性，由人员决定联合处置。", "high", "high"),
    ("observe", "继续观察并复测", "manual_observation", "暂不调整设备，安排人员持续观察和复测。", "none", "low"),
)
OBSERVATION_TOLERANCE = timedelta(minutes=10)


def _now() -> datetime:
    return datetime.now(UTC)


def _naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _data(db: Session, item: Intervention) -> InterventionData:
    observations = list(db.scalars(select(OutcomeObservation).where(
        OutcomeObservation.intervention_id == item.id).order_by(OutcomeObservation.offset_minutes)))
    return InterventionData(**{key: getattr(item, key) for key in (
        "id", "greenhouse_id", "warning_event_id", "candidate_id", "task_id",
        "action_type", "action_params_json", "operator_id", "selection_reason",
        "status", "selected_at", "started_at", "finished_at", "before_snapshot_json")},
        observations=[ObservationData.model_validate(row) for row in observations])


def ensure_candidates(db: Session, warning_id: int, *, create: bool = False) -> list[CandidateData]:
    warning = db.get(WarningEvent, warning_id)
    if warning is None:
        raise ServiceError(404, "预警不存在")
    if warning.crop_type != "tomato" or warning.warning_type != "temperature_humidity_combination":
        return []
    existing = list(db.scalars(select(ActionCandidate).where(
        ActionCandidate.warning_event_id == warning_id).order_by(ActionCandidate.id)))
    if not existing and create:
        for code, title, action_type, description, energy, labor in ACTION_OPTIONS:
            db.add(ActionCandidate(
                greenhouse_id=warning.greenhouse_id, warning_event_id=warning.id,
                action_code=code, title=title, description=description, action_type=action_type,
                action_params_json={"manual_confirmation": True, "target": "reduce_heat_humidity"},
                expected_response_minutes=None, energy_level=energy, labor_level=labor,
                evidence_note="规则生成的候选方案；响应时间、风险降幅和成本尚无本棚验证数据。",
            ))
        db.flush()
        existing = list(db.scalars(select(ActionCandidate).where(
            ActionCandidate.warning_event_id == warning_id).order_by(ActionCandidate.id)))
    return [CandidateData.model_validate(item) for item in existing]


def select_candidate(db: Session, candidate_id: int, reason: str) -> InterventionData:
    user = actor()
    candidate = db.get(ActionCandidate, candidate_id)
    if candidate is None:
        raise ServiceError(404, "候选方案不存在")
    warning = db.get(WarningEvent, candidate.warning_event_id)
    if warning is None or warning.status not in {"open", "acknowledged"}:
        raise ServiceError(409, "预警已关闭，无法选择方案")
    prior = db.scalar(select(Intervention).where(
        Intervention.warning_event_id == warning.id,
        Intervention.status.not_in(["cancelled"])))
    if prior:
        raise ServiceError(409, "该预警已有人工选择的处置方案")
    recommendation = db.scalar(select(DecisionRecommendation).where(
        DecisionRecommendation.warning_event_id == warning.id,
        DecisionRecommendation.status.in_(["pending_review", "accepted"])).limit(1))
    if recommendation is None:
        raise ServiceError(409, "预警尚无结构化建议")
    latest = db.scalar(select(SensorData).where(SensorData.greenhouse_id == warning.greenhouse_id)
                       .order_by(SensorData.recorded_at.desc()).limit(1))
    batch = db.get(CropBatch, warning.crop_batch_id) if warning.crop_batch_id else None
    risk = assess_current_risk(to_sensor_view(latest) if latest else None,
                               batch.growth_stage if batch else None, "tomato")
    before = {"sensor_record_id": latest.id if latest else None,
              "recorded_at": latest.recorded_at.isoformat() if latest else None,
              "temperature": latest.temperature if latest else None,
              "humidity": latest.air_humidity if latest else None,
              "soil_moisture": latest.soil_moisture if latest else None,
              "co2": latest.co2_concentration if latest else None,
              "risk_score": risk.overall_score, "risk_level": risk.level,
              "warning_risk_score": warning.risk_score,
              "crop_type": warning.crop_type,
              "growth_stage": batch.growth_stage if batch else None,
              "data_source": latest.source if latest else None}
    task = task_service.create_from_warning(db, warning.id, SourceTaskCreate(
        created_by=user.display_name, action_type=candidate.action_type,
        title=candidate.title, description=candidate.description,
    ), commit=False, candidate_id=candidate.id)
    intervention = Intervention(
        greenhouse_id=warning.greenhouse_id, warning_event_id=warning.id,
        candidate_id=candidate.id, recommendation_id=recommendation.id,
        task_id=task.id, action_type=candidate.action_type,
        action_params_json=candidate.action_params_json, operator_id=user.id,
        selection_reason=reason, before_snapshot_json=before,
    )
    db.add(intervention)
    for option in db.scalars(select(ActionCandidate).where(
        ActionCandidate.warning_event_id == warning.id)):
        option.status = "selected" if option.id == candidate.id else "not_selected"
    db.commit()
    db.refresh(intervention)
    return _data(db, intervention)


def list_interventions(db: Session, greenhouse_id: int) -> list[InterventionData]:
    items = list(db.scalars(select(Intervention).where(
        Intervention.greenhouse_id == greenhouse_id).order_by(Intervention.id.desc())))
    return [_data(db, item) for item in items]


def get_intervention(db: Session, intervention_id: int) -> InterventionData:
    item = db.get(Intervention, intervention_id)
    if item is None:
        raise ServiceError(404, "处置记录不存在")
    return _data(db, item)


def record_observation(db: Session, intervention_id: int,
                       payload: ObservationRequest) -> InterventionData:
    user = actor()
    item = db.get(Intervention, intervention_id)
    if item is None:
        raise ServiceError(404, "处置记录不存在")
    task = db.get(FarmTask, item.task_id) if item.task_id else None
    if task is None or task.started_at is None:
        raise ServiceError(409, "任务尚未开始，不能复测")
    if task.status not in {"in_progress", "completed"} or item.status == "cancelled":
        raise ServiceError(409, "已取消或未执行的任务不能复测")
    due = _naive(task.started_at) + timedelta(minutes=payload.offset_minutes)
    now = _now().replace(tzinfo=None)
    if now < due:
        raise ServiceError(409, f"距离开始尚未满 {payload.offset_minutes} 分钟")
    duplicate = db.scalar(select(OutcomeObservation.id).where(
        OutcomeObservation.intervention_id == item.id,
        OutcomeObservation.offset_minutes == payload.offset_minutes))
    if duplicate:
        raise ServiceError(409, "该时间点已经完成复测")
    baseline_sensor_id = item.before_snapshot_json.get("sensor_record_id") if item.before_snapshot_json else None
    sensors = list(db.scalars(select(SensorData).where(
        SensorData.greenhouse_id == item.greenhouse_id,
        SensorData.id > (baseline_sensor_id or 0),
        SensorData.recorded_at >= due - OBSERVATION_TOLERANCE,
        SensorData.recorded_at <= min(now, due + OBSERVATION_TOLERANCE),
        SensorData.source.in_(VALID_BUSINESS_SOURCES),
        SensorData.quality_flag == "valid",
    )))
    after_due = [row for row in sensors if _naive(row.recorded_at) >= due]
    sensor = (
        min(after_due, key=lambda row: (_naive(row.recorded_at) - due).total_seconds())
        if after_due else
        min(sensors, key=lambda row: abs((_naive(row.recorded_at) - due).total_seconds()))
        if sensors else None
    )
    batch = db.get(CropBatch, task.crop_batch_id) if task.crop_batch_id else None
    risk = assess_current_risk(to_sensor_view(sensor) if sensor else None,
                               batch.growth_stage if batch else None, "tomato")
    observation = OutcomeObservation(
        intervention_id=item.id, greenhouse_id=item.greenhouse_id,
        observation_type="follow_up", observed_at=_now(),
        target_at=due, sample_delta_seconds=(int((_naive(sensor.recorded_at) - due).total_seconds())
                                             if sensor else None),
        offset_minutes=payload.offset_minutes, sensor_record_id=sensor.id if sensor else None,
        temperature=sensor.temperature if sensor else None,
        humidity=sensor.air_humidity if sensor else None,
        soil_moisture=sensor.soil_moisture if sensor else None,
        co2=sensor.co2_concentration if sensor else None,
        risk_score=risk.overall_score, manual_status=payload.manual_status,
        risk_resolved=payload.risk_resolved, notes=payload.notes, operator_id=user.id,
    )
    db.add(observation)
    db.flush()
    count = db.query(OutcomeObservation).filter(
        OutcomeObservation.intervention_id == item.id).count()
    if count >= 2 and task.status == "completed":
        item.status = "completed"
    db.commit()
    db.refresh(item)
    return _data(db, item)
