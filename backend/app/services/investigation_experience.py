"""Human-verified experience statistics and case-separated, gated lightweight learning."""
from collections import defaultdict
from datetime import UTC, datetime
import json
from hashlib import sha256
from typing import Literal
import numpy as np
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.models.agronomist import AgronomyRecord
from app.models import Greenhouse
from app.services import investigation_service as s
from app.services.access import actor, require_role
from app.services.agronomist_service import serialize, save
from app.services.errors import ServiceError

class Verification(BaseModel):
    version: int = Field(ge=1)
    cause_id: str | None = None
    conclusion: str = Field(min_length=4,max_length=1000)
    method: str = Field(min_length=4,max_length=500)
    confirmed: bool = False
    dataset_usage: Literal["training", "holdout"] = "training"

def verify(db,record_id,payload):
    require_role("admin","agronomist")
    row=s.get(db,record_id)
    if row.version!=payload.version: raise ServiceError(409,"调查已更新，请刷新")
    if row.status!="completed": raise ServiceError(422,"请先归档调查，再记录人工核验")
    previous=row.payload.get("verification",{})
    if previous and previous.get("dataset_usage","training")!=payload.dataset_usage:
        raise ServiceError(409,"已核验案例不能切换训练/验证用途，避免训练信息泄漏至验证集")
    from app.services.investigation_policy import causes
    if payload.confirmed and payload.cause_id not in {c[0] for c in causes() if c[0]!="unknown"}: raise ServiceError(422,"请选择实际核验原因，不能将未知或AI判断作为标签")
    row.payload={**row.payload,"verification":{"origin":"human","confirmed":payload.confirmed,"cause_id":payload.cause_id,
        "conclusion":payload.conclusion,"method":payload.method,"dataset_usage":payload.dataset_usage,
        "verified_by":actor().id,"at":datetime.now(UTC).isoformat()}}
    s.commit(db)
    return serialize(row)

def verified_cases(db):
    return [r for r in db.scalars(select(AgronomyRecord).where(AgronomyRecord.kind=="investigation",AgronomyRecord.status=="completed"))
        if r.payload.get("verification",{}).get("origin")=="human" and r.payload["verification"].get("confirmed")]

def make_dataset(cases):
    rows=[];export=[]
    for case in cases:
        p=case.payload;target=p["verification"]["cause_id"]
        # Preserve review events as the state BEFORE the next observation. Removing
        # them would falsely attribute a human correction to a later action.
        transitions=[(p["history"][j-1]["analysis"],h["analysis"],h["added"])
            for j,h in enumerate(p["history"]) if j and h.get("added")]
        if not transitions:  # Legacy records without explicit added-event snapshots.
            history=[h for h in p["history"] if h.get("event")!="visual_review"]
            transitions=[(history[i]["analysis"],history[i+1]["analysis"],e)
                for i,e in enumerate(p["evidence"]) if i+1<len(history)]
        for before,after,e in transitions:
            before_rank=next((j for j,c in enumerate(before["candidates"]) if c["id"]==target),len(before["candidates"]))
            after_rank=next((j for j,c in enumerate(after["candidates"]) if c["id"]==target),len(after["candidates"]))
            # Proxy: movement towards the eventually human-verified target, not causal efficacy.
            gain=max(0,before_rank-after_rank)/max(1,max(len(before["candidates"]),len(after["candidates"]))-1)
            costs={a[0]:a[3] for a in s.ACTIONS}
            cost=e.get("duration_seconds")
            vector=feature_vector(before,e["action"],costs[e["action"]])
            rows.append({"case_id":case.id,"dataset_usage":p["verification"].get("dataset_usage","training"),"action":e["action"],"x":vector,"target_gain":gain,
                "observed_seconds":cost,"estimated_minutes":costs[e["action"]],
                "has_evidence":has_effective_evidence(e)})
        # No files, credentials, actor IDs or attachment paths in training export.
        export.append({"case_id":case.id,"question":p["question"],"zone":p["zone"],"budget":p["budget"],"target":target,
            "label_origin":"human_verified","dataset_usage":p["verification"].get("dataset_usage","training"),"observations":[{k:v for k,v in e.items() if k in
                ("action","zone","features","visual_review","humidity","temperature","observed_at","duration_seconds","height_cm")} for e in p["evidence"]]})
    return rows,export

def has_effective_evidence(e):
    if e.get("features") or any(v is not None for v in e.get("visual_review",{}).values()) or e.get("humidity") is not None:
        return True
    v=e.get("visual")
    if not v or v["quality"].get("retake"): return False
    from app.services.investigation_policy import VISUAL_MAP
    if any(f["suspected"] is True and VISUAL_MAP[f["key"]] not in e.get("visual_review",{}) for f in v["features"]):
        return True
    return bool(v.get("classifier",{}).get("predicted_class") and not e.get("reject_classifier"))

def feature_vector(analysis,action,cost):
    candidates=analysis["candidates"]
    gap=candidates[0]["score"]-candidates[1]["score"] if len(candidates)>1 else 0
    return [float(gap),float(len(analysis.get("facts",{}))),float(cost)]+[float(a[0]==action) for a in s.ACTIONS]

