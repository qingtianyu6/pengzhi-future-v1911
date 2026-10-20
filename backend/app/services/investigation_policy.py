"""V2 evidence fusion and deterministic, feasibility-aware active observation."""
from datetime import datetime, timezone
from itertools import combinations
from app.services import investigation_service as v1

EXTRA_LABELS={"yellowing":"叶片黄化待核查","spots":"叶面斑点","necrosis":"疑似坏死","curling":"卷叶或形态异常"}
VISUAL_MAP={"yellow_pixels":"yellowing","yellowing":"yellowing","spots":"spots","necrosis":"necrosis","mold":"mold","webbing":"webbing","curling":"curling"}

def causes():
    items=[(k,n,dict(e),s) for k,n,e,s in v1.CAUSES]
    for k,_,effects,_ in items:
        # Correlated absolute humidity and humidity difference should not overwhelm
        # a directly observed morphological sign by being counted as independent.
        if k == "microclimate": effects.update(local_humid=3,humidity_gap=2)
        if k == "water_stress": effects.update(yellowing=1,curling=1)
        if k == "leaf_mold": effects.update(spots=1,necrosis=1)
        if k == "mites": effects.update(yellowing=1)
    items.insert(-1,("leaf_spot","叶斑类表现（病因待鉴别）",{"spots":4,"necrosis":3,"yellowing":1,"mold":-2,"webbing":-2},[2]))
    return items

def actions():
    items=[]
    for key,name,features,cost,target in v1.ACTIONS:
        features=list(features)
        if key == "front": features += ["yellowing","spots","necrosis","curling"]
        if key == "symptom": features = ["stippling","yellowing","curling","wilting","localized"]
        items.append((key,name,features,cost,target))
    return items

