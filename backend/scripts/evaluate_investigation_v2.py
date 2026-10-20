"""Actual bounded strategy replay; synthetic results are never field accuracy."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services import investigation_service as s
from app.services.investigation_policy import actions

def synthetic_cases():
    cases=[]
    scenarios=[
        ("microclimate",{"local_humid":True,"poor_ventilation":True,"localized":True,"mold":False,"webbing":False}),
        ("leaf_mold",{"mold":True,"local_humid":True,"spreading":True,"webbing":False}),
        ("mites",{"webbing":True,"stippling":True,"mold":False,"yellowing":True}),
        ("water_stress",{"irrigation_changed":True,"wilting":True,"mold":False,"webbing":False,"curling":True}),
    ]
    for i,(target,facts) in enumerate(scenarios):
        for variation in range(1):
            observations=[]
            for key,_,features,_,_ in actions():
                e={"action":key,"zone":"中央" if key=="normal" else "东侧","observed_at":"2026-10-16T00:00:00+00:00",
                   "note":"合成算法行为夹具，不是真实农业观察","features":{f:facts[f] for f in features if f in facts and f not in ("local_humid","humidity_gap")}}
                if key in ("local","normal"):
                    e["humidity"]=(92 if facts.get("local_humid") else 50) if key=="local" else 60
                observations.append(e)
            cases.append({"case_id":f"synthetic-{i}-{variation}","question":"东侧番茄叶片异常","zone":"东侧","target":target,
                "label_origin":"synthetic","observations":observations})
    return cases

def evaluate(cases,budget=3):
    report=[]
    for strategy in ("direct","fixed","v1","v2"):
        successes=corrected=used=0;total_cost=0;actual_seconds=0;measured=0
        for case in cases:
            oracle={e["action"]:e for e in case["observations"]}
            evidence=[]
            initial=s.evaluate([],case["question"],case["zone"],budget)
            first=initial["candidates"][0]["id"]
            before=initial
            for _ in range(0 if strategy=="direct" else budget):
                if strategy=="fixed":
                    selected=next((a[0] for a in s.ACTIONS if a[0] in oracle and a[0] not in {e["action"] for e in evidence}),None)
                else:
                    picker=s.evaluate_v1 if strategy=="v1" else s.evaluate
                    result=picker(evidence,case["question"],case["zone"],budget)
                    selected=next((a["id"] for a in result["plan"] if a["id"] in oracle and a["id"] not in {e["action"] for e in evidence}),None)
                if selected is None: break
                e=oracle[selected]
                evidence.append(e);total_cost+=s.ACTION_MAP[selected][3];used+=1
                if e.get("duration_seconds") is not None:
                    actual_seconds+=e["duration_seconds"];measured+=1
                before=s.evaluate(evidence,case["question"],case["zone"],budget)
            final=before["candidates"][0]["id"]
            successes+=final==case["target"];corrected+=first!=case["target"] and final==case["target"]
        n=len(cases)
        report.append({"strategy":strategy,"cases":n,"correct_proportion":successes/n if n else None,
            "mean_checks":used/n if n else None,"mean_estimated_minutes":total_cost/n if n else None,
            "corrected_cases":corrected,"budget":budget,"budget_respected":used<=budget*n,
            "measured_duration_observations":measured,"mean_actual_minutes":actual_seconds/60/n if n and used==measured else None})
    synthetic=all(c.get("label_origin")=="synthetic" for c in cases)
    return {"data_kind":"synthetic_behavior_checks" if synthetic else "human_verified_limited_replay",
        "field_accuracy_claimed":False,"results":report,
        "note":"各策略相同初始证据、可见动作及预算。仅重放实际提供的动作结果，未观测动作无法估计；合成比例不代表真实农业诊断准确率。V1只负责动作选择，统一用V2评价最终证据，避免评分器不同混淆。"}

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--dataset",type=Path);parser.add_argument("--budget",type=int,default=3)
    args=parser.parse_args()
    if not 1<=args.budget<=3: parser.error("比较V1时预算仅支持1–3次")
    cases=json.loads(args.dataset.read_text(encoding="utf-8"))["cases"] if args.dataset else synthetic_cases()
    if args.dataset and any(c.get("label_origin")!="human_verified" for c in cases): parser.error("真实回放仅接受人工核验数据")
    result=evaluate(cases,args.budget)
    out=Path(__file__).resolve().parents[2]/".run/investigate-v2";out.mkdir(parents=True,exist_ok=True)
    (out/"strategy-evaluation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
