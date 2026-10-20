import io
from dataclasses import replace
import numpy as np
from PIL import Image
from app.services import investigation_vision as vision, investigation_service as s
from app.services.investigation_v2_service import review_payload
from app.services.investigation_experience import train_rows
from app.database import SessionLocal
from app.models.agronomist import AgronomyRecord
from sqlalchemy import select,func
from test_final_product import create_context

def image_bytes(dark=False):
    if dark: arr=np.zeros((300,400,3),dtype=np.uint8)
    else:
        rng=np.random.default_rng(2)
        arr=rng.integers(25,80,(300,400,3),dtype=np.uint8)
        arr[60:240,100:300]=[210,190,40]
        noise=rng.integers(0,20,arr.shape,dtype=np.uint8)
        arr=np.clip(arr.astype(int)+noise,0,255).astype(np.uint8)
    b=io.BytesIO();Image.fromarray(arr).save(b,format="PNG");return b.getvalue()

def test_real_local_visual_and_semantic_separation(client):
    result=client.post("/api/investigate-demo/vision",files={"image":("test.png",image_bytes(),"image/png")})
    assert result.status_code==200,result.text
    v=result.json()["data"]
    assert v["quality"]["yellow_pixel_fraction"]>.1 and v["regions"][0]["kind"]=="color_pixels"
    assert [f["key"] for f in v["features"]]==["yellow_pixels"]
    assert v["multimodal"]["status"]=="not_requested"
    assert "model_version" in v["classifier"] or v["classifier"].get("status")=="model_unavailable"
    dark=client.post("/api/investigate-demo/vision",files={"image":("dark.png",image_bytes(True),"image/png")}).json()["data"]
    assert dark["quality"]["retake"] and dark["quality"]["brightness"]==0
    assert client.post("/api/investigate-demo/vision",files={"image":("bad.jpg",b"not an image")}).status_code==422

def test_formal_photo_review_budget_restore_and_verified_stats(client):
    gid,_=create_context(client,"VISION2")
    r=client.post("/api/investigate",json={"greenhouse_id":gid,"question":"东侧番茄叶片异常","budget":2}).json()["data"]
    photo=client.post(f"/api/investigate/{r['id']}/vision",data={"version":r["version"],"action":"front","zone":"东侧"},
        files={"image":("actual.png",image_bytes(),"image/png")})
    assert photo.status_code==200,photo.text
    r=photo.json()["data"]
    assert r["payload"]["evidence"][0]["visual"]["features"][0]["key"]=="yellow_pixels"
    corrected=client.post(f"/api/investigate/{r['id']}/visual-review",json={"version":r["version"],"index":0,
        "features":{"webbing":True,"mold":False},"note":"人工近距离核查蛛网"})
    assert corrected.status_code==200,corrected.text
    r=corrected.json()["data"]
    assert r["payload"]["analysis"]["candidates"][0]["id"]=="mites"
    assert r["payload"]["analysis"]["remaining"]==1
    restored=client.get(f"/api/investigate/{r['id']}").json()["data"]
    assert restored["payload"]["history"][-1]["event"]=="visual_review"
    assert restored["payload"]["evidence"][0]["visual_review"]["webbing"] is True
    # A normal-quality completed view cannot be repeatedly uploaded.
    assert client.post(f"/api/investigate/{r['id']}/vision",data={"version":r["version"],"action":"front","zone":"东侧"},files={"image":("test.png",image_bytes(),"image/png")}).status_code==409
    final=client.post(f"/api/investigate/{r['id']}/finish",json={"version":r["version"],"note":"待独立人工核验后记录"}).json()["data"]
    assert client.get("/api/investigate/experience").json()["data"]["verified_cases"]==0
    verified=client.post(f"/api/investigate/{r['id']}/verify",json={"version":final["version"],"confirmed":True,"cause_id":"mites",
        "method":"合成测试的人工作用标记，非真实农艺验证","conclusion":"仅用于权限和统计测试"})
    assert verified.status_code==200,verified.text
    stats=client.get("/api/investigate/experience").json()["data"]
    assert stats["verified_cases"]==1 and stats["learning_status"]=="insufficient_verified_cases"
    train=client.post(f"/api/investigate/train-policy?greenhouse_id={gid}").json()["data"]
    assert train["available"] is False
    data=client.get("/api/investigate/training-data").json()["data"]
    assert len(data["cases"])==1 and "asset_id" not in data["cases"][0]["observations"][0]
    other=client.post("/api/auth/register",json={"display_name":"其他组织","phone":"13900000013","password":"Greenhouse2026"}).json()["data"]
    headers={"Authorization":"Bearer "+other["token"]}
    assert client.get(f"/api/investigate/{r['id']}",headers=headers).status_code==404
    assert client.get("/api/investigate/experience",headers=headers).json()["data"]["verified_cases"]==0

