"""Read-only case memory built from the existing production records."""

from collections import defaultdict
from datetime import datetime
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (ActionCandidate, CropBatch, FarmTask, Greenhouse,
                        Intervention, OutcomeObservation, SensorData, TaskFeedback,
                        WarningEvent)
from app.schemas.case_memory import (ActionEvidence, CaseCandidate, CaseContext,
                                     CaseData, CaseExecution, CasePage, SimilarCase,
                                     SimilarCaseResult)
from app.schemas.intervention import ObservationData
from app.services.errors import ServiceError


def _number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _snapshot_context(db: Session, warning: WarningEvent, snapshot: dict) -> CaseContext:
    greenhouse = db.get(Greenhouse, warning.greenhouse_id)
    return CaseContext(
        greenhouse_id=warning.greenhouse_id,
        greenhouse_name=greenhouse.name if greenhouse else "未知大棚",
        crop_type=snapshot.get("crop_type") or warning.crop_type,
        growth_stage=snapshot.get("growth_stage"),
        risk_type=warning.warning_type,
        temperature_c=_number(snapshot.get("temperature")),
        air_humidity_pct=_number(snapshot.get("humidity")),
        co2_ppm=_number(snapshot.get("co2")),
        soil_moisture_pct=_number(snapshot.get("soil_moisture")),
        risk_score=_number(snapshot.get("risk_score")),
        recorded_at=_parse_date(snapshot.get("recorded_at")),
    )


