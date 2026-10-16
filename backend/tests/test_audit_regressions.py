from datetime import datetime, UTC, timedelta
from sqlalchemy import select, func
from app.models import SensorData, FarmTask, RiskEvent, SimulationRecord, GreenhouseProfile
from app.database import SessionLocal
from app.services.risk_engine.environmental_features import build_features
from app.services.v2_decision_service import evaluate_task
from app.services.errors import ServiceError
from app.schemas.common import ApiResponse
from app.schemas.auth import UserData
import pytest

def greenhouse(client, code='AUDIT'):
    result=client.post('/api/greenhouses',json={'code':code,'name':'回归检查棚','location':'山东莘县','area_mu':2})
    assert result.status_code==201,result.text
    return result.json()['data']['id']

def batch(client,gid):
    result=client.post(f'/api/greenhouses/{gid}/crop-batches',json={'batch_code':'TEST-B','variety':'番茄','crop_type':'tomato','growth_stage':'开花坐果期','planted_at':'2026-09-01'})
    assert result.status_code==201
    return result.json()['data']['id']

def test_no_metrics_rejected_and_missing_temperature_cannot_simulate(client):
    gid=greenhouse(client); now=datetime.now(UTC)
    empty={'greenhouse_id':gid,'source':'sensor','recorded_at':now.isoformat()}
    assert client.post('/api/sensors/batch',json={'items':[empty]}).status_code==422
    assert client.post('/api/sensors/batch',json={'items':[{**empty,'air_humidity':80}]}).status_code==200
    assert client.post('/api/simulation/run',json={'greenhouse_id':gid}).status_code==422
    assert client.get(f'/api/risk/greenhouse/{gid}').json()['data']['data_status']=='insufficient_data'

def test_complementary_devices_merge_and_retries_do_not_overwrite(client):
    gid=greenhouse(client);now=datetime.now(UTC).isoformat()
    base={'greenhouse_id':gid,'source':'sensor','recorded_at':now}
    items=[{**base,'device_id':'temperature','temperature':25},{**base,'device_id':'humidity','air_humidity':85}]
    result=client.post('/api/sensors/batch',json={'items':items});assert result.status_code==200
    latest=client.get(f'/api/sensors/latest?greenhouse_id={gid}').json()['data']
    assert latest['temperature']==25 and latest['air_humidity']==85
    result=client.post('/api/sensors/batch',json={'items':items}).json()['data']
    assert result['success_count']==0 and result['skipped_count']==2

def test_high_humidity_uses_elapsed_time_and_breaks_at_normal_sample():
    now=datetime.now(UTC)
    rows=[SensorData(recorded_at=now+timedelta(minutes=i*5),temperature=25+i,air_humidity=85) for i in range(12)]
    features=build_features(rows)
    assert features.high_humidity_hours==pytest.approx(55/60,abs=.01)
    assert features.temperature_trend_per_hour==12
    rows[-2].air_humidity=60
    assert build_features(rows).high_humidity_hours==0

def test_simulation_duration_changes_end_and_zero_intensity_keeps_baseline(client):
    gid=greenhouse(client);now=datetime.now(UTC).isoformat()
    client.post('/api/sensors/batch',json={'items':[{'greenhouse_id':gid,'source':'sensor','recorded_at':now,'temperature':25,'air_humidity':85}]})
    def simulate(duration,intensity=30):
        r=client.post('/api/simulation/run',json={'greenhouse_id':gid,'duration_minutes':duration,'intensity':intensity})
        assert r.status_code==200,r.text
        return r.json()['data']['timeline'][-1]
    assert simulate(10)['humidity']>simulate(60)['humidity']
    assert simulate(60,0)['temperature']==25
    assert simulate(60,0)['humidity']==85

def test_missing_completed_snapshot_never_becomes_measured_effect(client):
    gid=greenhouse(client);bid=batch(client,gid)
    task=client.post('/api/tasks',json={'greenhouse_id':gid,'crop_batch_id':bid,'title':'检查','description':'现场检查','action_type':'manual_observation','priority':'medium','created_by':'测试员'}).json()['data']
    with SessionLocal() as db:
        row=db.get(FarmTask,task['id']);row.status='completed';row.evidence_snapshot_json={};row.result_snapshot_json={};db.commit()
    result=client.post(f"/api/tasks/{task['id']}/evaluate",json={'operator':'测试员'})
    assert result.status_code==422

def test_delete_removes_v2_records_and_empty_shelf_is_not_connected(client):
    gid=greenhouse(client)
    detail=client.get(f'/api/greenhouses/{gid}').json()['data']
    assert detail['data_status']=='no_data' and detail['device_count']==0 and detail['last_recorded_at'] is None
    with SessionLocal() as db:
        db.add(GreenhouseProfile(greenhouse_id=gid))
        db.add(SimulationRecord(greenhouse_id=gid,input_json={},result_json={}))
        db.commit()
    assert client.delete(f'/api/greenhouses/{gid}').status_code==200
    with SessionLocal() as db:
        for model in [GreenhouseProfile,SimulationRecord]:
            assert db.scalar(select(func.count()).select_from(model).where(model.greenhouse_id==gid))==0

def test_utc_naive_api_timestamp_gets_timezone():
    result=ApiResponse(data={'created_at':datetime(2026,10,14,14,55)}).model_dump(mode='json')
    assert result['data']['created_at'].endswith('Z')

def test_password_reset_restricted_to_current_organization_and_revokes_session(client):
    member=client.post('/api/auth/members',json={'display_name':'检查成员','phone':'13900001111','password':'Password123','role':'observer'}).json()['data']
    token=client.post('/api/auth/login',json={'phone':'13900001111','password':'Password123'}).json()['data']['token']
    assert client.patch(f"/api/auth/members/{member['id']}",json={'new_password':'Password456'}).status_code==200
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401
    me=client.get('/api/auth/me').json()['data']
    assert client.patch(f"/api/auth/members/{me['id']}",json={'is_active':False}).status_code==409

def test_login_throttle_stops_repeated_attempts(client):
    attempts=[client.post('/api/auth/login',json={'phone':'13900002222','password':'incorrect'}).status_code for _ in range(11)]
    assert attempts[:10]==[401]*10 and attempts[-1]==429


def test_legacy_profile_is_not_counted(client):
    from app.services.v2_decision_service import _profile_coefficients
    gid=greenhouse(client)
    with SessionLocal() as db:
        db.add(GreenhouseProfile(greenhouse_id=gid, cooling_response=99, humidity_response=99, sample_count=4))
        db.commit()
        assert _profile_coefficients(db,gid)['cooling']==2.4
        profile=db.scalar(select(GreenhouseProfile).where(GreenhouseProfile.greenhouse_id==gid))
        assert profile.sample_count==0 and profile.cooling_response==0


def test_portable_scaler_preserves_prediction_input_precision():
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from app.ml.portable_scalers import PortableStandardScaler
    original=StandardScaler().fit([[15,80],[25,60],[35,70]])
    converted=PortableStandardScaler({'mean':original.mean_.tolist(),'scale':original.scale_.tolist(),
        'with_mean':True,'with_std':True,'features':2})
    for dtype in (np.float32,np.float64):
        inputs=np.asarray([[18,83],[21,72],[30,65]],dtype=dtype)
        np.testing.assert_array_equal(converted.transform(inputs),original.transform(inputs))
        np.testing.assert_array_equal(converted.inverse_transform(inputs),original.inverse_transform(inputs))
    with pytest.raises(ValueError):converted.transform([[1,2,3]])
