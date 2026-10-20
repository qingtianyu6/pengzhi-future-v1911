"""Browser UI backed by the real FastAPI TestClient and pytest's temporary database.
Only the external public-news provider is a labeled fixture; never touches production DB.
"""
from datetime import datetime,UTC,timedelta
from pathlib import Path
import json
import os
import pytest
from time import perf_counter
from urllib.parse import urlsplit
playwright_api=pytest.importorskip('playwright.sync_api')
sync_playwright=playwright_api.sync_playwright
expect=playwright_api.expect
pytestmark=pytest.mark.skipif(os.environ.get('PENGZHI_BROWSER_TESTS')!='1',reason='Opt-in browser acceptance requires the Vite service')
from app.database import SessionLocal
from app.models.community import NewsArticle,NewsSource,NewsAutomation
from app.services import chinese_news

OUT=Path(__file__).resolve().parents[2]/'.run/news-reference'

def test_news_editorial_browser(client,monkeypatch):
    expect.set_options(timeout=20000)
    OUT.mkdir(parents=True,exist_ok=True);checks=[];errors=[];calls=[]
    def check(name,ok=True):
        assert ok,name
        checks.append(name);print('PASS',name,flush=True)
    titles=['【隔离测试】把田间变化，看得更清楚','【隔离测试】智慧温室与环境监测的新变化','【隔离测试】甜瓜栽培与水肥授粉管理参考','【隔离测试】农业政策与技术推广通知','【隔离测试】番茄病虫防治观察要点']
    tags=[['tomato','technology'],['tomato','technology'],['muskmelon','cultivation'],['policy'],['tomato','disease']]
    public={'items':[{'title':t,'url':f'https://example.org/editorial-ui/{i}','source':'隔离测试栏目（非新闻）','published_at':f'2026-10-{19-i:02}'} for i,t in enumerate(titles)],'sources':[{'status':'ok'}],'fetched_at':datetime.now(UTC).isoformat()}
    monkeypatch.setattr(chinese_news,'public_headlines',lambda:public)
    user=client.get('/api/auth/me').json()['data']
    with SessionLocal() as db:
        source=NewsSource(organization_id=user['organization_id'],name='隔离测试来源（非新闻）',url='https://example.org/ui-fixture.xml',kind='rss',enabled=False,permission_note='临时数据库测试，不是真实新闻来源');db.add(source);db.flush()
        db.add(NewsAutomation(organization_id=user['organization_id'],enabled=False,use_ai=False))
        for i,title in enumerate(titles):
            db.add(NewsArticle(organization_id=user['organization_id'],source_id=source.id,title=title,canonical_url=f'https://example.org/editorial-ui/{i}',summary='隔离数据库验收摘要，仅用于验证网页阅读与收藏，不是真实农业资讯。',tags=tags[i],published_at=datetime(2026,10,19-i),collected_at=datetime.now(UTC)+timedelta(seconds=i),status='metadata_only',analysis={'method':'metadata_classification'}))
        db.commit()
    token=client.headers['Authorization'].split(' ',1)[1]
    def forward(route):
        req=route.request;parsed=urlsplit(req.url);path=parsed.path+('?' + parsed.query if parsed.query else '')
        calls.append((req.method,path))
        headers={k:v for k,v in req.headers.items() if k.lower() in ('authorization','content-type')}
        started=perf_counter()
        response=client.request(req.method,path,content=req.post_data_buffer,headers=headers)
        if req.method!='GET': print('API WRITE',req.method,path,response.status_code,round(perf_counter()-started,2),flush=True)
        if response.status_code>=400: print('API ERROR',req.method,path,response.status_code,response.text[:400],flush=True)
        route.fulfill(status=response.status_code,body=response.content,headers={'content-type':response.headers.get('content-type','application/json')})
    def choose(page,label,text,container=None):
        box=(container or page).get_by_role('combobox',name=label,exact=True)
        box.locator('xpath=ancestor::div[contains(concat(" ",normalize-space(@class)," ")," ant-select ")][1]').locator('.ant-select-selector').click()
        page.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).last.click()
    with sync_playwright() as p:
        installed=sorted((Path.home()/'AppData/Local/ms-playwright').glob('chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe'))
        browser=p.chromium.launch(**({'executable_path':str(installed[0])} if installed else {}));context=browser.new_context(viewport={'width':1600,'height':1000},timezone_id='Asia/Shanghai',reduced_motion='reduce')
        context.route('http://127.0.0.1:5173/api/**',forward)
        context.add_init_script('localStorage.setItem("pengzhi_auth_token",'+json.dumps(token)+');localStorage.setItem("pengzhi_auth_user",'+json.dumps(json.dumps(user))+');')
        page=context.new_page();page.set_default_timeout(30000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda msg:print('CONSOLE ERROR',msg.text,flush=True) if msg.type=='error' else None)
        page.goto('http://127.0.0.1:5173/platform/news')
        page.locator('.news-page').wait_for(timeout=60000)
        page.wait_for_timeout(1200)
        expect(page.locator('.news-editorial-row')).to_have_count(4)
        check('真实临时数据库渲染头条与四条资讯',titles[0] in page.locator('.news-feature-copy').inner_text())
        geometry=page.evaluate('''()=>{let rect=s=>{let r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}};return {sidebar:rect('.exact-sider'),lead:rect('.news-lead'),photo:rect('.news-feature-photo'),quick:rect('.news-quick'),title:getComputedStyle(document.querySelector('.news-masthead h1')).fontSize}}''')
        check('设计图侧栏与主区起点',abs(geometry['sidebar']['width']-240)<1 and abs(geometry['lead']['x']-296)<3)
        check('头条图片高度与大标题字号',abs(geometry['photo']['height']-310)<1 and geometry['title']=='60px')
        check('今日速览三条',page.locator('.news-quick>div>button').count()==3)
        check('主页面仅保留两个入口',page.locator('.news-main-navigation>nav>button').count()==2)
        page.locator('.news-editorial-row').first.locator('.news-row-copy h2 button').click()
        dialog=page.get_by_role('dialog',name=titles[1]);expect(dialog).to_be_visible();check('真实摘要阅读', '隔离数据库验收摘要' in dialog.inner_text())
        dialog.get_by_role('button',name='收藏资讯',exact=True).click();expect(dialog.get_by_role('button',name='取消收藏',exact=True)).to_be_visible();check('阅读框收藏更新')
        dialog.get_by_role('button',name='Close',exact=True).click()
        page.get_by_role('button',name='我的收藏与关注',exact=True).click();expect(page.locator('.news-editorial-row')).to_have_count(1);check('真实账户收藏查询')
        page.get_by_role('button',name='管理关注',exact=True).click();drawer=page.get_by_role('dialog',name='日报与订阅管理');expect(drawer).to_be_visible()
        choose(page,'关注作物','甜瓜',drawer);expect(drawer.locator('.ant-select-selection-item').filter(has_text='甜瓜')).to_be_visible();drawer.locator('button[type=submit]').filter(has_text='保存关注设置').click()
        expect(page.get_by_text('日报偏好已保存',exact=True)).to_be_visible();pref=client.get('/api/community/news/preferences').json()['data'];print('SAVED PREFERENCE',pref,flush=True);assert pref['crops']==['muskmelon'],pref;check('关注偏好保存到真实API')
        page.locator('.ant-drawer-close:visible').click()
        page.get_by_role('button',name='关注动态',exact=True).click();expect(page.locator('.news-editorial-row')).to_have_count(1)
        check('关注动态按实际作物筛选','甜瓜' in page.locator('.news-editorial-row').inner_text())
        page.get_by_role('button',name='今日快讯',exact=True).click();expect(page.locator('.news-editorial-row')).to_have_count(4)
        page.get_by_role('button',name='农业政策',exact=True).click();expect(page.locator('.news-feature-copy h2')).to_contain_text('政策');check('主题真实API过滤')
        page.get_by_role('button',name='全部',exact=True).click();expect(page.locator('.news-editorial-row')).to_have_count(4)
        page.get_by_role('textbox',name='搜索农业资讯',exact=True).fill('不存在xyz49276');page.get_by_role('textbox',name='搜索农业资讯',exact=True).press('Enter');expect(page.locator('.news-empty')).to_be_visible();check('搜索空状态')
        page.get_by_role('button',name='清除筛选',exact=True).first.click();expect(page.locator('.news-editorial-row')).to_have_count(4)
        page.locator('.news-filter-tools summary').click();choose(page,'资讯排序','最近采集');expect(page.locator('.news-feature-copy h2')).to_contain_text('病虫防治');check('按真实采集时间排序')
        page.locator('.news-filter-tools summary').click()
        page.get_by_role('button',name='阅读今日简报').click();expect(page.get_by_role('dialog',name='日报与订阅管理')).to_be_visible();check('简报入口保留')
        page.get_by_role('tab',name='来源与运行',exact=True).click();expect(page.get_by_role('button',name='添加资讯来源',exact=True)).to_be_visible();check('来源与运行管理保留')
        page.get_by_role('tab',name='自动简报',exact=True).click();expect(page.get_by_role('button',name='配置自动简报',exact=True)).to_be_visible();check('自动简报配置入口保留')
        page.locator('.ant-drawer-close:visible').click()
        check('未授权付费模型调用为零',client.get('/api/community/news/automation').json()['data']['calls_reserved_today']==0)
        page.locator('.news-filter-tools summary').click();choose(page,'资讯排序','最新发布');page.locator('.news-filter-tools summary').click()
        page.locator('.pengxiaozhi-dock canvas').wait_for(timeout=60000);page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(500);page.screenshot(path=str(OUT/'desktop-test-data.png'),full_page=False,animations='disabled',timeout=20000)
        check('桌面无横向溢出',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.set_viewport_size({'width':390,'height':844});page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(400);page.screenshot(path=str(OUT/'mobile-test-data.png'),full_page=True,animations='disabled',timeout=20000);check('手机无横向溢出',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        check('独立三维棚小智保留',page.locator('.pengxiaozhi-dock').evaluate('(e)=>getComputedStyle(e).position==="fixed"&&!e.classList.contains("is-compact")'))
        guest=browser.new_context(viewport={'width':1600,'height':1000});guest.route('http://127.0.0.1:5173/api/**',forward);g=guest.new_page();g.on('pageerror',lambda e:errors.append(str(e)))
        baseline=len(calls);g.goto('http://127.0.0.1:5173/platform/news?mode=guest&greenhouse_id=101');expect(g.locator('.news-editorial-row')).to_have_count(4)
        g.locator('.news-row-actions button[aria-pressed]').first.click();g.get_by_role('button',name='我的收藏与关注',exact=True).click();expect(g.locator('.news-editorial-row')).to_have_count(1);check('公开标题可在浏览器收藏')
        g.reload();expect(g.locator('.news-editorial-row')).to_have_count(1);check('公开收藏会话恢复')
        g.locator('.news-read-action').click();expect(g.get_by_role('dialog').get_by_text('栏目仅提供标题和原文链接，未生成文章摘要。',exact=True)).to_be_visible();check('仅标题来源不伪造摘要')
        g.get_by_role('dialog').get_by_role('button',name='Close',exact=True).click()
        check('游客无正式业务写入',not any(method not in ('GET','OPTIONS') and path.startswith('/api/community/') for method,path in calls[baseline:]))
        public['items']=[];public['sources']=[{'status':'failed'}]
        g.get_by_role('button',name='今日快讯',exact=True).click();g.get_by_role('button',name='刷新资讯',exact=True).first.click();expect(g.locator('.news-quick-empty')).to_contain_text('暂不可用');expect(g.locator('.news-editorial-row')).to_have_count(0);check('外部来源故障不填充假新闻')
        check('无JavaScript运行错误',not errors)
        (OUT/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'geometry':geometry,'errors':errors,'data':'FastAPI TestClient + temporary DB; public external provider uses labeled fixtures'},ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()
