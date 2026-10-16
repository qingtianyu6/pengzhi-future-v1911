from __future__ import annotations


def risk_level(score: float) -> str:
    if score < 30:
        return "低"
    if score < 60:
        return "中"
    if score < 80:
        return "高"
    return "极高"


def risk_trend(current: float, risk_72h: float) -> str:
    delta = risk_72h - current
    if delta >= 15:
        return "持续上升"
    if delta >= 5:
        return "小幅上升"
    if delta <= -10:
        return "下降"
    return "基本稳定"


def readable_explanation(disease_name: str, score: float, contributions: list[dict]) -> str:
    top = [item for item in contributions if item["value"] > 0][:4]
    if not top:
        return f"{disease_name}风险为{score:.0f}%，当前主要环境指标未触发明显风险因子。"
    factors = "、".join(f"{item['label']}+{item['value']:.0f}%" for item in top)
    return f"{disease_name}风险为{score:.0f}%，主要由{factors}推动；建议优先关注高湿持续、通风与温差变化。"
