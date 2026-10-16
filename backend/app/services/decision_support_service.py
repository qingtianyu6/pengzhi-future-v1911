"""Evidence comparison, exploratory action simulation and guarded outcome modeling."""

from datetime import timedelta
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionCandidate, SensorData, WarningEvent
from app.schemas.decision_support import (CandidateEvidence, DecisionSupport,
                                          OutcomeEstimate, Scenario, ScenarioPoint)
from app.services.case_service import get_similar_cases
from app.services.errors import ServiceError


LEVEL = {"none": 0, "low": 1, "medium": 2, "high": 3}
RULE_DELTAS = {
    "observe": (0.0, 0.0),
    "roof_vent": (-1.0, -3.0),
    "fan_check": (-1.5, -4.0),
    "vent_and_fan": (-2.0, -6.0),
}


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _change_pairs(cases, offset: int):
    pairs = []
    for case in cases:
        observation = next((row for row in case.observations if row.offset_minutes == offset), None)
        if observation and observation.sensor_record_id:
            pairs.append((case, observation))
    return pairs


def _trend(db: Session, warning: WarningEvent) -> tuple[float, float]:
    readings = list(db.scalars(select(SensorData).where(
        SensorData.greenhouse_id == warning.greenhouse_id,
        SensorData.recorded_at <= warning.first_triggered_at,
        SensorData.recorded_at >= warning.first_triggered_at - timedelta(hours=2),
        SensorData.quality_flag == "valid",
    ).order_by(SensorData.recorded_at.desc()).limit(2)))
    if len(readings) < 2:
        return 0.0, 0.0
    newest, older = readings
    minutes = (newest.recorded_at.replace(tzinfo=None) - older.recorded_at.replace(tzinfo=None)).total_seconds() / 60
    if minutes < 15 or newest.temperature is None or older.temperature is None or newest.air_humidity is None or older.air_humidity is None:
        return 0.0, 0.0
    return (_clip((newest.temperature - older.temperature) * 60 / minutes, -3, 3),
            _clip((newest.air_humidity - older.air_humidity) * 60 / minutes, -10, 10))


