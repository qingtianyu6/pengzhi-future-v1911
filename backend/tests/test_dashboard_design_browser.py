"""Empty, stale and failed dashboard states against pytest's isolated database."""
from datetime import UTC,datetime,timedelta
from pathlib import Path
from urllib.parse import urlsplit
import json,os
import pytest
from test_final_product import create_context,readings

pytestmark=pytest.mark.skipif(os.environ.get('PENGZHI_BROWSER_TESTS')!='1',reason='Requires local Vite and Edge')


def test_dashboard_real_empty_stale_and_retry(client,monkeypatch):
    from playwright.sync_api import sync_playwright,expect
    from app.services import chinese_news
    monkeypatch.setattr(chinese_news,'public_headlines',lambda:{'items':[],'photo_stories':[],'sources':[],'fetched_at':datetime.now(UTC).isoformat()})
    user=client.get('/api/auth/me').json()['data']
    token=client.headers['Authorization'].split(' ',1)[1]
    state={'fail':False};checks=[];errors=[]
    def forward(route):
        req=route.request;p=urlsplit(req.url);path=p.path+('?' + p.query if p.query else '')
        if state['fail'] and p.path=='/api/dashboard/summary':
            route.fulfill(status=503,json={'message':'隔离验收：暂时无法读取采样'});return
        r=client.request(req.method,path,content=req.post_data_buffer,headers={k:v for k,v in req.headers.items() if k.lower() in ('authorization','content-type')})
        route.fulfill(status=r.status_code,body=r.content,content_type=r.headers.get('content-type','application/json'))
    with sync_playwright() as p:
        b=p.chromium.launch(channel='msedge')
        c=b.new_context(viewport={'width':1491,'height':1055})
        c.route('http://127.0.0.1:5173/api/**',forward)
        c.add_init_script('localStorage.setItem("pengzhi_auth_token",'+json.dumps(token)+');localStorage.setItem("pengzhi_auth_user",'+json.dumps(json.dumps(user))+');')
        page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:5173/platform')
        expect(page.get_by_text('还没有可用的大棚工作区',exact=True)).to_be_visible()
        checks.append('无大棚显示接入入口，不生成读数')
        gid,_=create_context(client,'DESIGN-UI')
        url=f'http://127.0.0.1:5173/platform?greenhouse_id={gid}'
        page.goto(url)
        expect(page.locator('.dd-metric-value strong')).to_have_count(5)
        assert page.locator('.dd-metric-value strong').all_inner_texts()==['—']*5
        expect(page.locator('.dd-status-risk strong')).to_have_text('待评估')
        expect(page.get_by_role('button',name='连接环境数据',exact=False)).to_be_visible()
        assert not page.locator('.dd-demo-tag').count()
        checks.append('有大棚无采样：五项缺测、风险待评估，无游客标识')
        reading=readings(gid,'sensor',1)[0]
        reading['recorded_at']=(datetime.now(UTC)-timedelta(days=3)).isoformat()
        result=client.post('/api/sensors/batch',json={'items':[reading]})
        assert result.status_code==200,result.text
        page.reload()
        expect(page.locator('.dd-status-data strong')).to_have_text('数据待同步')
        expect(page.locator('.dd-focus-status')).to_have_text('采样数据待同步')
        expect(page.locator('.dd-focus')).to_contain_text('超过2小时')
        checks.append('过期采样明确显示待同步，不伪装实时')
        state['fail']=True;page.reload()
        expect(page.get_by_text('生产工作台数据加载失败',exact=True)).to_be_visible()
        expect(page.get_by_text('隔离验收：暂时无法读取采样',exact=True)).to_be_visible()
        state['fail']=False
        page.get_by_role('button',name='重试读取工作台',exact=True).click()
        expect(page.locator('.dd-metric-value strong')).to_have_count(5)
        expect(page.get_by_text('生产工作台数据加载失败',exact=True)).to_have_count(0)
        checks.append('服务失败可见、实际重试恢复，不保留假数据')
        b.close()
    assert not errors,errors
    out=Path(__file__).resolve().parents[2]/'.run/dashboard-design';out.mkdir(exist_ok=True)
    (out/'data-states.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'database':'pytest temporary only'},ensure_ascii=False,indent=2),encoding='utf-8')
