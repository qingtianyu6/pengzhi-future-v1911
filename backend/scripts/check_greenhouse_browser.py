"""Live browser workflow against the isolated demo server; requires Microsoft Edge or Playwright Chromium."""
from pathlib import Path
import json
import os
import time
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parents[2]
out=root/'.run'/'greenhouse'/'browser';out.mkdir(parents=True,exist_ok=True)
url=os.getenv('GREENHOUSE_BROWSER_URL','http://127.0.0.1:5180')
errors=[];api_failures=[];checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1080},device_scale_factor=1)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('response',lambda r:api_failures.append(f'{r.status} {r.url}') if '/greenhouse-' in r.url and r.status>=400 else None)
    page.goto(url+'/platform/autonomy?mode=guest')
    expect(page.get_by_role('heading',name='AI 温室模拟调控')).to_be_visible(timeout=60000)
    expect(page.get_by_text('虚拟设备模式',exact=True)).to_be_visible()
    expect(page.get_by_text('正常环境',exact=True)).to_be_visible(timeout=30000)
    page.screenshot(path=str(out/'initial.png'),full_page=True)
    checks.append('navigation and backend-loaded state')
    page.locator('div.ant-select[aria-label=模拟场景]').click()
    page.get_by_text('多指标异常',exact=True).last.click()
    expect(page.get_by_label('空气温度输入',exact=True)).to_have_value('37.0')
    page.get_by_label('空气温度输入',exact=True).fill('39')
    page.locator('div.ant-select[aria-label=控制模式]').click()
    page.get_by_text('预测优化 · 候选动作搜索',exact=True).last.click()
    page.get_by_role('button',name='启动自动调控').click()
    expect(page.get_by_text('运行中',exact=True)).to_be_visible(timeout=30000)
    expect(page.get_by_text('虚拟 GPIO 已确认',exact=True).first).to_be_visible()
    expect(page.locator('.simulation-reason')).to_contain_text('预测优化：枚举')
    page.wait_for_function("document.querySelector('.simulation-trend canvas') !== null")
    # Read through the same session rather than another anonymous runtime.
    state=page.evaluate("""async () => (await fetch('/api/greenhouse-demo/state',{headers:{'X-Simulation-Session':sessionStorage.getItem('greenhouse_sim_session')}})).json()""")
    assert state['source']=='simulation' and state['device']['mode']=='mock' and not state['device']['physical_verified']
    assert state['environment']['air_temperature']>38
    assert len(state['decision']['candidates'])>=1
    time.sleep(2.5)
    page.evaluate('window.scrollTo(0,0)')
    page.wait_for_timeout(250)
    page.screenshot(path=str(out/'desktop.png'),full_page=True)
    checks.append('custom input, predictive candidate computation, protocol ACK, dynamic curve')
    page.get_by_role('button',name='暂停',exact=True).click()
    expect(page.get_by_text('已暂停',exact=True)).to_be_visible(timeout=10000)
    page.get_by_role('button',name='模拟断连',exact=True).click()
    expect(page.get_by_role('alert').filter(has_text='虚拟串口已断开')).to_be_visible(timeout=10000)
    page.get_by_role('button',name='恢复连接',exact=True).click()
    expect(page.get_by_text('协议已连接',exact=True)).to_be_visible(timeout=10000)
    checks.append('pause, disconnect injection, reconnect')
    page.get_by_label('自定义场景名称',exact=True).fill('浏览器自定义场景')
    page.get_by_role('button',name='保存自定义场景').click()
    expect(page.get_by_text('浏览器自定义场景',exact=True).first).to_be_visible(timeout=10000)
    checks.append('named custom scenario persisted and recalled')
    page.get_by_role('button',name='运行对比实验').click()
    expect(page.get_by_text('已运行：seed=42，steps=120。',exact=False)).to_be_visible(timeout=30000)
    checks.append('repeatable comparison metrics rendered')
    page.get_by_role('button',name='紧急停止',exact=True).click()
    expect(page.get_by_text('急停锁定',exact=True)).to_be_visible(timeout=10000)
    expect(page.get_by_role('button',name='启动自动调控')).to_be_disabled()
    page.get_by_role('button',name='重置',exact=True).click()
    expect(page.get_by_label('空气温度输入',exact=True)).to_have_value('26.0')
    checks.append('emergency latch and reset')
    page.locator('div.ant-select[aria-label=控制模式]').click()
    page.get_by_text('手动接管',exact=True).last.click()
    page.get_by_label('指示灯手动开关',exact=True).click()
    page.get_by_role('button',name='启动手动控制').click()
    expect(page.get_by_text('运行中',exact=True)).to_be_visible(timeout=10000)
    page.get_by_role('button',name='暂停',exact=True).click()
    checks.append('manual command through backend')
    page.set_viewport_size({'width':390,'height':844})
    page.evaluate('window.scrollTo(0,0)')
    page.wait_for_timeout(250)
    page.screenshot(path=str(out/'mobile.png'),full_page=True)
    overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 2')
    assert not overflow,'Mobile viewport overflow'
    checks.append('mobile width without page overflow')
    # Read-only regression: original guest workspace remains reachable.
    page.goto(url+'/platform/environment')
    page.wait_for_timeout(1500)
    assert page.locator('body').inner_text().find('监测')>=0
    checks.append('existing environment workspace regression')
    browser.close()
report={'checks':checks,'page_errors':errors,'api_failures':api_failures,'hardware':'HARDWARE_PENDING'}
(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert not errors,errors
assert not api_failures,api_failures
print(json.dumps(report,ensure_ascii=False,indent=2))
