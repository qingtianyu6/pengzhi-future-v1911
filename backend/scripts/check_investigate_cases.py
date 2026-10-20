"""Reproduce the three acceptance scenarios without a model or database writes."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.investigation_service import Demo, Evidence, demo

first = demo(Demo())["payload"]["analysis"]
updated = demo(Demo(evidence=[
    Evidence(action="local", zone="东侧", humidity=45),
    Evidence(action="back", zone="东侧", features={"webbing": True, "mold": False})
]))["payload"]["analysis"]
result = {"active": {"candidates": len(first["candidates"]), "leader": first["candidates"][0]["name"], "next": first["next"]["name"]},
    "revision": {"leader": updated["candidates"][0]["name"], "next": updated["next"]["name"],
                 "previous_actions_excluded": all(a["id"] not in ("local", "back") for a in updated["rankings"])},
    "budgets": [{"budget": b, "plan_length": len(demo(Demo(budget=b))["payload"]["analysis"]["plan"])} for b in (1, 2, 3, 0)],
    "model_called": False}
out = Path(__file__).resolve().parents[2] / ".run" / "investigate"
out.mkdir(parents=True, exist_ok=True)
(out / "scenarios.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
