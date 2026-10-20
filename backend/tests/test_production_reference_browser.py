"""Opt-in reference-design checks. Every business write uses pytest's temporary database."""
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import pytest
from app.database import SessionLocal
from app.models import FarmTask, Greenhouse
from test_final_product import create_context

pytestmark = pytest.mark.skipif(os.environ.get('PENGZHI_BROWSER_TESTS') != '1', reason='Requires Vite and Edge')
OUT = Path(__file__).resolve().parents[2] / '.run/production-reference'


def test_production_reference_browser(client):
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=20000)
    OUT.mkdir(parents=True, exist_ok=True)
    checks, errors, writes = [], [], []
    gid, bid = create_context(client, 'DESIGN')
    titles = ['开启顶窗通风 30 分钟', '复测东侧区域湿度', '巡检滴灌管路', '补拍异常叶片背面', '记录今日采收', '检查遮阳网状态']
    ids = []
    for title in titles:
        response = client.post('/api/tasks', json={'greenhouse_id':gid,'crop_batch_id':bid,'title':title,'description':'开启顶窗\n保持通风 30 分钟\n补充湿度测量','action_type':'ventilation_check','priority':'medium','created_by':'隔离验收'})
        assert response.status_code == 200, response.text
        ids.append(response.json()['data']['id'])
    with SessionLocal() as db:
        house = db.get(Greenhouse, gid)
        house.name = '一号番茄棚 · 隔离验收'
        house.manager_name = '李农艺师'
        for i, aid in enumerate(ids):
            task = db.get(FarmTask, aid)
            task.status = ['pending','pending','in_progress','pending','completed','completed'][i]
            task.assignee_name = ['现场执行员','张师傅','王师傅','李农艺师','王师傅','现场执行员'][i]
            task.planned_start_at = datetime.now(UTC) + timedelta(minutes=i*30)
            task.due_at = datetime.now(UTC) + timedelta(hours=5)
            task.evidence_snapshot_json = {'zone_name': '东侧区域' if i < 2 else '全棚'}
            if i >= 4: task.completed_at = datetime.now(UTC) - timedelta(days=i-4)
            if i == 0: task.priority = 'urgent'
        db.commit()
    user = client.get('/api/auth/me').json()['data']
    auth = client.headers['Authorization']
    def check(name):
        checks.append(name)
        print('PASS',name,flush=True)
    def forward(route):
        req = route.request; parsed = urlsplit(req.url)
        path = parsed.path + ('?' + parsed.query if parsed.query else '')
        if req.method not in ('GET','OPTIONS'): writes.append((req.method,path))
        response = client.request(req.method,path,content=req.post_data_buffer,headers={
            k:v for k,v in req.headers.items() if k.lower() in ('authorization','content-type','x-simulation-session')})
        route.fulfill(status=response.status_code,body=response.content,content_type=response.headers.get('content-type','application/json'))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        context = browser.new_context(viewport={'width':1586,'height':992},timezone_id='Asia/Shanghai',reduced_motion='reduce')
        context.route('http://127.0.0.1:5173/api/**',forward)
        context.add_init_script('localStorage.setItem("pengzhi_auth_token",'+json.dumps(auth.split(' ',1)[1])+');localStorage.setItem("pengzhi_auth_user",'+json.dumps(json.dumps(user))+');')
        page = context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://127.0.0.1:5173/platform/production?greenhouse_id={gid}')
        expect(page.locator('.farm-design-row')).to_have_count(6)
        expect(page.locator('.farm-current-task>h2')).to_have_text(titles[0])
        check('正式接口渲染六条隔离任务与当前任务')
        assert page.locator('.exact-sider').bounding_box()['width'] == 240
        assert abs(page.locator('.farm-execution-design').bounding_box()['x']-270) < 2
        assert page.locator('.pz-production-design-nav .ant-menu-item-selected').inner_text() == '农事执行'
        assert page.locator('.pz-section-nav').count() == 0
        check('设计图侧栏、子导航与主区起点')
        page.screenshot(path=str(OUT/'production-desktop.png'),full_page=False,animations='disabled')
        page.locator('.farm-design-row').nth(2).click()
        expect(page.locator('.farm-current-task>h2')).to_have_text(titles[2])
        check('点击任务同步右侧内容')
        page.get_by_role('navigation',name='任务状态').get_by_role('button',name='待处理').click()
        expect(page.locator('.farm-design-row')).to_have_count(3)
        page.get_by_role('navigation',name='任务状态').get_by_role('button',name='已完成').click()
        expect(page.locator('.farm-design-row')).to_have_count(2)
        check('任务状态筛选与计数')
        page.get_by_role('navigation',name='任务状态').get_by_role('button',name='全部').click()
        page.get_by_role('textbox',name='搜索任务',exact=True).fill('不存在xyz')
        expect(page.get_by_text('没有符合筛选条件的任务',exact=True)).to_be_visible()
        page.get_by_role('textbox',name='搜索任务',exact=True).fill('滴灌')
        expect(page.locator('.farm-design-row')).to_have_count(1)
        page.get_by_role('textbox',name='搜索任务',exact=True).fill('')
        check('任务搜索与无结果状态')
        page.get_by_role('button',name='筛选任务',exact=True).click()
        box = page.get_by_role('combobox',name='筛选任务优先级')
        box.locator('xpath=ancestor::div[contains(concat(" ",normalize-space(@class)," ")," ant-select ")][1]').locator('.ant-select-selector').click()
        page.locator('.ant-select-dropdown:visible').get_by_text('紧急',exact=True).click()
        expect(page.locator('.farm-design-row')).to_have_count(1)
        page.get_by_role('button',name='筛选任务',exact=True).click()
        check('优先级筛选使用实际数据')
        page.locator('.farm-design-row').first.click()
        page.get_by_role('button',name='排程日历',exact=True).click()
        drawer = page.get_by_role('dialog',name='排程日历',exact=True)
        expect(drawer.locator('.farm-calendar-tasks button').first).to_be_visible()
        drawer.locator('.farm-calendar-tasks button').first.click()
        expect(drawer).not_to_be_visible()
        check('排程日历展示实际任务并可选中')
        page.get_by_role('button',name='新建任务',exact=True).click()
        expect(page.get_by_role('dialog',name='手工创建任务草稿')).to_be_visible()
        page.get_by_role('dialog',name='手工创建任务草稿').get_by_role('button',name='Close',exact=True).click()
        expect(page.get_by_role('dialog',name='手工创建任务草稿')).not_to_be_visible()
        page.locator('.ant-drawer-open .ant-drawer-close').first.click()
        check('新建任务仍打开真实编辑表单')
        page.get_by_role('button',name='开始执行',exact=True).click()
        expect(page.get_by_role('button',name='记录执行反馈',exact=True)).to_be_visible()
        assert client.get(f'/api/tasks/{ids[0]}').json()['data']['status']=='in_progress'
        check('开始执行写入真实隔离任务并刷新状态')
        page.get_by_role('button',name='查看详情',exact=True).click()
        expect(page.get_by_role('dialog').filter(has_text=titles[0]).last).to_be_visible()
        check('任务详情与反馈入口保留')
        # Fresh visit closes nested task drawers and resets local filters.
        page.goto(f'http://127.0.0.1:5173/platform/production?greenhouse_id={gid}')
        expect(page.locator('.farm-design-row')).to_have_count(6)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(700)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(OUT/'production-mobile.png'),full_page=True,animations='disabled')
        check('农事执行手机布局无横向溢出')
        page.set_viewport_size({'width':1586,'height':992})
        client.put('/api/greenhouse-control/state',json={'scenario_id':'humid','mode':'threshold'})
        page.goto(f'http://127.0.0.1:5173/platform/autonomy?greenhouse_id={gid}')
        expect(page.locator('.autonomy-status-bar')).to_contain_text('托管已暂停')
        expect(page.locator('.autonomy-zone-value.center')).to_contain_text('92.0%')
        assert page.locator('.autonomy-zone-value.west').inner_text().endswith('—')
        assert page.locator('.autonomy-zone-value.east').inner_text().endswith('—')
        check('自治全棚读数使用后端，未接入分区不伪造数值')
        page.get_by_role('button',name='启动托管',exact=True).click()
        expect(page.locator('.autonomy-status-bar')).to_contain_text('托管运行中')
        expect(page.locator('.autonomy-zone-value.center')).not_to_contain_text('92.0%',timeout=15000)
        assert client.get('/api/greenhouse-control/state').json()['running']
        check('启动托管驱动真实后端仿真并持续复测')
        expect(page.locator('.autonomy-records li')).to_have_count(6,timeout=18000)
        assert page.locator('.autonomy-trend-card svg path[stroke="#006147"]').count() == 1
        check('循环状态、运行日志与历史曲线更新')
        page.screenshot(path=str(OUT/'autonomy-desktop.png'),full_page=False,animations='disabled')
        page.get_by_role('button',name='暂停托管',exact=True).click()
        expect(page.locator('.autonomy-status-bar')).to_contain_text('托管已暂停')
        assert not client.get('/api/greenhouse-control/state').json()['running']
        check('暂停托管同步后端状态')
        page.get_by_role('button',name='人工接管',exact=True).click()
        expect(page.get_by_role('dialog',name='调控设置与方案比较')).to_be_visible()
        expect(page.get_by_role('dialog',name='调控设置与方案比较').get_by_role('button',name='启动手动控制',exact=False)).to_be_visible()
        assert client.get('/api/greenhouse-control/state').json()['mode']=='manual'
        check('人工接管先停止自动输出再进入手动配置')
        page.get_by_role('button',name='紧急停止',exact=True).click()
        assert client.get('/api/greenhouse-control/state').json()['emergency']
        page.get_by_role('button',name='重置',exact=True).click()
        assert not client.get('/api/greenhouse-control/state').json()['emergency']
        check('原有急停与重置功能保留')
        page.get_by_role('spinbutton',name='实验步数',exact=True).fill('10')
        page.get_by_role('button',name='运行对比实验',exact=True).click()
        expect(page.get_by_text('已运行：seed=42，steps=10。',exact=False)).to_be_visible()
        check('原有策略对比实验可运行')
        page.get_by_role('dialog',name='调控设置与方案比较').locator('.ant-drawer-close').click()
        page.get_by_role('button',name='查看完整运行记录',exact=False).click()
        expect(page.locator('.autonomy-full-records article').first).to_be_visible()
        page.get_by_role('dialog',name='自主运行记录',exact=True).locator('.ant-drawer-close').click()
        check('完整运行记录可查看')
        page.get_by_role('button',name='研究记录',exact=True).click()
        page.wait_for_url('**/research?**')
        assert 'tab=studies' in page.url and f'greenhouse_id={gid}' in page.url
        check('AI研究台入口与大棚上下文保留')
        page.goto(f'http://127.0.0.1:5173/platform/autonomy?greenhouse_id={gid}')
        expect(page.locator('.autonomy-status-bar')).to_be_visible()
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(700)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(OUT/'autonomy-mobile.png'),full_page=True,animations='disabled')
        check('棚智自治手机布局无横向溢出')
        assert page.locator('.pengxiaozhi-dock canvas').count()==1
        check('独立三维棚小智保留')
        assert not errors,errors
        check('无JavaScript运行错误')
        browser.close()
    (OUT/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,'data':'Real FastAPI TestClient and temporary pytest DB; six labeled fixture tasks; no production business writes','write_count':len(writes)},ensure_ascii=False,indent=2),encoding='utf8')