def test_quality_retake_custom_budget_and_conditions(client):
    gid,_=create_context(client,"RETAKE")
    r=client.post("/api/investigate",json={"greenhouse_id":gid,"question":"东侧番茄叶片异常","budget":4,"unavailable_actions":["normal"]}).json()["data"]
    r=client.post(f"/api/investigate/{r['id']}/vision",data={"version":r["version"],"action":"front","zone":"东侧"},files={"image":("dark.png",image_bytes(True),"image/png")}).json()["data"]
    rankings=r["payload"]["analysis"]["rankings"]
    assert next(a for a in rankings if a["id"]=="front")["retake"] is True
    assert all(a["id"]!="normal" for a in r["payload"]["analysis"]["plan"])
    again=client.post(f"/api/investigate/{r['id']}/vision",data={"version":r["version"],"action":"front","zone":"东侧"},files={"image":("different.png",image_bytes(),"image/png")})
    assert again.status_code==200,again.text
    assert again.json()["data"]["payload"]["analysis"]["remaining"]==2

def test_multimodal_adapter_requires_consent_and_uses_structured_output(monkeypatch):
    import asyncio
    from app.services import ai_provider
    calls=[]
    class Provider:
        async def chat(self,messages,tools):
            calls.append(messages)
            assert messages[1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
            return {"content":'{"features":[{"key":"webbing","suspected":true,"description":"测试提供商输出，非真实模型验证","method":"multimodal_visual"}]}'}
    monkeypatch.setattr(vision,"capabilities",lambda:{"multimodal_enabled":True})
    monkeypatch.setattr(ai_provider,"get_llm_provider",lambda:Provider())
    no=asyncio.run(vision.analyze(image_bytes(),False,True))
    assert not calls and no["multimodal"]["status"]=="not_requested"
    yes=asyncio.run(vision.analyze(image_bytes(),True,True))
    assert len(calls)==1 and yes["multimodal"]["status"]=="completed"
    assert any(f["key"]=="webbing" for f in yes["features"])

def test_case_group_split_and_synthetic_training_never_deploys():
    rows=[]
    for case in range(36):
        for step in range(2):
            rows.append({"case_id":case,"x":[case%5,step,2]+[float(i==case%10) for i in range(10)],"target_gain":float(case%2)})
    trained=train_rows(rows,synthetic=True)
    assert set(trained["train_cases"]).isdisjoint(trained["test_cases"])
    assert trained["available"] is False and trained["synthetic"] is True

def test_rejected_or_empty_visual_is_not_effective_experience():
    from app.services.investigation_experience import has_effective_evidence
    e={"features":{},"visual_review":{"yellowing":None},"reject_classifier":True,
        "visual":{"quality":{"retake":False},"features":[{"key":"yellow_pixels","suspected":True}],"classifier":{}}}
    assert not has_effective_evidence(e)
    e["visual_review"]["yellowing"]=False
    assert has_effective_evidence(e)
