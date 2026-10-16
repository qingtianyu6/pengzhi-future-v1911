from pathlib import Path
from playwright.sync_api import sync_playwright,expect
BASE=Path(__file__).resolve().parent
with sync_playwright() as p:
 browser=p.chromium.launch()
 for width,height in [(1440,1000),(390,844)]:
  page=browser.new_page(viewport={'width':width,'height':height})
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto((BASE/'方案阅读版.html').as_uri())
  expect(page.get_by_role('heading',name='棚智未来 · AI值守与协同运营',exact=True)).to_be_visible()
  assert page.locator('article h2').count()==16
  for name in ['环境异常','设备与数据','农事跟进','生产日报']:
   tab=page.get_by_role('tab',name=name,exact=True)
   tab.click()
   expect(tab).to_have_attribute('aria-selected','true')
   assert page.locator('.step').count()==6
  page.get_by_role('tab',name='环境异常',exact=True).click()
  page.get_by_role('tab',name='环境异常',exact=True).press('ArrowRight')
  expect(page.get_by_role('tab',name='设备与数据',exact=True)).to_have_attribute('aria-selected','true')
  page.get_by_role('tab',name='环境异常',exact=True).click()
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  assert not errors,errors
  page.screenshot(path=str(BASE/('方案预览_'+str(width)+'.png')))
  print('PASS',width,'layout, 16 sections, 4 scenarios, keyboard navigation',flush=True)
  page.close()
 browser.close()

