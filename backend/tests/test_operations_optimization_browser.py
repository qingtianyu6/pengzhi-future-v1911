"""Opt-in UI checks forwarded to pytest's temporary DB, including artificial slow network."""
import json
import os
from pathlib import Path
import time
import re
from urllib.parse import urlsplit, parse_qs

import pytest
from app.database import SessionLocal
from app.models import FarmTask
from app.greenhouse_sim.runtime import manager
from test_task_api import task_context, create_manual  # noqa: F401

pytestmark = pytest.mark.skipif(os.environ.get('PENGZHI_BROWSER_TESTS') != '1', reason='Requires Vite and Edge')
OUT = Path(__file__).resolve().parents[2] / '.run' / 'operations-optimization'


def test_operations_ui_with_isolated_api(client, task_context):
    from playwright.sync_api import sync_playwright, expect
    gid, bid = task_context
    ids = [create_manual(client, gid, bid)['id'] for _ in range(9)]
    with SessionLocal() as db:
        for i, task_id in enumerate(ids):
            task = db.get(FarmTask, task_id)
            task.title = f'隔离分页任务{i}'
            task.status = 'in_progress' if i == 0 else 'pending'
            task.assignee_name = '隔离执行员'
        db.commit()
    user = client.get('/api/auth/me').json()['data']
    token = client.headers['Authorization'].split(' ',1)[1]
    errors, queries, checks = [], [], []
    delay, fail = [False], [False]
    OUT.mkdir(parents=True, exist_ok=True)
    def forward(route):
        req = route.request
        parsed = urlsplit(req.url)
        path = parsed.path + ('?' + parsed.query if parsed.query else '')
        if parsed.path == '/api/tasks' and req.method == 'GET':
            queries.append(parse_qs(parsed.query))
        if delay[0] and parsed.path == '/api/greenhouse-control/state' and req.method == 'GET':
            time.sleep(3.1)
            if fail[0]:
                fail[0] = False
                route.fulfill(status=503, json={'message':'隔离慢网测试：暂时不可用'})
                return
        response = client.request(req.method, path, content=req.post_data_buffer, headers={k:v for k,v in req.headers.items() if k.lower() in ('authorization','content-type','x-simulation-session')})
        route.fulfill(status=response.status_code, body=response.content, content_type=response.headers.get('content-type','application/json'))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        context = browser.new_context(viewport={'width':1586,'height':992}, timezone_id='Asia/Shanghai', reduced_motion='reduce')
        context.route('http://127.0.0.1:5173/api/**', forward)
        context.add_init_script('localStorage.setItem("pengzhi_auth_token",'+json.dumps(token)+');localStorage.setItem("pengzhi_auth_user",'+json.dumps(json.dumps(user))+');')
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f'http://127.0.0.1:5173/platform/production?greenhouse_id={gid}')
        expect(page.locator('.farm-design-row')).to_have_count(6)
        assert queries[-1]['page_size'] == ['6'] and not any(q.get('page') == ['2'] for q in queries)
        page.get_by_title('2', exact=True).click()
        expect(page.locator('.farm-design-row')).to_have_count(3)
        assert queries[-1]['page'] == ['2']
        checks.append('服务端按需分页：首屏6条，翻页3条')
        page.get_by_role('textbox',name='搜索任务',exact=True).fill('任务0')
        expect(page.locator('.farm-design-row')).to_have_count(1)
        expect(page.locator('.farm-current-task>h2')).to_have_text('隔离分页任务0')
        assert queries[-1]['q'] == ['任务0']
        page.get_by_role('textbox',name='搜索任务',exact=True).fill('没有匹配')
        expect(page.locator('.farm-design-row')).to_have_count(0)
        expect(page.locator('.farm-current-task>h2')).to_have_count(0)
        checks.append('搜索由后端处理，无结果时清空右侧任务')
        page.get_by_role('textbox',name='搜索任务',exact=True).fill('任务0')
        expect(page.get_by_role('button',name='记录执行反馈',exact=True)).to_be_visible()
        page.get_by_role('button',name='记录执行反馈',exact=True).click()
        feedback = page.get_by_role('dialog',name='追加执行反馈',exact=True)
        expect(feedback).to_be_visible()
        assert page.get_by_role('dialog').count() == 1
        feedback.get_by_label('执行记录').fill('隔离测试：记录现场观察，不推断因果。')
        feedback.get_by_role('button',name='确 定',exact=True).click()
        expect(feedback).not_to_be_visible()
        assert len(client.get(f'/api/tasks/{ids[0]}').json()['data']['feedbacks']) == 1
        page.get_by_role('dialog').locator('.ant-drawer-close').click()
        checks.append('反馈直接打开单层表单，写入隔离数据库并保留详情')
        page.get_by_role('button',name='新建任务',exact=True).click()
        create = page.get_by_role('dialog',name='手工创建任务草稿',exact=True)
        expect(create).to_be_visible()
        assert page.get_by_role('dialog').count() == 1
        create.get_by_label('标题',exact=True).fill('隔离新建任务')
        create.get_by_label('任务说明',exact=True).fill('只写入本次测试临时数据库')
        create.get_by_role('button',name='确 定',exact=True).click()
        expect(create).not_to_be_visible()
        expect(page.get_by_role('dialog')).to_contain_text('隔离新建任务')
        page.get_by_role('dialog').locator('.ant-drawer-close').click()
        checks.append('新建任务单层创建，完成后直接查看草稿')
        page.screenshot(path=str(OUT/'after-create.png'))
        page.get_by_role('button',name='全部任务与证据链',exact=True).click()
        expect(page.get_by_role('dialog',name='农事任务中心',exact=True)).to_be_visible()
        page.get_by_role('dialog',name='农事任务中心',exact=True).locator('.ant-drawer-close').click()
        checks.append('高级任务中心保留')

        page.set_viewport_size({'width':390,'height':844})
        page.goto(f'http://127.0.0.1:5173/platform/research?greenhouse_id={gid}')
        empty = page.locator('.ag-table-scroll').first
        expect(empty.locator('.ant-empty')).to_be_visible()
        dims = empty.evaluate("e=>({visible:e.clientWidth,table:e.querySelector('.ant-table-container').getBoundingClientRect().width,cell:e.querySelector('.ant-table-placeholder td').getBoundingClientRect().width})")
        assert dims['table'] <= dims['visible']+1 and dims['cell'] <= dims['visible']+1, dims
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        collapse = page.get_by_role('button',name='收起棚小智',exact=True)
        expect(collapse).to_be_visible()
        box = collapse.bounding_box()
        assert box['width'] >= 44 and box['height'] >= 44
        page.screenshot(path=str(OUT/'research-mobile.png'), full_page=True)
        checks.append('手机空表格宽度与可见区域一致，角色收起按钮44px')

        client.put('/api/greenhouse-control/state',json={'environment':{'air_humidity':85},'target':{'air_humidity':65}})
        runtime = manager.runtimes[f"user:{user['organization_id']}:{user['id']}"]
        with runtime.lock:
            runtime.history.extend({**runtime.env.model_dump(),'time':t,'air_humidity':h} for t,h in [(1000,80),(1002,78),(1010,75)])
            runtime.simulation_time = 1010
            runtime.env.air_humidity = 75
        delay[0] = True
        page.set_viewport_size({'width':1586,'height':992})
        page.goto(f'http://127.0.0.1:5173/platform/autonomy?greenhouse_id={gid}')
        expect(page.locator('.autonomy-status-bar')).to_be_visible(timeout=15000)
        expect(page.locator('.autonomy-data-status')).to_contain_text('最近更新')
        expect(page.locator('.autonomy-data-status')).to_contain_text('不随顶部大棚切换')
        expect(page.locator('.autonomy-trend-card svg')).to_contain_text('1000 秒')
        path = page.locator('.autonomy-trend-card svg path[stroke="#006147"]').get_attribute('d')
        xs = [float(x) for x in re.findall(r'[ML]([\d.]+),',path)]
        assert abs((xs[1]-xs[0])/(xs[2]-xs[0]) - .2) < .001
        checks.append('历史窗口以真实起始秒数标注，不等间隔采样按时间绘制')
        page.wait_for_timeout(300)
        reading = page.locator('.autonomy-current-reading').bounding_box()
        dock = page.locator('.pengxiaozhi-dock').bounding_box()
        if reading['y'] < dock['y']+dock['height'] and reading['y']+reading['height'] > dock['y']:
            assert reading['x']+reading['width'] <= dock['x']
        checks.append('曲线当前读数在角色重叠时为其留出空间，角色位置保持手动')
        page.wait_for_function("performance.getEntriesByType('resource').filter(e=>e.name.includes('/greenhouse-control/state')).length>=2",timeout=20000)
        timings = page.evaluate("performance.getEntriesByType('resource').filter(e=>e.name.includes('/greenhouse-control/state')).map(e=>({start:e.startTime,end:e.responseEnd}))")
        assert timings[1]['start'] >= timings[0]['end'] + 1800, timings
        checks.append('3.1秒慢网仍能更新；请求完成后才安排下一次轮询')
        fail[0] = True
        expect(page.locator('.autonomy-data-status')).to_contain_text('数据可能已过期',timeout=20000)
        expect(page.locator('.autonomy-data-status')).not_to_contain_text('数据可能已过期',timeout=22000)
        checks.append('失败标识过期状态，退避后恢复')
        page.screenshot(path=str(OUT/'autonomy-desktop.png'))
        assert not errors, errors
        browser.close()
    (OUT/'results.json').write_text(json.dumps({'checks':checks,'errors':errors,'slow_network_timings':timings,'database':'pytest temporary database only'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False))
