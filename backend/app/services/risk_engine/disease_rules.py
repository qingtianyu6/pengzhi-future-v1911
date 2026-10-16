from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR


RULE_PATH = BACKEND_DIR / "config" / "disease_risk_rules.json"


@lru_cache(maxsize=1)
def load_rules() -> dict[str, Any]:
    return json.loads(RULE_PATH.read_text(encoding="utf-8"))


def disease_rules() -> dict[str, Any]:
    return load_rules()["diseases"]
