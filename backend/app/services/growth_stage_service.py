from datetime import date

from app.algorithms.crop_rule_registry import get_rule_profile
from app.algorithms.tomato_growth_stage_rules import TOMATO_STAGE_DAY_LIMITS


def calculate_growth_day(planted_at: date, on_date: date | None = None) -> int:
    """按自然日计算定植后的生长天数，尚未到定植日时返回 0。"""
    return max(0, ((on_date or date.today()) - planted_at).days)


def calculate_growth_stage(planted_at: date, on_date: date | None = None, crop_type: str = "tomato") -> str:
    """按作物生育期配置计算当前阶段；允许后续人工修正。"""
    day = calculate_growth_day(planted_at, on_date)
    profile=get_rule_profile(crop_type)
    if profile is None:return "规则不可用"
    limits=TOMATO_STAGE_DAY_LIMITS if crop_type=="tomato" else (15,30,50,75)
    for index,limit in enumerate(limits):
        if day<=limit:return profile.stages[index]
    return profile.stages[-1]
