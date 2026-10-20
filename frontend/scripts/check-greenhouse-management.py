"""Actual guest workflows; no network mocks, production writes or paid model calls."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[2]
out=root/'.run/greenhouse-redesign';out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
def passed(name):
 checks.append(name);print(name,flush=True)
with sync_playwright() as p:
 b=p.chromium.launch()
 page=b.new_page(viewport={'width':1586,'height':1000})
 page.set_default_timeout(20000)
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:5173/platform/data?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
 page.locator('.gh-inventory-item').first.wait_for()
 assert page.locator('.gh-hero-metrics dd').all_text_contents()==['2','2','2']
 assert page.locator('.wb-assistant-rail').count()==0
 assert page.locator('.pz-section-nav').count()==0
 assert page.locator('.exact-side-menu .ant-menu-item').count()==7
 passed('one management page, actual guest totals, full-width hero and independent 3D navigation')
 row=page.locator('.gh-inventory-item').first
 row.get_by_role('button',name='管理接入').click()
 assert page.locator('.gh-access-strip').count()==0
 row.get_by_role('button',name='管理接入').click()
 page.locator('.gh-access-strip').wait_for()
 passed('inline connection details collapse and reopen')
 row.get_by_role('button',name='配置数据').click()
 drawer=page.locator('.ant-drawer-open .gh-connection-drawer')
 drawer.get_by_role('button',name='选择文件导入',exact=True).click()
 dialog=page.get_by_role('dialog').last
 assert '游客体验番茄棚' in dialog.inner_text()
 assert page.locator('input[type=file]').count()>0
 page.get_by_role('dialog').last.get_by_label('Close',exact=True).click()
 drawer.locator('.ant-drawer-close').click()
 passed('file import opens in place with matching greenhouse selected')
 row.get_by_role('button',name='查看大棚',exact=True).click()
 page.get_by_text('当前种植批次',exact=True).wait_for()
 page.locator('.ant-drawer-open .ant-drawer-close').click()
 passed('greenhouse detail and existing planting-batch view retained')
 page.locator('.gh-create-button').click()
 dialog=page.get_by_role('dialog')
 dialog.get_by_label('大棚名称',exact=True).fill('本轮管理测试棚')
 dialog.get_by_label('位置',exact=True).fill('示例测试区')
 dialog.get_by_label('面积（亩）',exact=True).fill('1.25')
 dialog.get_by_role('button',name='确 定',exact=True).click()
 page.get_by_role('heading',name='本轮管理测试棚',exact=True).wait_for()
 assert page.locator('.gh-hero-metrics dd').all_text_contents()==['3','2','2']
 passed('create greenhouse updates list and global summary without a route change')
 created=page.locator('.gh-inventory-item').filter(has=page.get_by_role('heading',name='本轮管理测试棚',exact=True))
 created.get_by_role('button',name='绑定设备',exact=True).click()
 drawer=page.locator('.ant-drawer-open .gh-connection-drawer')
 drawer.get_by_label('设备编号',exact=True).fill('BROWSER-NODE-01')
 drawer.get_by_label('设备名称',exact=True).fill('东侧温湿度传感器')
 drawer.get_by_role('button',name='保存设备登记',exact=True).click()
 drawer.get_by_text('东侧温湿度传感器',exact=True).wait_for()
 assert '待上报' in drawer.inner_text()
 assert page.locator('.gh-hero-metrics dd').all_text_contents()==['3','2','2']
 drawer.locator('.ant-drawer-close').click()
 created.get_by_role('button',name='绑定设备',exact=True).click()
 drawer.get_by_text('东侧温湿度传感器',exact=True).wait_for()
 drawer.locator('.ant-drawer-close').click()
 passed('binding is saved in guest session, does not fake online status, and drawer reopens')
 created.get_by_role('button',name='接入数据',exact=True).click()
 page.locator('.ant-drawer-open .gh-connection-drawer').get_by_role('button',name='选择文件导入',exact=True).wait_for()
 page.locator('.ant-drawer-open .gh-connection-drawer .ant-drawer-close').click()
 passed('unconnected greenhouse data action opens the correct panel directly')
 page.get_by_placeholder('搜索大棚',exact=True).fill('本轮管理测试棚')
 page.get_by_placeholder('搜索大棚',exact=True).press('Enter')
 page.wait_for_function('document.querySelectorAll(".gh-inventory-item").length===1')
 assert page.locator('.gh-hero-metrics dd').all_text_contents()==['3','2','2']
 passed('search filters list while hero remains the global total')
 page.get_by_placeholder('搜索大棚',exact=True).fill('不存在的大棚')
 page.get_by_placeholder('搜索大棚',exact=True).press('Enter')
 page.get_by_text('没有符合条件的大棚，请调整筛选',exact=True).wait_for()
 page.get_by_placeholder('搜索大棚',exact=True).fill('')
 page.get_by_placeholder('搜索大棚',exact=True).press('Enter')
 page.wait_for_function('document.querySelectorAll(".gh-inventory-item").length===3')
 passed('empty search has recovery and does not replace actual statistics')
 for number in [2,3]:
  page.locator('.gh-create-button').click()
  dialog=page.get_by_role('dialog')
  dialog.get_by_label('大棚名称',exact=True).fill(f'分页测试棚{number}')
  dialog.get_by_label('位置',exact=True).fill('分页测试区')
  dialog.get_by_label('面积（亩）',exact=True).fill('1')
  dialog.get_by_role('button',name='确 定',exact=True).click()
  page.wait_for_function(f'document.querySelector(".gh-hero-metrics dd").textContent==="{number+2}"')
 page.locator('.ant-pagination-item-2').click()
 page.get_by_role('heading',name='分页测试棚3',exact=True).wait_for()
 assert page.locator('.gh-inventory-item').count()==1
 assert page.locator('.gh-hero-metrics dd').all_text_contents()==['5','2','2']
 page.locator('.ant-pagination-item-1').click()
 page.wait_for_function('document.querySelectorAll(".gh-inventory-item").length===4')
 passed('pagination displays four records per page with consistent global totals')
 page.locator('.exact-side-menu').get_by_text('三维大棚',exact=True).click()
 page.wait_for_url('**/platform/3d?**')
 page.locator('.greenhouse-3d-page canvas').first.wait_for()
 assert 'greenhouse_id=101' in page.url
 assert '三维大棚' in page.locator('.exact-side-menu .ant-menu-item-selected').inner_text()
 page.locator('.exact-side-menu').get_by_text('大棚管理',exact=True).click()
 page.locator('.gh-management-hero').wait_for()
 passed('independent 3D menu renders the existing scene and returns with context preserved')
 row=page.locator('.gh-inventory-item').first
 row.get_by_role('button',name='管理设备').click()
 drawer=page.locator('.ant-drawer-open .gh-connection-drawer')
 drawer.get_by_label('设备编号',exact=True).fill('PERSIST-NODE')
 drawer.get_by_label('设备名称',exact=True).fill('会话保留测试设备')
 drawer.get_by_role('button',name='保存设备登记',exact=True).click()
 drawer.get_by_text('会话保留测试设备',exact=True).wait_for()
 drawer.locator('.ant-drawer-close').click()
 page.reload(wait_until='domcontentloaded')
 page.locator('.gh-access-strip').get_by_role('button',name='管理设备').click()
 page.locator('.ant-drawer-open .gh-connection-drawer').get_by_text('会话保留测试设备',exact=True).wait_for()
 page.locator('.ant-drawer-open .gh-connection-drawer .ant-drawer-close').click()
 passed('device registration survives refresh in the browser session')
 page.screenshot(path=str(out/'desktop-final.png'),full_page=True)
 for width in [1280,768,390]:
  page.set_viewport_size({'width':width,'height':844})
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),width
  page.screenshot(path=str(out/f'layout-{width}.png'),full_page=True)
 passed('1280px, tablet 768px and mobile 390px have no horizontal page overflow')
 row=page.locator('.gh-inventory-item').first
 row.get_by_role('button',name='查看大棚',exact=True).click()
 page.get_by_text('当前种植批次',exact=True).wait_for()
 page.locator('.ant-drawer-open .ant-drawer-close').click()
 passed('mobile detail interaction remains usable')
 assert not errors,errors
 passed('zero JavaScript runtime errors')
 b.close()
(out/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'javascript_errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