def stats(db):
    cases=verified_cases(db)
    train_cases=[c for c in cases if c.payload["verification"].get("dataset_usage","training")=="training"]
    rows,_=make_dataset(cases)
    groups=defaultdict(list)
    for r in rows: groups[r["action"]].append(r)
    return {"verified_cases":len(cases),"observations":len(rows),"minimum_training_cases":30,
        "actions":[{"action":key,"name":s.ACTION_MAP[key][1],"uses":len(items),
            "helpful_rank_changes":sum(r["target_gain"]>0 for r in items),"no_effective_evidence":sum(not r["has_evidence"] for r in items),
            "mean_actual_seconds":round(float(np.mean([r["observed_seconds"] for r in items if r["observed_seconds"] is not None])),2) if any(r["observed_seconds"] is not None for r in items) else None,
            "cost_measured_count":sum(r["observed_seconds"] is not None for r in items)} for key,items in groups.items()],
        "training_cases":len(train_cases),"holdout_cases":len(cases)-len(train_cases),
        "learning_status":"eligible_for_training" if len(train_cases)>=30 else "insufficient_verified_cases",
        "note":"仅人工核验案例进入统计。有效性为向最终核验原因的排名变化代理指标；未填写实际用时不冒充测得成本。"}

def train_rows(rows,synthetic=False):
    rows=[r for r in rows if r.get("dataset_usage","training")=="training"]
    case_ids=sorted({r["case_id"] for r in rows})
    if len(case_ids)<30 or len(rows)<30:
        return {"available":False,"reason":"至少需要30个人工核验且有观察记录的独立案例","case_count":len(case_ids)}
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error
    x=np.array([r["x"] for r in rows],dtype=float);y=np.array([r["target_gain"] for r in rows],dtype=float)
    groups=np.array([r["case_id"] for r in rows])
    train,test=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=42).split(x,y,groups))
    model=Ridge(alpha=10).fit(x[train],y[train])
    mae=float(mean_absolute_error(y[test],model.predict(x[test])))
    baseline=float(mean_absolute_error(y[test],np.full(len(test),float(y[train].mean()))))
    gate=mae<baseline and not synthetic
    return {"available":gate,"algorithm":"Ridge-ranking-gain-proxy-v1","coefficients":model.coef_.tolist(),"intercept":float(model.intercept_),
        "test_mae":mae,"constant_baseline_mae":baseline,"train_cases":sorted(set(groups[train].tolist())),
        "test_cases":sorted(set(groups[test].tolist())),"dataset_hash":sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
        "synthetic":synthetic,"reason":"仅优于留出案例常量基线时启用；该代理模型不是病害准确率或已证明最优策略"}

def train(db,gid):
    require_role("admin","agronomist")
    s.research.context(db,gid)
    rows,_=make_dataset([c for c in verified_cases(db) if c.payload["verification"].get("dataset_usage","training")=="training"])
    result=train_rows(rows)
    if "coefficients" in result:
        save(db,gid,None,"investigation_policy","探因观察策略训练",result,"active" if result["available"] else "draft")
    return result

def active_policy(db):
    row=db.scalar(select(AgronomyRecord).where(AgronomyRecord.kind=="investigation_policy",AgronomyRecord.status=="active").order_by(AgronomyRecord.updated_at.desc()).limit(1))
    return {**row.payload,"record_id":row.id} if row and row.payload.get("available") else None


def evaluation_report(db):
    """Retrospective concordance only; reserved cases never enter strategy fitting."""
    from app.services.investigation_policy import causes
    labels=[c[0] for c in causes()]
    cases=[c for c in verified_cases(db) if c.payload["verification"].get("dataset_usage")=="holdout"]
    matrix=[[0 for _ in labels] for _ in labels]
    corrected=0
    versions=set()
    for case in cases:
        p=case.payload;actual=p["verification"]["cause_id"]
        predicted=p["analysis"]["candidates"][0]["id"]
        if actual not in labels or predicted not in labels: continue
        matrix[labels.index(actual)][labels.index(predicted)]+=1
        initial=p["history"][0]["analysis"]["candidates"][0]["id"]
        corrected+=initial!=actual and predicted==actual
        versions.add(p["analysis"].get("rule_version","unknown"))
    n=sum(map(sum,matrix));correct=sum(matrix[i][i] for i in range(len(labels)))
    return {"status":"available" if n else "insufficient_holdout_cases",
        "cases":n,"labels":labels,"confusion_matrix":matrix,"matrix_axes":"rows=human_label,columns=final_candidate",
        "top1_agreement":correct/n if n else None,"corrected_cases":corrected,
        "rule_versions":sorted(versions),"field_accuracy_validated":False,
        "note":"仅保留验证集的回顾性人机结论一致率，不是盲测田间准确率。验证集不参与训练；人工核验仍需独立证据，重复植株/同批次病例不得冒充独立样本。"}