def get_decision_support(db: Session, warning_id: int, *, max_energy_level: str = "high",
                         max_labor_level: str = "high") -> DecisionSupport:
    warning = db.get(WarningEvent, warning_id)
    if warning is None:
        raise ServiceError(404, "预警不存在")
    if warning.warning_type != "temperature_humidity_combination" or warning.crop_type != "tomato":
        raise ServiceError(422, "此版本的处置模拟仅支持番茄高温高湿预警")
    similar = get_similar_cases(db, warning_id, top_k=20)
    context = similar.query_context
    candidates = list(db.scalars(select(ActionCandidate).where(
        ActionCandidate.warning_event_id == warning_id).order_by(ActionCandidate.id)))
    history = {row.action_code: row for row in similar.action_evidence}
    cases_by_action = {row.action_code: [match.case for match in similar.matches
                                         if match.case.selected_action_code == row.action_code]
                       for row in candidates}
    candidate_evidence = []
    scenarios = []
    estimates = []
    current_risk = context.risk_score
    complete_context = context.temperature_c is not None and context.air_humidity_pct is not None and current_risk is not None
    trend_t, trend_h = _trend(db, warning)
    observe_pairs = _change_pairs(cases_by_action.get("observe", []), 60)
    observe_changes = [obs.risk_score - case.context.risk_score for case, obs in observe_pairs
                       if obs.risk_score is not None and case.context.risk_score is not None]
    observe_mean = mean(observe_changes) if len(observe_changes) >= 5 else None

    for candidate in candidates:
        code = candidate.action_code
        past = cases_by_action.get(code, [])
        stats = history.get(code)
        condition = ("需现场确认外界温湿度及顶窗可用性" if code in {"roof_vent", "vent_and_fan"}
                     else "需现场确认风机、供电及运行状态" if code == "fan_check"
                     else "安排人员持续观察并按时复测")
        candidate_evidence.append(CandidateEvidence(
            candidate_id=candidate.id, action_code=code, title=candidate.title,
            applicability="suitable" if code == "observe" else "needs_site_check",
            applicability_note=condition, energy_level=candidate.energy_level,
            labor_level=candidate.labor_level,
            historical_case_count=stats.case_count if stats else 0,
            measured_60min_count=stats.with_60min_measurement if stats else 0,
            observed_risk_decrease_count=stats.observed_risk_decrease_count if stats else 0,
            manually_resolved_count=stats.manually_resolved_count if stats else 0,
            median_temperature_change_c=stats.median_temperature_change_c if stats else None,
            median_humidity_change_pct=stats.median_humidity_change_pct if stats else None,
            evidence_level=stats.evidence_level if stats else "none",
        ))

        measured60 = _change_pairs(past, 60)
        risk_changes = [obs.risk_score - case.context.risk_score for case, obs in measured60
                        if obs.risk_score is not None and case.context.risk_score is not None]
        resolved = [obs.risk_resolved for _, obs in measured60 if obs.risk_resolved is not None]
        enough = len(risk_changes) >= 5
        observed_mean = mean(risk_changes) if risk_changes else None
        smoothed = observed_mean * len(risk_changes) / (len(risk_changes) + 5) if enough else None
        within_limit = (LEVEL[candidate.energy_level] <= LEVEL[max_energy_level]
                        and LEVEL[candidate.labor_level] <= LEVEL[max_labor_level])
        relative = observed_mean - observe_mean if enough and observe_mean is not None else None
        score = None
        if enough and within_limit and smoothed is not None:
            score = round(-smoothed * .7 - LEVEL[candidate.energy_level] * 3 - LEVEL[candidate.labor_level] * 2, 2)
        estimates.append(OutcomeEstimate(
            action_code=code, title=candidate.title, measured_cases=len(risk_changes),
            observed_risk_change_mean=round(observed_mean, 2) if observed_mean is not None else None,
            smoothed_risk_change=round(smoothed, 2) if smoothed is not None else None,
            observed_difference_vs_observe=round(relative, 2) if relative is not None else None,
            observed_resolution_rate=round(sum(resolved) / len(resolved), 3) if resolved else None,
            energy_level=candidate.energy_level, labor_level=candidate.labor_level,
            within_cost_limit=within_limit, comparison_score=score,
            note="基于观察案例的平滑估计；无法排除天气、人工选择等混杂因素。" if enough
                 else "有效 60 分钟案例不足 5 次，暂不估计方案表现。",
        ))

        if not complete_context:
            continue
        points = []
        for offset in (30, 60):
            pairs = _change_pairs(past, offset)
            changes_t = [obs.temperature - case.context.temperature_c for case, obs in pairs
                         if obs.temperature is not None and case.context.temperature_c is not None]
            changes_h = [obs.humidity - case.context.air_humidity_pct for case, obs in pairs
                         if obs.humidity is not None and case.context.air_humidity_pct is not None]
            changes_r = [obs.risk_score - case.context.risk_score for case, obs in pairs
                         if obs.risk_score is not None and case.context.risk_score is not None]
            use_history = min(len(changes_t), len(changes_h), len(changes_r)) >= 3
            if use_history:
                dt, dh, dr = median(changes_t), median(changes_h), median(changes_r)
                spread = max(8.0, (max(changes_r) - min(changes_r)) / 2)
            else:
                factor = offset / 60
                assumption_t, assumption_h = RULE_DELTAS.get(code, (0, 0))
                dt = (trend_t + assumption_t) * factor
                dh = (trend_h + assumption_h) * factor
                dr = 2.5 * dt + .7 * dh
                spread = 18.0 if offset == 60 else 12.0
            projected_risk = _clip(current_risk + dr, 0, 100)
            points.append(ScenarioPoint(
                offset_minutes=offset,
                temperature_c=round(_clip(context.temperature_c + dt, -20, 60), 2),
                humidity_pct=round(_clip(context.air_humidity_pct + dh, 0, 100), 2),
                risk_score=round(projected_risk, 2),
                risk_lower=round(_clip(projected_risk - spread, 0, 100), 2),
                risk_upper=round(_clip(projected_risk + spread, 0, 100), 2),
            ))
        historical_basis = all(len(_change_pairs(past, offset)) >= 3 for offset in (30, 60))
        scenarios.append(Scenario(
            action_code=code, title=candidate.title,
            basis="historical_median" if historical_basis else "recent_trend" if code == "observe" else "rule_assumption",
            supporting_cases=len(measured60), points=points,
            note="历史相似案例的观察中位数与离散范围" if historical_basis
                 else "基于近两小时趋势和简化动作假设的探索性区间，尚未校准。",
        ))
    return DecisionSupport(
        warning_event_id=warning_id, status="ready" if complete_context else "insufficient_context",
        current_risk_score=current_risk, candidate_evidence=candidate_evidence,
        scenarios=scenarios, outcome_model_status="observational_estimates" if any(
            item.comparison_score is not None for item in estimates) else "insufficient_data",
        outcome_estimates=estimates, max_energy_level=max_energy_level,
        max_labor_level=max_labor_level,
        explanation="方案依据、模拟与评分仅供人工比较；历史分组存在选择偏差，不是因果效果或自动处置指令。",
    )
