from types import SimpleNamespace
from app.services import investigation_service as s
from app.services.investigation_experience import make_dataset, train_rows
from test_final_product import create_context


def test_reserved_validation_is_not_training_and_is_org_scoped(client):
    gid,_=create_context(client,"HOLDOUT")
    assert client.get('/api/investigate/evaluation').json()['data']['top1_agreement'] is None
    r=client.post('/api/investigate',json={'greenhouse_id':gid,'question':'番茄叶片出现蛛网和黄化','budget':2}).json()['data']
    r=client.post(f"/api/investigate/{r['id']}/evidence",json={'version':r['version'],'evidence':{'action':'back','zone':'东侧','features':{'webbing':True,'mold':False}}}).json()['data']
    r=client.post(f"/api/investigate/{r['id']}/finish",json={'version':r['version'],'note':'测试夹具的归档结论'}).json()['data']
    verification={'version':r['version'],'cause_id':'mites','method':'测试夹具，非真实田间核验','conclusion':'仅测试保留验证数据隔离','confirmed':True,'dataset_usage':'holdout'}
    result=client.post(f"/api/investigate/{r['id']}/verify",json=verification)
    assert result.status_code==200,result.text
    r=result.json()['data']
    report=client.get('/api/investigate/evaluation').json()['data']
    assert report['cases']==1 and report['top1_agreement']==1
    assert sum(map(sum,report['confusion_matrix']))==1 and not report['field_accuracy_validated']
    stats=client.get('/api/investigate/experience').json()['data']
    assert stats['training_cases']==0 and stats['holdout_cases']==1
    assert client.post(f'/api/investigate/train-policy?greenhouse_id={gid}').json()['data']['case_count']==0
    # Relabeling a training case as held-out must not become a leakage bypass.
    changed=client.post(f"/api/investigate/{r['id']}/verify",json={**verification,'version':r['version'],'dataset_usage':'training'})
    assert changed.status_code==409
    other=client.post('/api/auth/register',json={'display_name':'独立组织','phone':'13900000014','password':'Greenhouse2026'}).json()['data']
    isolated=client.get('/api/investigate/evaluation',headers={'Authorization':'Bearer '+other['token']}).json()['data']
    assert isolated['cases']==0 and isolated['top1_agreement'] is None


def test_train_rows_excludes_holdout_even_when_passed_directly():
    rows=[{'case_id':i,'dataset_usage':'holdout','x':[1,2,3],'target_gain':1} for i in range(35)]
    assert train_rows(rows)['case_count']==0


def test_review_gain_is_not_attributed_to_next_observation():
    def analysis(rank):
        ids=['mites','leaf_mold'] if rank==0 else ['leaf_mold','mites']
        return {'candidates':[{'id':key,'score':2-i} for i,key in enumerate(ids)],'facts':{}}
    first={'action':'front','features':{},'zone':'东侧'}
    second={'action':'local','features':{},'zone':'东侧','humidity':60}
    payload={'question':'测试','zone':'东侧','budget':2,'verification':{'cause_id':'mites','dataset_usage':'training'},
        'evidence':[first,second], 'history':[
            {'analysis':analysis(1)},
            {'added':first,'analysis':analysis(1)},
            {'event':'visual_review','analysis':analysis(0)},
            {'added':second,'analysis':analysis(0)}]}
    rows,_=make_dataset([SimpleNamespace(id=1,payload=payload)])
    assert len(rows)==2
    assert all(r['target_gain']==0 for r in rows)
