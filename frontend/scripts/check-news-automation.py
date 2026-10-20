"""Real browser controls against an isolated backend; never enables paid automation."""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright

out=Path(__file__).resolve().parents[2]/'.run/news-automation'
checks=[];errors=[]
def passed(name):checks.append(name);print('PASS '+name,flush=True)
with sync_playwright() as p:
    api=p.request.new_context(base_url='http://127.0.0.1:8001')
    a=api.post('/api/auth/register',data={'display_name':'农讯浏览器验收','phone':'134'+str(int(time.time())%100000000).zfill(8),'password':'NewsBrowser2026'}).json()['data']
    headers={'Authorization':'Bearer '+a['token']}
    gh=api.post('/api/greenhouses',headers=headers,data={'name':'农讯隔离验收棚','code':'NEWS-'+str(int(time.time())),'area_mu':1,'location':'测试','status':'active'}).json()['data']
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000})
    def forward(route):route.continue_(url=route.request.url.replace('http://127.0.0.1:5173/api/','http://127.0.0.1:8001/api/',1))
    page.route('http://127.0.0.1:5173/api/**',forward)
    page.add_init_script('localStorage.setItem("pengzhi_auth_token",'+json.dumps(a['token'])+');localStorage.setItem("pengzhi_auth_user",'+json.dumps(json.dumps(a['user']))+');')
    page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(25000)
    page.goto('http://127.0.0.1:5173/platform/news?greenhouse_id='+str(gh['id']),wait_until='domcontentloaded')
    page.get_by_role('button',name='配置自动简报',exact=True).wait_for()
    assert page.get_by_role('button',name='立即运行一次',exact=True).is_disabled()
    passed('unconfigured pipeline cannot run')
    page.get_by_role('button',name='配置自动简报',exact=True).click()
    dialog=page.get_by_role('dialog');dialog.wait_for()
    assert dialog.get_by_role('checkbox',name='农业农村部 · 部级动态',exact=True).is_checked()
    assert not dialog.get_by_role('checkbox',name='ScienceDaily 农业与食品研究资讯',exact=True).is_checked()
    assert dialog.get_by_role('checkbox',name='农业农村部 · 全国信息联播',exact=True).is_checked()
    passed('verified source catalog and configuration form render')
    page.get_by_role('button',name='保存并启用所选配置',exact=True).click()
    dialog.get_by_text('请确认公开订阅用途',exact=True).wait_for()
    passed('source-use confirmation validation')
    # Save paused and AI off, preventing any external model calls or periodic collection.
    dialog.get_by_role('switch',name='自动采集与每日简报',exact=True).click()
    dialog.get_by_role('checkbox',name='确认所选公开来源用于站内标题或摘要阅读，保留出处，不批量转载全文或图片',exact=True).check()
    with page.expect_response(lambda r:'/news/automation/setup' in r.url and r.request.method=='POST') as response:
        page.get_by_role('button',name='保存并启用所选配置',exact=True).click()
    assert response.value.status==200
    dialog.wait_for(state='hidden')
    settings=api.get('/api/community/news/automation',headers=headers).json()['data']
    assert settings['enabled'] is False and settings['use_ai'] is False and settings['calls_reserved_today']==0
    assert len(api.get('/api/community/news/sources',headers=headers).json()['data'])==3
    passed('real API persists source setup, paused status and zero model calls')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
    page.screenshot(path=str(out/'automation-mobile.png'),full_page=True)
    passed('390px mobile layout has no horizontal overflow')
    guest=browser.new_page(viewport={'width':1440,'height':1000});guest.route('http://127.0.0.1:5173/api/**',forward)
    guest.on('pageerror',lambda e:errors.append(str(e)))
    guest.goto('http://127.0.0.1:5173/platform/news?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
    guest.get_by_role('link',name='登录设置自动推送',exact=True).wait_for()
    assert guest.get_by_role('button',name='立即运行一次',exact=True).count()==0
    passed('guest sees source preview and login entry without formal write controls')
    assert not errors,errors
    passed('no JavaScript runtime errors')
    browser.close()
(out/'browser-result.json').write_text(json.dumps({'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
