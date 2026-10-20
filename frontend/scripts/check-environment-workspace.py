import json
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[2];out=root/'.run/environment-redesign';out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];writes=[]
def passed(name):checks.append(name);print(name,flush=True)
with sync_playwright() as p:
 b=p.chromium.launch();page=b.new_page(viewport={'width':1586,'height':1000});page.set_default_timeout(20000)
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:writes.append(r.url) if r.method=='POST' and any(x in r.url for x in ['/api/warnings','/api/tasks','/api/v1/ai/chat']) else None)
 def open_page(gid=101,suffix=''):
  page.goto(f'http://127.0.0.1:5173/platform/environment?greenhouse_id={gid}&mode=guest{suffix}',wait_until='domcontentloaded')
  page.locator('.env-alert-row').first.wait_for()
  page.locator('.env-response-detail h3').wait_for()
 def no_overflow():assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 def close_drawer():page.locator('.ant-drawer-open .ant-drawer-close').click()
 def confirm(note=None):
  dialog=page.get_by_role('dialog')
  if note:dialog.get_by_label('现场处理说明',exact=True).fill(note)
  dialog.locator('.ant-modal-footer .ant-btn-primary').click()
  page.locator('.ant-modal:visible').wait_for(state='hidden')
 open_page()
 assert page.locator('.env-metric-strip > button').count()==5
 assert page.locator('.env-chart-region').get_attribute('data-forecast')=='6'
 assert page.locator('.env-chart-region').get_attribute('data-interval')=='true'
 assert page.locator('.wb-assistant-rail').count()==0
 no_overflow();passed('unified page: five metrics, actual history and six future points with provided bounds')
 page.get_by_role('button',name='土壤湿度',exact=False).first.click()
 assert page.locator('.env-chart-region').get_attribute('data-forecast')=='0'
 assert page.locator('.env-chart-region').get_attribute('data-interval')=='false'
 assert '当前指标暂无可用' in page.locator('.env-chart-note').inner_text()
 passed('unsupported soil forecast remains empty; no borrowed curve or uncertainty band')
 page.locator('.env-metric-strip button').nth(1).click()
 assert page.locator('.env-chart-region').get_attribute('aria-label').startswith('空气湿度')
 assert page.locator('.env-chart-region').get_attribute('data-forecast')=='6'
 page.locator('.env-metric-strip button').first.click();passed('metric selection switches the real curve and units')
 page.get_by_role('button',name='预测设置',exact=True).click()
 field=page.get_by_role('combobox',name='预测时长',exact=True);field.focus();field.press('ArrowDown');field.press('ArrowUp');field.press('ArrowUp');field.press('Enter')
 close_drawer()
 page.wait_for_function('document.querySelector(".env-chart-region").dataset.forecast==="1"')
 passed('prediction horizon changes to one hour through settings')
 page.get_by_role('button',name='数据明细',exact=True).click()
 page.locator('.ant-drawer-open .ant-table-row').first.wait_for()
 close_drawer()
 with page.expect_download() as downloaded:page.get_by_role('button',name='导出环境数据',exact=True).click()
 assert downloaded.value.suggested_filename=='environment-101.csv';passed('original readings table and CSV export are functional')
 page.get_by_role('button',name='预警依据',exact=True).click();page.locator('.env-evidence-json').wait_for();close_drawer();passed('selected warning retains source evidence and rule version')
 page.get_by_role('button',name='开始处理',exact=True).click();confirm('已检查通风口，安排补测异常区域温湿度')
 page.wait_for_function('document.querySelector(".env-alert-tabs button[aria-pressed=true]").textContent.includes("处理中")')
 page.get_by_text('现场确认：已检查通风口，安排补测异常区域温湿度',exact=True).wait_for()
 assert page.locator('.env-warning-count').inner_text().startswith('0');passed('acknowledgement moves warning to processing and updates actual counts and note')
 page.reload(wait_until='domcontentloaded')
 page.locator('.env-alert-tabs').wait_for()
 page.locator('.env-alert-tabs button').nth(1).click()
 page.get_by_text('现场确认：已检查通风口，安排补测异常区域温湿度',exact=True).wait_for();passed('processing state and explanation survive refresh in isolated guest session')
 page.get_by_role('button',name='记录复查结果',exact=True).click();confirm('已现场复测并确认湿度恢复，后续继续观察')
 page.wait_for_function('document.querySelector(".env-alert-tabs button[aria-pressed=true]").textContent.includes("已恢复")')
 page.get_by_text('复查记录：已现场复测并确认湿度恢复，后续继续观察',exact=True).wait_for()
 assert page.locator('.env-handling-progress .is-done').count()==3
 passed('review outcome moves warning to recovered and retains the review record')
 open_page(102)
 page.get_by_role('button',name='开始处理',exact=True).wait_for();passed('warning state is isolated between greenhouse sessions')
 page.get_by_role('button',name='创建农事任务',exact=True).click();confirm()
 page.get_by_role('button',name='查看处理任务',exact=True).wait_for()
 page.reload(wait_until='domcontentloaded');page.get_by_role('button',name='查看处理任务',exact=True).wait_for();passed('warning creates a linked task without route change and restores it after refresh')
 page.get_by_role('button',name='处置与复测记录',exact=True).click()
 page.locator('.ant-drawer-open').get_by_text('处置',exact=False).first.wait_for();close_drawer();passed('original intervention and follow-up records remain accessible')
 for width in [1586,1280,768,390]:
  page.set_viewport_size({'width':width,'height':1000 if width>1000 else 844});no_overflow()
  page.screenshot(path=str(out/f'page-{width}.png'),full_page=True)
 passed('desktop, compact desktop, tablet and mobile have no horizontal overflow')
 page.locator('.env-metric-strip button').nth(3).click()
 assert page.locator('.env-chart-region').get_attribute('data-forecast')=='0';passed('mobile metric switching remains functional')
 page.get_by_role('button',name='忽略',exact=True).click();confirm('已人工核实为示例数据，记录忽略原因')
 page.get_by_text('忽略记录：已人工核实为示例数据，记录忽略原因',exact=True).wait_for()
 assert page.locator('.env-handling-progress').count()==0
 passed('ignored warnings retain their reason and do not display an active treatment workflow')
 page.reload(wait_until='domcontentloaded');page.locator('.env-alert-tabs button').nth(3).click()
 page.get_by_text('忽略记录：已人工核实为示例数据，记录忽略原因',exact=True).wait_for()
 passed('ignored status survives refresh without reopening a treatment workflow')
 assert not errors,errors
 assert not writes,writes
 passed('zero JavaScript runtime errors, formal warning/task writes and paid model chat calls')
 b.close()
(out/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'javascript_errors':errors,'formal_writes':writes},ensure_ascii=False,indent=2),encoding='utf-8')
