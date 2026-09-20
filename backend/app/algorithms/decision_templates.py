from __future__ import annotations

from typing import Any


DECISION_RULE_VERSION = "tomato-decision-rule-v0.1"

# Stable action vocabulary for facility-tomato decision support. Every
# action is a manual check or review; none represents an executed device command.
ACTION_CATALOG = (
    "ventilation_check",
    "shading_check",
    "heating_check",
    "humidity_control",
    "condensation_inspection",
    "irrigation_check",
    "sensor_inspection",
    "manual_observation",
    "expert_review",
)

TEMPLATES: dict[str, dict[str, Any]] = {
    "high_temperature": {"code": "tomato_high_temperature_response", "priority": "high", "action_type": "ventilation_check", "title": "番茄高温时段前检查通风与遮阳条件", "steps": ["建议检查通风口、风机和棚膜通风状态", "建议根据现场光照和番茄植株状态考虑遮阳", "建议在预测风险时段前安排人工复核"]},
    "high_air_humidity": {"code": "tomato_high_humidity_response", "priority": "high", "action_type": "humidity_control", "title": "番茄持续高湿前检查通风和结露", "steps": ["建议检查通风状态及棚膜、番茄叶面和地表结露", "建议避免增加不必要的叶面湿润", "如现场条件允许，建议咨询农技人员确认调控方式；本提示不构成病害诊断"]},
    "low_temperature": {"code": "tomato_low_temperature_response", "priority": "high", "action_type": "heating_check", "title": "番茄低温时段前检查保温条件", "steps": ["建议检查棚膜密闭、保温被和加温设备状态", "建议重点关注夜间最低温度", "建议优先确认传感器读数与备用测量是否一致"]},
    "low_air_humidity": {"code": "tomato_low_humidity_response", "priority": "medium", "action_type": "irrigation_check", "title": "番茄低湿时段检查土壤和灌溉状态", "steps": ["建议检查土壤湿度和灌溉系统状态", "建议结合现场番茄植株状态判断，不仅凭空气湿度确定灌溉量", "建议安排人工观察叶片状态，不生成确定灌溉量"]},
    "temperature_humidity_combination": {"code": "tomato_temperature_humidity_combination_response", "priority": "urgent", "action_type": "condensation_inspection", "title": "优先复核番茄温湿度组合风险", "steps": ["建议优先确认温湿度传感器读数", "建议检查通风和棚内结露", "建议由现场人员结合番茄生育期和植株状态复核"]},
    "data_quality": {"code": "tomato_sensor_data_quality_response", "priority": "high", "action_type": "sensor_inspection", "title": "检查番茄棚环境数据完整性和传感器状态", "steps": ["建议检查传感器供电、连接和校准状态", "建议使用备用设备或人工测量进行对照", "数据恢复前建议暂停依赖异常指标的自动判断"]},
}


def recommendation_for_warning(warning_type: str, evidence: dict[str, Any]) -> dict[str, Any]:
    template = TEMPLATES.get(warning_type, {"code": "manual_expert_review", "priority": "medium", "action_type": "expert_review", "title": "安排人工复核", "steps": ["建议优先确认现场环境和作物状态", "如现场条件复杂，建议咨询农技人员"]})
    return {**template, "rationale": "；".join(evidence.get("trigger_reasons", [])) or "设施番茄生育期规则触发，需要人工复核", "safety_note": "决策建议需由管理人员确认后执行；系统不会自动控制设备，也不能替代农技专家判断。", "rule_version": DECISION_RULE_VERSION, "status": "pending_review"}