def _parse_date(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def build_case(db: Session, item: Intervention) -> CaseData:
    warning = db.get(WarningEvent, item.warning_event_id)
    candidate = db.get(ActionCandidate, item.candidate_id)
    if warning is None or candidate is None:
        raise ServiceError(409, "案例关联的预警或候选方案缺失")
    task = db.get(FarmTask, item.task_id) if item.task_id else None
    candidates = list(db.scalars(select(ActionCandidate).where(
        ActionCandidate.warning_event_id == warning.id).order_by(ActionCandidate.id)))
    observations = list(db.scalars(select(OutcomeObservation).where(
        OutcomeObservation.intervention_id == item.id).order_by(OutcomeObservation.offset_minutes)))
    feedbacks = list(db.scalars(select(TaskFeedback).where(
        TaskFeedback.task_id == task.id).order_by(TaskFeedback.id))) if task else []
    context = _snapshot_context(db, warning, item.before_snapshot_json or {})
    offsets = {observation.offset_minutes for observation in observations}
    flags = []
    if context.temperature_c is None or context.air_humidity_pct is None:
        flags.append("missing_before_measurement")
    if not context.growth_stage:
        flags.append("missing_growth_stage")
    for offset in (30, 60):
        if offset not in offsets:
            flags.append(f"missing_{offset}min_observation")
        elif next(obs for obs in observations if obs.offset_minutes == offset).sensor_record_id is None:
            flags.append(f"manual_only_{offset}min")
    complete = bool(task and task.status == "completed" and item.status == "completed" and {30, 60} <= offsets)
    if not complete:
        flags.append("case_in_progress")
    duration = None
    if task and task.started_at and task.completed_at:
        duration = round((task.completed_at.replace(tzinfo=None) - task.started_at.replace(tzinfo=None)).total_seconds() / 60, 1)
    return CaseData(
        id=item.id, case_code=f"CASE-{item.id:05d}", warning_event_id=warning.id,
        warning_title=warning.title, warning_status=warning.status, context=context,
        candidates=[CaseCandidate(id=row.id, action_code=row.action_code, title=row.title,
                                  energy_level=row.energy_level, labor_level=row.labor_level,
                                  selected=row.id == candidate.id) for row in candidates],
        selected_candidate_id=candidate.id, selected_action_code=candidate.action_code,
        selected_action_title=candidate.title, selection_reason=item.selection_reason,
        selected_by_user_id=item.operator_id, selected_at=item.selected_at,
        intervention_status=item.status,
        execution=CaseExecution(
            task_id=task.id if task else None, task_status=task.status if task else None,
            started_at=task.started_at if task else item.started_at,
            finished_at=task.completed_at if task else item.finished_at,
            duration_minutes=duration, assignee_name=task.assignee_name if task else None,
            execution_operator_user_id=feedbacks[-1].operator_user_id if feedbacks else None,
            feedback_notes=[row.execution_note for row in feedbacks]),
        before_snapshot=item.before_snapshot_json or {},
        observations=[ObservationData.model_validate(row) for row in observations],
        complete=complete, quality_flags=flags,
    )


def list_cases(db: Session, greenhouse_id: int | None, page: int, page_size: int) -> CasePage:
    criteria = [Intervention.greenhouse_id == greenhouse_id] if greenhouse_id else []
    total = db.scalar(select(func.count()).select_from(Intervention).where(*criteria)) or 0
    rows = db.scalars(select(Intervention).where(*criteria).order_by(Intervention.id.desc())
                      .offset((page - 1) * page_size).limit(page_size))
    return CasePage(items=[build_case(db, row) for row in rows], total=total,
                    page=page, page_size=page_size)


def list_task_case_memories(db: Session, greenhouse_id: int, limit: int = 5) -> list[dict]:
    rows = db.scalars(select(FarmTask).where(FarmTask.greenhouse_id == greenhouse_id,
        FarmTask.status == "completed", FarmTask.result_snapshot_json.is_not(None))
        .order_by(FarmTask.id.desc()).limit(100))
    result = []
    for row in rows:
        case = (row.result_snapshot_json or {}).get("agent_case")
        if case:
            result.append({"task_id": row.id, "case": case})
        if len(result) >= limit:
            break
    return result


def get_case(db: Session, case_id: int) -> CaseData:
    row = db.get(Intervention, case_id)
    if row is None:
        raise ServiceError(404, "案例不存在")
    return build_case(db, row)


def _query_context(db: Session, warning: WarningEvent) -> CaseContext:
    evidence = warning.evidence_json or {}
    current = evidence.get("current_environment") or {}
    if not isinstance(current, dict):
        current = {}
    sensor = db.scalar(select(SensorData).where(SensorData.greenhouse_id == warning.greenhouse_id,
                                                SensorData.recorded_at <= warning.first_triggered_at)
                       .order_by(SensorData.recorded_at.desc()).limit(1))
    batch = db.get(CropBatch, warning.crop_batch_id) if warning.crop_batch_id else None
    def metric(key, sensor_value):
        return _number(current.get(key)) if current.get(key) is not None else sensor_value
    greenhouse = db.get(Greenhouse, warning.greenhouse_id)
    return CaseContext(
        greenhouse_id=warning.greenhouse_id, greenhouse_name=greenhouse.name if greenhouse else "未知大棚",
        crop_type=warning.crop_type, growth_stage=batch.growth_stage if batch else None,
        risk_type=warning.warning_type,
        temperature_c=metric("temperature", sensor.temperature if sensor else None),
        air_humidity_pct=metric("air_humidity", sensor.air_humidity if sensor else None),
        co2_ppm=metric("co2_concentration", sensor.co2_concentration if sensor else None),
        soil_moisture_pct=metric("soil_moisture", sensor.soil_moisture if sensor else None),
        risk_score=_number((evidence.get("current_risk") or {}).get("overall_score")) or warning.risk_score,
        recorded_at=sensor.recorded_at if sensor else warning.first_triggered_at,
    )


FEATURES = (("temperature_c", .30, 10), ("air_humidity_pct", .30, 30),
            ("co2_ppm", .10, 1000), ("soil_moisture_pct", .10, 30),
            ("growth_stage", .20, 1))


def _distance(query: CaseContext, past: CaseContext) -> tuple[float, float, list[str]]:
    weighted = 0.0
    covered = 0.0
    names = []
    for name, weight, scale in FEATURES:
        a, b = getattr(query, name), getattr(past, name)
        if a is None or b is None:
            continue
        difference = float(a != b) if name == "growth_stage" else min(abs(a - b) / scale, 1.0)
        weighted += weight * difference
        covered += weight
        names.append(name)
    return round(weighted / covered, 4), round(covered, 2), names


def get_similar_cases(db: Session, warning_id: int, top_k: int = 5) -> SimilarCaseResult:
    warning = db.get(WarningEvent, warning_id)
    if warning is None:
        raise ServiceError(404, "预警不存在")
    query = _query_context(db, warning)
    if query.temperature_c is None or query.air_humidity_pct is None:
        return SimilarCaseResult(
            warning_event_id=warning.id, status="insufficient_context", query_context=query,
            total_eligible_cases=0, matches=[], action_evidence=[],
            explanation="当前预警缺少温度或湿度，暂不能检索相似案例。")
    rows = db.scalars(select(Intervention).where(
        Intervention.warning_event_id != warning.id,
        Intervention.status == "completed").order_by(Intervention.id.desc()))
    eligible = []
    for row in rows:
        case = build_case(db, row)
        past = case.context
        if not case.complete or past.crop_type != query.crop_type or past.risk_type != query.risk_type:
            continue
        if past.temperature_c is None or past.air_humidity_pct is None:
            continue
        distance, coverage, names = _distance(query, past)
        eligible.append(SimilarCase(case=case, distance=distance,
                                    feature_coverage=coverage, matched_features=names))
    eligible.sort(key=lambda match: (match.distance, -match.feature_coverage, -match.case.id))
    matches = eligible[:top_k]
    grouped = defaultdict(list)
    for match in matches:
        grouped[match.case.selected_action_code].append(match.case)
    evidence = []
    for code, cases in grouped.items():
        measured = [next((obs for obs in case.observations if obs.offset_minutes == 60), None)
                    for case in cases]
        temp_changes = [obs.temperature - case.context.temperature_c for case, obs in zip(cases, measured)
                        if obs and obs.temperature is not None and case.context.temperature_c is not None]
        humidity_changes = [obs.humidity - case.context.air_humidity_pct for case, obs in zip(cases, measured)
                            if obs and obs.humidity is not None and case.context.air_humidity_pct is not None]
        count = len(cases)
        evidence.append(ActionEvidence(
            action_code=code, action_title=cases[0].selected_action_title, case_count=count,
            with_60min_measurement=sum(bool(obs and obs.sensor_record_id) for obs in measured),
            observed_risk_decrease_count=sum(bool(obs and obs.sensor_record_id and obs.risk_score is not None
                                                  and case.context.risk_score is not None
                                                  and obs.risk_score < case.context.risk_score)
                                             for case, obs in zip(cases, measured)),
            manually_resolved_count=sum(bool(obs and obs.risk_resolved is True) for obs in measured),
            median_temperature_change_c=round(median(temp_changes), 2) if temp_changes else None,
            median_humidity_change_pct=round(median(humidity_changes), 2) if humidity_changes else None,
            evidence_level="limited" if count < 3 else "emerging" if count < 10 else "moderate",
        ))
    evidence.sort(key=lambda row: (-row.case_count, row.action_code))
    return SimilarCaseResult(
        warning_event_id=warning.id, status="ready", query_context=query,
        total_eligible_cases=len(eligible), matches=matches, action_evidence=evidence,
        explanation="仅展示同作物、同风险类型的已完成案例；相似度与历史观察不构成最佳方案或因果结论。")
