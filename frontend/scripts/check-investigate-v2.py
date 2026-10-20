"""Actual image upload -> local vision -> human correction -> backend recalculation."""
from pathlib import Path
import io,json,time
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[2]
out=root/'.run/investigate-v2';out.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(22)
arr=rng.integers(30,85,(300,400,3),dtype=np.uint8)
arr[60:230,100:300]=[210,190,30]
arr=np.clip(arr.astype(int)+rng.integers(0,18,arr.shape),0,255).astype(np.uint8)
blob=io.BytesIO();Image.fromarray(arr).save(blob,format='PNG')
checks=[];errors=[]
with sync_playwright() as p:
    api=p.request.new_context(base_url='http://127.0.0.1:8001')
    for _ in range(30):
        try:
            if api.get('/api/health',timeout=2000).status==200: break
        except Exception: time.sleep(1)
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1500,'height':1000},timezone_id='Asia/Shanghai')
    page.set_default_timeout(30000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    writes=[]
    page.on('request',lambda r:writes.append(r.url) if '/api/investigate/' in r.url and r.method=='POST' else None)
    page.goto('http://127.0.0.1:5174/platform/investigate?mode=guest&greenhouse_id=101',wait_until='networkidle')
    page.locator('input[type=file]').set_input_files({'name':'actual-pixel-fixture.png','mimeType':'image/png','buffer':blob.getvalue()})
    card=page.locator('.investigate-visual-card').first
    card.get_by_text('黄色像素（未分割叶片）',exact=False).first.wait_for()
    checks.append('real uploaded pixels produce structured visual result and image preview')
    assert page.get_by_text('图上仅标注实际黄色像素范围，不是病害检测框。',exact=True).count()==1
    checks.append('pixel region labelled accurately, no fabricated lesion boxes')
    card.get_by_text('确认、修正或拒绝视觉证据',exact=True).click()
    for label,option in [('蛛网状结构','已核查：有'),('疑似霉层','已核查：未见')]:
        select=card.get_by_label(label,exact=True)
        select.focus();select.press('ArrowDown')
        if option=='已核查：未见': select.press('ArrowDown')
        select.press('Enter')
    card.get_by_role('button',name='保存人工核查并重算',exact=True).click()
    page.get_by_text('第2轮 · 优先调查：叶螨等刺吸危害待鉴别',exact=True).wait_for()
    checks.append('human correction changes candidate ranking and timeline without another check')
    stored=page.evaluate('JSON.parse(sessionStorage.getItem("pengzhi-investigations-v1"))[0]')
    assert len(stored['payload']['evidence'])==1 and stored['payload']['analysis']['remaining']==2
    assert stored['payload']['evidence'][0]['visual_review']['mold'] is False
    assert stored['payload']['analysis']['next']['id']!='front'
    checks.append('completed photo excluded and review does not spend budget')
    # A new back-view image is analyzed in the same investigation.
    select=page.get_by_role('combobox',name='照片观察动作',exact=True)
    select.focus();select.press('ArrowDown')
    page.locator('.ant-select-dropdown:visible').get_by_text('叶片背面',exact=True).click()
    second=io.BytesIO();Image.fromarray(np.clip(arr.astype(int)+5,0,255).astype(np.uint8)).save(second,format='PNG')
    page.locator('input[type=file]').set_input_files({'name':'back-fixture.png','mimeType':'image/png','buffer':second.getvalue()})
    page.locator('.investigate-visual-card').nth(1).wait_for()
    checks.append('follow-up photo runs vision again and joins same case')
    page.reload(wait_until='networkidle')
    page.locator('.investigate-visual-card').nth(1).wait_for()
    assert not writes
    checks.append('guest visual history restores without formal business writes')
    page.screenshot(path=str(out/'desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(out/'mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    checks.append('390px mobile has no horizontal document overflow')
    # Formal real API: a fictional account and greenhouse live only in isolated DB.
    a=api.post('/api/auth/register',data={'display_name':'视觉验收','phone':'135'+str(int(time.time())%100000000).zfill(8),'password':'BrowserTest2026'}).json()['data']
    headers={'Authorization':'Bearer '+a['token']}
    gh=api.post('/api/greenhouses',headers=headers,data={'name':'视觉验收棚','code':'VIS-'+str(int(time.time())),'location':'隔离自动化','area_mu':1,'status':'active'}).json()['data']
    formal=browser.new_page(viewport={'width':1440,'height':1000})
    formal.on('pageerror',lambda e:errors.append(str(e)))
    formal.add_init_script('localStorage.setItem("pengzhi_auth_token",'+json.dumps(a['token'])+');localStorage.setItem("pengzhi_auth_user",'+json.dumps(json.dumps(a['user']))+');')
    formal.goto('http://127.0.0.1:5174/platform/investigate?greenhouse_id='+str(gh['id']),wait_until='networkidle')
    formal.locator('input[type=file]').set_input_files({'name':'formal.png','mimeType':'image/png','buffer':blob.getvalue()})
    formal.locator('.investigate-visual-card').wait_for()
    formal.reload(wait_until='networkidle')
    formal.locator('.investigate-visual-card').wait_for()
    checks.append('formal photo, visual result and history persist through real API')
    # Never select the external-call checkbox in browser fixtures: only the
    # separately authorized generated-image probe calls a real model.
    assert formal.get_by_role('checkbox',name='本次允许调用已配置且支持图片的模型（可能计费）').is_enabled()
    checks.append('verified image model enabled; each upload still requires opt-in')
    records=api.get('/api/investigate?greenhouse_id='+str(gh['id']),headers=headers).json()['data']
    record=records[0]
    finished=api.post(f"/api/investigate/{record['id']}/finish",headers=headers,data={'version':record['version'],'note':'浏览器隔离测试归档，不是真实田间案例'}).json()['data']
    formal.reload(wait_until='networkidle')
    formal.get_by_label('核验方法或独立证据',exact=True).fill('浏览器隔离测试夹具的独立标签')
    formal.get_by_label('核验结论',exact=True).fill('仅验证表单和报告生成流程')
    select=formal.get_by_label('最终人工核验原因',exact=True)
    select.focus();select.press('ArrowDown');select.press('Enter')
    select=formal.get_by_label('案例用途（首次确认后固定，验证案例不参与训练）',exact=True)
    formal.get_by_text('经验训练案例',exact=True).click()
    formal.locator('.ant-select-dropdown:visible').get_by_text('保留验证案例',exact=True).click()
    formal.get_by_role('checkbox',name='我已依据人工核验确认上述原因，允许进入经验数据；未勾选则记为仍未明确').check()
    formal.get_by_role('button',name='保存人工核验',exact=True).click()
    formal.get_by_text('混淆矩阵：行是人工核验，列是系统首位候选',exact=True).wait_for()
    report=api.get('/api/investigate/evaluation',headers=headers).json()['data']
    assert report['cases']==1 and not report['field_accuracy_validated']
    assert formal.get_by_role('button',name='训练轻量观察策略').is_disabled()
    checks.append('human holdout form produces real confusion matrix without enabling training')
    formal.set_viewport_size({'width':390,'height':844})
    assert formal.evaluate('document.documentElement.scrollWidth<=innerWidth')
    formal.screenshot(path=str(out/'validation-mobile.png'),full_page=True)
    checks.append('holdout confusion matrix stays inside mobile scroll container')
    assert not errors,errors
    checks.append('no JavaScript runtime errors')
    browser.close()
out.joinpath('browser-results.json').write_text(json.dumps({'checks':checks,'errors':errors,'data':'synthetic pixel fixtures through real algorithms, no API interception'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':len(checks),'errors':errors}))