def infer(evidence,question,zone,budget,context=None):
    context=context or {}
    old=v1.evaluate_v1(evidence,question,zone,min(budget,3) if budget else 0,context)
    labels={**v1.FEATURE_LABELS,**EXTRA_LABELS}
    facts,trust,origins={}, {}, {}
    ledger=[]
    def put(key,value,reliability,origin):
        facts[key]=value;trust[key]=reliability;origins[key]=origin
    latest=context.get("latest")
    if latest:
        ledger.append({"id":"existing-environment","data_type":"environment","time":latest.get("recorded_at"),"zone":None,
            "source":"已有传感器/导入快照","reliability":"valid_record_unlocated" if context.get("fresh") else "historical_only"})
    if context.get("batch"):
        ledger.append({"id":"crop-stage","data_type":"crop","source":"本棚种植批次","zone":None,"reliability":"recorded_context",
            "stage":context["batch"].get("growth_stage"),"note":"V2尚无经验证的分阶段概率参数，不编造阶段加权"})
    for key in ("operations","diseases","knowledge"):
        if context.get(key): ledger.append({"id":key,"data_type":key,"source":"现有平台记录/适用知识","zone":None,
            "reliability":"reference_context_only","count":len(context[key])})
    for i,e in enumerate(evidence):
        visual=e.get("visual")
        if visual and not visual["quality"].get("retake"):
            for f in visual["features"]:
                key=VISUAL_MAP[f["key"]]
                if key in e.get("visual_review",{}) or key in e.get("features",{}): continue
                # Non-detection from an uncalibrated visual model is not negative evidence.
                if f["suspected"] is True and trust.get(key,0)<.35:
                    put(key,True,.2 if f["key"]=="yellow_pixels" else .35,
                        f"图片#{i+1} 自动可疑特征，尚未确认；{f['description']}")
        for key,value in e.get("features",{}).items():
            put(key,value,1.0,f"人工观察#{i+1} · {e['zone']} · {e['observed_at']}")
        for key,value in e.get("visual_review",{}).items():
            if value is not None: put(key,value,1.0,f"图片#{i+1} 人工修正 · {e['zone']}")
        for key in ("local_humid","humidity_gap"):
            if key in old["facts"]:
                put(key,old["facts"][key],1.0,"区域实测计算，位置由用户标记，仪器误差尚未校准")
        ledger.append({"id":f"observation-{i+1}","data_type":"visual" if visual else "environment" if e.get("humidity") is not None else "manual",
            "source":"本地/多模态图片分析与人工复核" if visual else "关联采样/"+e.get("data_source","unknown") if e.get("sensor_id") else "用户现场观察",
            "time":e["observed_at"],"zone":e["zone"],"reliability":("rejected" if all(v is None for v in e["visual_review"].values()) else "human_reviewed") if e.get("visual_review") else "review_required" if visual else "user_reported",
            "time_kind":"upload_time_capture_unverified" if visual else "observed_or_sampled",
            "height_cm":e.get("height_cm"),"sensor_id":e.get("sensor_id")})
    candidates=[]
    for key,name,effects,source_indices in causes():
        score=1.0 if key=="microclimate" and any(w in question for w in ["东侧","西侧","局部","一侧"]) else 0.0
        supporting=["问题描述中的空间差异（弱线索+1，非实测）"] if score else []
        conflicting=[]
        if key in ("microclimate","leaf_mold") and any((s.get("air_humidity") or 0)>=85 for s in context.get("history",[])):
            score+=1;supporting.append("历史有效采样中有高湿，弱线索+1；不能当作当前局部实测")
        if key in ("leaf_mold","leaf_spot"):
            for e in evidence:
                classifier=(e.get("visual") or {}).get("classifier",{})
                cls=classifier.get("predicted_class")
                matching=(key=="leaf_mold" and cls=="leaf_mold") or (key=="leaf_spot" and cls in ("early_blight","late_blight","septoria_leaf_spot"))
                if matching and not e["visual"]["quality"].get("retake") and not e.get("reject_classifier"):
                    score+=.5;supporting.append("现有六分类模型有相关候选（+0.5），未经本地标定，未转换为细粒度症状")
                    break
        for feature,weight in effects.items():
            if feature not in facts: continue
            # Absence of an incompatible sign does not establish an unrelated cause.
            if not facts[feature] and weight<0: continue
            delta=(weight if facts[feature] else -weight)*trust[feature]
            score+=delta
            (supporting if delta>0 else conflicting).append(f"{labels[feature]}：{'有' if facts[feature] else '未见'}；{origins[feature]}（{delta:+.2f}）")
        candidates.append({"id":key,"name":name,"score":round(score,3),"support":supporting,"conflict":conflicting,
            "missing":[labels[f] for f in effects if trust.get(f,0)<1],"key_features":[labels[f] for f in effects],
            "sources":[v1.SOURCES[s] for s in source_indices],"state":"待人工核实"})
    candidates.sort(key=lambda c:(-c["score"],c["id"]))
    ranked=[c for c in candidates if c["id"]!="unknown"]
    active=[c for i,c in enumerate(ranked) if i<2 or ranked[0]["score"]-c["score"]<=3]
    effects={k:e for k,_,e,_ in causes()}
    # Focus on the leading unresolved competing explanations, not every catalog pair.
    pairs=list(combinations(active,2))
    max_score=active[0]["score"] if active else 0
    weights={c["id"]:1/(1+max_score-c["score"]) for c in active}
    penalty=.65 if budget==1 else .3 if budget==2 else .16 if budget else .08
    last={e["action"]:e for e in evidence}
    unavailable=context.get("unavailable_actions",[])
    rankings=[]
    for key,name,features,cost,target in actions():
        retake=key in last and bool((last[key].get("visual") or {}).get("quality",{}).get("retake"))
        if key in last and not retake: continue
        uncertainty={f:1-trust.get(f,0) for f in features}
        difference=0.0;distinguished=set()
        for a,b in pairs:
            d=sum(abs(effects[a["id"]].get(f,0)-effects[b["id"]].get(f,0))*uncertainty[f] for f in features)
            difference+=d*weights[a["id"]]*weights[b["id"]]
            if d: distinguished.update([a["name"],b["name"]])
        novelty=sum(uncertainty.values())/len(features)
        if retake: difference+=3;novelty=max(novelty,.8)
        score=round(difference*novelty-penalty*cost,4)
        feasible=key not in unavailable
        target_zone=next((z for z in v1.ZONES if z!=zone),"中央") if key=="normal" else zone
        item={"id":key,"name":("重拍：" if retake else "")+name,"features":features,"cost_minutes":cost,
            "target":target,"target_zone":target_zone,"can_execute":feasible,"retake":retake,
            "possible_outcomes":["发现相关特征","明确未见","质量不足或无法判断"],
            "discrimination":round(difference,4),"missing_ratio":novelty,"cost_penalty":penalty,"score":score,
            "distinguishes":sorted(distinguished),"strategy":"v2-top-competing-evidence",
            "reason":f"针对当前前{len(active)}位解释，剩余证据缺失度{novelty:.2f}；预计{cost}分钟。"+("上次照片质量不足，需换照片重拍。" if retake else "")+
                     ("" if feasible else "用户标记无法执行，不纳入推荐。")}
        rankings.append(item)
    rankings.sort(key=lambda a:(-a["score"],a["cost_minutes"],a["id"]))
    learned=context.get("learned_policy")
    if learned and learned.get("available") and not learned.get("synthetic"):
        from app.services.investigation_experience import feature_vector
        for item in rankings:
            vector=feature_vector({"candidates":candidates,"facts":facts},item["id"],item["cost_minutes"])
            coefficients=learned.get("coefficients",[])
            if len(coefficients)!=len(vector): continue
            prediction=max(0,min(1,sum(a*b for a,b in zip(vector,coefficients))+learned["intercept"]))
            item["learned_adjustment"]=round(.25*prediction,4)
            item["score"]=round(item["score"]+item["learned_adjustment"],4)
            item["reason"]+=f"采用已通过案例留出验证的排名增益代理模型，调整{item['learned_adjustment']}，不是病害概率。"
        rankings.sort(key=lambda a:(-a["score"],a["cost_minutes"],a["id"]))
    remaining=max(0,(budget or 10)-len(evidence))
    useful=[a for a in rankings if a["can_execute"] and a["missing_ratio"]>0 and a["score"]>0]
    status="budget_exhausted" if not remaining else "investigating" if useful else "review_required"
    summary="检查预算已耗尽，保留证据供人工复核。" if not remaining else "没有可执行且正价值的检查，请人工核实未决事项。" if not useful else "优先调查："+candidates[0]["name"]+"；尚未确诊。"
    points=[{"zone":e["zone"],"humidity":e.get("humidity"),"temperature":e.get("temperature"),"time":e["observed_at"],"height_cm":e.get("height_cm"),"source":e.get("data_source","manual")} for e in evidence if e.get("humidity") is not None]
    local=next((e for e in reversed(evidence) if e["action"]=="local" and e.get("humidity") is not None),None)
    normal=next((e for e in reversed(evidence) if e["action"]=="normal" and e.get("humidity") is not None),None)
    comparison=None
    if local and normal and local["zone"]!=normal["zone"]:
        seconds=abs((datetime.fromisoformat(local["observed_at"])-datetime.fromisoformat(normal["observed_at"])).total_seconds())
        if seconds<=3600:
            comparison={"abnormal_zone":local["zone"],"reference_zone":normal["zone"],"delta_humidity_points":round(local["humidity"]-normal["humidity"],2),
                "delta_temperature_c":round(local["temperature"]-normal["temperature"],2) if local.get("temperature") is not None and normal.get("temperature") is not None else None,
                "time_difference_seconds":seconds,"note":"高度、仪器与取样可比性仍需人工核查，不生成全棚空间插值"}
    return {"rule_version":"investigation-2.0","candidates":candidates,"rankings":rankings,"next":useful[0] if useful and remaining else None,
        "plan":useful[:remaining],"remaining":remaining,"status":status,"summary":summary,"facts":facts,"feature_reliability":trust,
        "evidence_ledger":ledger,"spatial":{"points":points,"comparison":comparison,"coverage":"不同区域、时间相近测量已配对；高度/仪器可比性仍需核查" if comparison else "可比测点覆盖不足，不生成热力图"},
        "score_note":"V2确定性区分度/成本评分，不是病害概率。自动视觉特征为低权重可疑证据，人工确认或修正后按人工证据重算。"}
