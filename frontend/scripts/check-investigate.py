"""Focused real-browser checks; backend 8001 and Vite 5174 use an isolated test DB."""
from pathlib import Path
import json
import time
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[2]
out = root / '.run' / 'investigate'
out.mkdir(parents=True, exist_ok=True)
checks, errors = [], []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1700, 'height': 1000}, timezone_id='Asia/Shanghai')
    page.set_default_timeout(20000)
    page.on('pageerror', lambda e: errors.append(str(e)))
    writes = []
    page.on('request', lambda r: writes.append(r.url) if '/api/investigate' in r.url and '/investigate-demo/' not in r.url and r.method == 'POST' else None)
    page.goto('http://127.0.0.1:5174/platform/investigate?mode=guest&greenhouse_id=101', wait_until='networkidle')
    page.get_by_role('heading', name='棚智探因', exact=True).wait_for()
    page.get_by_role('button', name='开始调查', exact=True).click()
    page.get_by_text('局部潮湿或通风差异', exact=True).first.wait_for()
    checks.append('multiple candidates and concrete observation')
    action_select = page.get_by_label('本次检查', exact=True).first
    action_select.evaluate('(e) => e.scrollIntoView({block:"center"})')
    action_select.click()
    page.locator('.ant-select-dropdown:visible').get_by_text('拍摄异常叶片背面', exact=True).click()
    page.get_by_label('叶背蛛网/活动小点', exact=True).click()
    page.locator('.ant-select-dropdown:visible').get_by_text('是 / 看到了', exact=True).click()
    page.get_by_label('叶背霉层', exact=True).click()
    page.locator('.ant-select-dropdown:visible').get_by_text('否 / 已检查未见', exact=True).click()
    page.get_by_label('观察说明', exact=True).fill('叶背可见细蛛网与活动小点，已检查未见霉层。')
    page.get_by_role('button', name='提交证据并重新分析', exact=True).click()
    page.get_by_text('第1轮 · 优先调查：叶螨等刺吸危害待鉴别', exact=True).wait_for()
    checks.append('new evidence changes leading explanation')
    assert not writes
    checks.append('guest performs real rule calculation without business writes')
    page.reload(wait_until='networkidle')
    page.get_by_text('第1轮 · 优先调查：叶螨等刺吸危害待鉴别', exact=True).wait_for()
    checks.append('guest investigation survives reload')
    page.screenshot(path=str(out/'desktop.png'), full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(out/'mobile.png'), full_page=True)
    if page.evaluate('document.documentElement.scrollWidth > innerWidth'):
        print(page.evaluate('Array.from(document.querySelectorAll(".investigate-page *")).filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>[e.tagName,e.className,e.getBoundingClientRect().width]).slice(0,15)'),flush=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    checks.append('390px no horizontal document overflow')
    page.screenshot(path=str(out/'mobile.png'), full_page=True)
    # Authenticated create/persist against the actual isolated API.
    api = p.request.new_context(base_url='http://127.0.0.1:8001')
    a = api.post('/api/auth/register',data={'display_name':'探因浏览器验收','phone':'136'+str(int(time.time())%100000000).zfill(8),'password':'BrowserTest2026'}).json()['data']
    headers={'Authorization':'Bearer '+a['token']}
    response=api.post('/api/greenhouses',headers=headers,data={'name':'探因测试棚','code':'INV-'+str(int(time.time())),'location':'隔离浏览器验收','area_mu':1,'status':'active'})
    assert response.status == 201, response.text()
    gh=response.json()['data']
    formal=browser.new_page(viewport={'width':1440,'height':1000})
    formal.on('pageerror',lambda e:errors.append(str(e)))
    formal.add_init_script('localStorage.setItem("pengzhi_auth_token",'+json.dumps(a['token'])+');localStorage.setItem("pengzhi_auth_user",'+json.dumps(json.dumps(a['user']))+');')
    formal.goto('http://127.0.0.1:5174/platform/investigate?greenhouse_id='+str(gh['id']),wait_until='networkidle')
    formal.get_by_role('button',name='开始调查',exact=True).click()
    formal.get_by_text('局部潮湿或通风差异',exact=True).first.wait_for()
    formal.reload(wait_until='networkidle')
    formal.get_by_text('局部潮湿或通风差异',exact=True).first.wait_for()
    checks.append('formal investigation persists via actual API')
    assert not errors,errors
    checks.append('no JavaScript runtime errors')
    browser.close()
out.joinpath('browser-results.json').write_text(json.dumps({'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':len(checks),'errors':errors}))
