import copy
from datetime import UTC, datetime
from hashlib import sha256
from pydantic import BaseModel, Field
from app.services import investigation_service as s, investigation_vision as vision
from app.services.agronomist_service import serialize
from app.services.errors import ServiceError

class VisualReview(BaseModel):
    version: int = Field(ge=1)
    index: int = Field(ge=0,le=9)
    features: dict[str,bool | None] = Field(default_factory=dict,max_length=6)
    reject_classifier: bool = False
    note: str = Field(default="",max_length=1000)

def writable(db,record_id,version):
    row=s.get(db,record_id)
    if row.version!=version: raise ServiceError(409,"调查已更新，请刷新")
    if row.status in ("completed","archived"): raise ServiceError(409,"调查已归档，不覆盖历史结论")
    return row

async def add_photo(db,record_id,version,action,zone,content,filename,use_multimodal=False):
    from app.services.forum_service import upload
    row=writable(db,record_id,version)
    if action not in ("front","back","plant"): raise ServiceError(422,"照片检查请选择正面、背面或完整植株")
    if zone not in s.ZONES: raise ServiceError(422,"未知区域")
    payload=copy.deepcopy(row.payload)
    if len(payload["evidence"]) >= (payload["budget"] or 10): raise ServiceError(409,"检查预算已用完，未调用图片模型")
    if action in payload["context"].get("unavailable_actions",[]): raise ServiceError(422,"该检查已标记无法执行")
    existing=[e for e in payload["evidence"] if e["action"]==action]
    if existing:
        old=existing[-1].get("visual")
        if not old or not old["quality"].get("retake") or old["image_hash"]==sha256(content).hexdigest():
            raise ServiceError(409,"该检查已完成；仅质量不足时允许换照片重拍")
    result=await vision.analyze(content,use_multimodal,allow_external=True)
    import io
    normalized=io.BytesIO();vision.decode(content).save(normalized,format="JPEG",quality=92)
    asset=upload(db,"observation.jpg",normalized.getvalue(),"image/jpeg")
    db.refresh(row)
    if row.version!=version: raise ServiceError(409,"图片分析期间调查已更新，请刷新后重试")
    evidence=s.Evidence(action=action,zone=zone,asset_id=asset["id"],visual=vision.VisualResult.model_validate(result),
        note="照片已进行实际视觉分析；自动可疑特征按低权重融合，未替代人工确诊。拍摄时间未核验，所记时间为上传时间")
    row.payload=s.append(payload,evidence)
    row.status=row.payload["analysis"]["status"]
    s.commit(db)
    return serialize(row)

def review_payload(payload,index,features,reject_classifier=False,note=""):
    from app.services.investigation_policy import VISUAL_MAP
    if index>=len(payload["evidence"]): raise ServiceError(404,"观察不存在")
    e=payload["evidence"][index]
    if not e.get("visual"): raise ServiceError(422,"此观察没有视觉分析")
    if set(features)-set(VISUAL_MAP.values()): raise ServiceError(422,"未知视觉特征")
    old=payload["analysis"]
    e["visual_review"]={**e.get("visual_review",{}),**features}
    e["reject_classifier"]=reject_classifier
    e["review_note"]=note
    e["reviewed_at"]=datetime.now(UTC).isoformat()
    analysis=s.evaluate(payload["evidence"],payload["question"],payload["zone"],payload["budget"],payload["context"])
    payload["analysis"]=analysis
    payload["history"].append({"round":len(payload["history"]),"event":"visual_review","at":e["reviewed_at"],
        "leader":analysis["candidates"][0]["name"],"previous_leader":old["candidates"][0]["name"],
        "changes":[{"name":c["name"],"before":next((p["score"] for p in old["candidates"] if p["id"]==c["id"]),0),"after":c["score"]} for c in analysis["candidates"]],
        "changed_evidence":index,"analysis":analysis})
    return payload

def review(db,record_id,request):
    row=writable(db,record_id,request.version)
    row.payload=review_payload(copy.deepcopy(row.payload),request.index,request.features,request.reject_classifier,request.note)
    row.status=row.payload["analysis"]["status"]
    s.commit(db)
    return serialize(row)
