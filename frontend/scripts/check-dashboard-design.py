"""Actual guest UI and data checks for the approved production dashboard design."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect

root=Path(__file__).resolve().parents[2];out=root/'.run/dashboard-design';out.mkdir(exist_ok=True)
base='http://127.0.0.1:5173';url=base+'/platform?mode=guest&greenhouse_id=101'
checks=[];errors=[]
with sync_playwright() as p:
 b=p.chromium.launch(channel='msedge')
 c=b.new_context(viewport={'width':1491,'height':1055},reduced_motion='reduce',timezone_id='Asia/Shanghai')
 page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
 def ready():
  expect(page.locator('.dd-metric-value strong')).to_have_count(5,timeout=30000)
  page.evaluate('document.fonts.ready')
 for width in (1491,1680,1440,1280,1024,768,390,320):
  page.set_viewport_size({'width':width,'height':1055 if width>760 else 844})
  page.goto(url,wait_until='domcontentloaded');ready()
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),width
  for s in ['.dd-chart','.dd-todo','.dd-metrics','.dd-chart-tools']:
   assert page.locator(s).evaluate('e=>e.scrollWidth<=e.clientWidth+1'),(width,s)
  expect(page.get_by_role('heading',name='生产工作台',exact=True)).to_be_visible()
  checks.append({'check':'真实工作台无横向溢出，核心内容完整','width':width})
  if width in (1491,390):page.screenshot(path=str(out/f'overview-{width}.png'),full_page=True)
 page.set_viewport_size({'width':1491,'height':1055});page.goto(url);ready()
 data=page.evaluate("""async()=>{const {getDashboardSummary}=await import('/src/api/dashboardApi.ts');const summary=await getDashboardSummary(101);return {latest:summary.latest_environment,tasks:summary.task_summary.recent_tasks,warning:summary.warning_summary.open_warning_count}}""")
 readings=page.locator('.dd-metric-value strong').all_inner_texts()
 assert readings==[f"{data['latest']['temperature']:.1f}",f"{data['latest']['air_humidity']:.0f}",f"{data['latest']['soil_moisture']:.0f}",f"{data['latest']['light_intensity']:.1f}",f"{data['latest']['co2_concentration']:.0f}"],readings
 checks.append({'check':'五项读数直接对应当前游客数据接口','values':readings})
 targets={'.dd-hero':(264,164,1207,198),'.dd-environment':(264,372,1207,164),'.dd-work-grid':(264,546,1207,254),'.dd-status-ribbon':(264,810,1207,84),'.dd-activity':(264,904,1207,113)}
 for selector,target in targets.items():
  r=page.locator(selector).bounding_box()
  assert all(abs(r[k]-v)<=4 for k,v in zip(['x','y','width','height'],target)),(selector,r,target)
 checks.append({'check':'1491×1055参考视口主分区位置、宽高校准','tolerance_px':4})
 for label,key in [('温度','temperature'),('湿度','air_humidity'),('土壤湿度','soil_moisture'),('全部','all')]:
  page.locator('.dd-chart-filters').get_by_role('button',name=label,exact=True).click()
  expect(page.locator('.dd-chart-filters').get_by_role('button',name=label,exact=True)).to_have_attribute('aria-pressed','true')
  selected=page.evaluate("""async()=>{const charts=await import('/node_modules/.vite/deps/echarts_core.js');const chart=charts.getInstanceByDom(document.querySelector('.exact-environment-chart'));return chart.getOption().legend[0].selected}""")
  assert selected=={'温度 (℃)':key in ('all','temperature'),'湿度 (%)':key in ('all','air_humidity'),'土壤湿度 (%)':key in ('all','soil_moisture')},selected
 checks.append({'check':'四个指标筛选真实改变图表系列选择'})
 original_date=page.locator('.dd-date-switch b').inner_text()
 page.get_by_role('button',name='上一天',exact=True).click()
 expect(page.locator('.dd-date-switch b')).not_to_have_text(original_date)
 expect(page.get_by_role('button',name='下一天',exact=True)).to_be_enabled()
 page.get_by_role('button',name='下一天',exact=True).click()
 expect(page.locator('.dd-date-switch b')).to_have_text(original_date)
 expect(page.get_by_role('button',name='下一天',exact=True)).to_be_disabled()
 assert page.locator('.dd-metric-value strong').all_inner_texts()==readings
 checks.append({'check':'历史日期前后切换保留当前采样读数'})
 page.get_by_role('button',name='记录观察',exact=True).click()
 expect(page.get_by_role('dialog',name='记录作物观察',exact=True)).to_be_visible(timeout=30000)
 assert 'greenhouse_id=101' in page.url
 assert 'observe=1' not in page.url
 page.locator('.ant-modal-close:visible').click();page.reload()
 expect(page.get_by_role('button',name='记录作物观察')).to_be_visible()
 expect(page.get_by_role('dialog',name='记录作物观察')).to_have_count(0)
 checks.append({'check':'记录观察直达正确大棚表单，刷新不重复弹出'})
 page.goto(url);ready();page.locator('.dd-task').first.click()
 assert '/platform/production?' in page.url and 'task_id=' in page.url and 'greenhouse_id=101' in page.url
 checks.append({'check':'任务行保留大棚和任务详情深链'})
 page.goto(url);ready();page.get_by_role('button',name='查看预警与建议',exact=False).click()
 assert '/platform/environment?' in page.url and 'tab=alerts' in page.url
 checks.append({'check':'预警按钮打开当前大棚预警页'})
 page.goto(url);ready();page.get_by_role('button',name='走进三维大棚',exact=False).click()
 assert '/platform/3d?' in page.url and 'greenhouse_id=101' in page.url
 checks.append({'check':'三维入口独立且保留当前大棚'})
 page.goto(url);ready();page.get_by_role('button',name='模型说明',exact=True).click()
 expect(page.get_by_role('dialog')).to_be_visible()
 checks.append({'check':'模型说明仍可打开'})
 b.close()
assert not errors,errors
(out/'results.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'scope':'Guest UI only, no production writes'},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS',len(checks),'dashboard checks')
