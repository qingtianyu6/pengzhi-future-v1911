"""Exercises real endpoints and rendered controls, with formal data only in an isolated DB."""
import json,os,subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[2];out=root/'.run/community-completion'
checks=[];errors=[]
def passed(name):checks.append(name);print('PASS '+name,flush=True)
with sync_playwright() as p:
    api=p.request.new_context(base_url='http://127.0.0.1:8001')
    a=api.post('/api/auth/register',data={'display_name':'社区验收','phone':'136'+str(int(time.time())%100000000).zfill(8),'password':'BrowserTest2026'}).json()['data']
    headers={'Authorization':'Bearer '+a['token']}
    gh=api.post('/api/greenhouses',headers=headers,data={'name':'隔离验收棚','code':'COMM-'+str(int(time.time())),'area_mu':1,'location':'自动化测试','status':'active'}).json()['data']
    gid=gh['id']
    # Deliberately labeled fixture records. Never connect this seed to a production DB.
    database=(out/'browser-test.db').resolve()
    assert database.parent==out.resolve()
    env={**os.environ,'DATABASE_URL':'sqlite:///'+database.as_posix()}
    seed='''from app.database import SessionLocal
from app.models.community import NewsSource,NewsArticle
from app.models import User
from sqlalchemy import select
with SessionLocal() as db:
 u=db.scalar(select(User).where(User.phone==PHONE))
 s=NewsSource(organization_id=u.organization_id,name='隔离验收来源（非新闻）',url='https://example.org/fixture.xml',kind='rss',enabled=False,permission_note='仅测试数据，不是真实来源授权');db.add(s);db.flush()
 db.add(NewsArticle(organization_id=u.organization_id,source_id=s.id,title='隔离验收：番茄观察流程',canonical_url='https://example.org/fixture',summary='本条仅用于隔离数据库浏览器测试，不是真实农业新闻。',tags=['tomato'],status='metadata_only',analysis={}));db.commit()
'''
    seed=seed.replace('PHONE',repr(a['user']['phone']))
    subprocess.run([str(root/'backend/.venv/Scripts/python.exe'),'-c',seed],cwd=root/'backend',env=env,check=True,capture_output=True)
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000})
    # Reuse the running frontend; forward real test-browser API requests to the isolated backend.
    def isolated_api(route):
        route.continue_(url=route.request.url.replace('http://127.0.0.1:5173/api/','http://127.0.0.1:8001/api/',1))
    page.route('http://127.0.0.1:5173/api/**',isolated_api)
    page.set_default_timeout(25000);page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script('localStorage.setItem("pengzhi_auth_token",'+json.dumps(a['token'])+');localStorage.setItem("pengzhi_auth_user",'+json.dumps(json.dumps(a['user']))+');')
    def visit(route):
        page.goto(f'http://127.0.0.1:5173/platform/{route}?greenhouse_id={gid}',wait_until='domcontentloaded');page.locator('.community-hero h1').wait_for()
    def select(label,text):
        field=page.get_by_role('combobox',name=label,exact=True);field.focus();field.press('ArrowDown')
        page.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).click()
    visit('knowledge')
    page.locator('.community-source-result').first.wait_for();passed('public references browse with retained sources')
    page.get_by_label('农业知识问题').fill('unknownxyz72634');page.get_by_role('button',name='检索知识',exact=True).click()
    page.get_by_text('没有可展示的检索结果；证据不足时不会回退到无关资料',exact=True).wait_for();passed('irrelevant query remains empty')
    page.get_by_role('button',name='返回参考目录',exact=True).click();page.locator('.community-source-result').first.wait_for()
    page.locator('.community-source-result').first.get_by_role('button',name='带着这条资料去论坛提问').click();page.wait_for_url('**/platform/forum?**')
    assert f'greenhouse_id={gid}' in page.url;passed('knowledge to forum retains greenhouse and topic')
    page.get_by_role('button',name='发布帖子',exact=False).click()
    assert page.get_by_label('帖子标题',exact=True).input_value()
    page.get_by_label('正文（支持 Markdown）',exact=True).fill('隔离浏览器验收的实际发布内容，记录了番茄观察问题。')
    page.get_by_role('button',name='确认发布',exact=True).click();page.get_by_role('button',name='编辑帖子').wait_for();passed('prefilled forum topic is only published after submit')
    page.get_by_role('button',name='← 返回论坛',exact=True).click()
    select('解答状态','待解答的求助');page.wait_for_timeout(400)
    assert page.locator('.community-title-button').count()==1;passed('formal unanswered filter returns actual posted question')
    select('解答状态','已采纳答案');page.get_by_text('还没有讨论，发布第一个种植问题吧',exact=True).wait_for();passed('accepted filter excludes unanswered discussion')
    visit('news');page.get_by_role('heading',name='隔离验收：番茄观察流程',exact=True).wait_for()
    select('资讯来源','隔离验收来源（非新闻）');select('阅读状态','未读资讯')
    page.get_by_role('button',name='阅读摘要',exact=True).click();page.get_by_role('dialog').wait_for()
    page.get_by_text('本条仅用于隔离数据库浏览器测试，不是真实农业新闻。',exact=True).last.wait_for();passed('article summary dialog and source-specific unread filter')
    page.get_by_role('dialog').get_by_role('button',name='Close',exact=True).click()
    select('阅读状态','已读资讯');page.get_by_role('heading',name='隔离验收：番茄观察流程',exact=True).wait_for()
    page.get_by_role('button',name='本页全部已读').click();passed('batch read works on already-read page')
    page.get_by_role('tab',name='关注与推送',exact=True).click();assert 'tab=preferences' in page.url
    page.reload(wait_until='domcontentloaded');page.get_by_role('tab',name='关注与推送',exact=True).wait_for();passed('news tab survives refresh')
    hour=page.get_by_role('spinbutton',name='每天推送时间（北京时间整点）',exact=True)
    hour.fill('9')
    with page.expect_response(lambda r:'/api/community/news/preferences' in r.url and r.request.method=='GET'):
        page.get_by_role('button',name='刷新页面',exact=True).click()
    assert hour.input_value()=='9'
    passed('refresh preserves unsaved notification preferences')
    for route in ('knowledge','forum','news'):
        page.set_viewport_size({'width':390,'height':844});visit(route)
        page.wait_for_timeout(500);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(out/f'{route}-mobile.png'),full_page=True);passed(route+' mobile layout')
    guest=browser.new_page(viewport={'width':1440,'height':1000});guest.on('pageerror',lambda e:errors.append(str(e)))
    guest.route('http://127.0.0.1:5173/api/**',isolated_api)
    writes=[];guest.on('request',lambda r:writes.append(r.url) if '/api/community/' in r.url and r.method!='GET' else None)
    guest.goto('http://127.0.0.1:5173/platform/knowledge?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
    guest.locator('.community-source-result').first.wait_for();assert guest.get_by_role('button',name='导入农业文档').is_disabled()
    assert not writes;passed('guest uses real public reference API without formal writes')
    browser.close()
report={'passed':len(checks),'checks':checks,'javascript_errors':errors,'data':'formal fixtures only in .run/community-completion/browser-test.db'}
(out/'browser-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False));assert not errors
