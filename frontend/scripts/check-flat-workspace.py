"""Real route and responsive checks for the shared unboxed workspace."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[2]
out=root/'.run/flat-ui'
out.mkdir(parents=True,exist_ok=True)
checks=[]
errors=[]
with sync_playwright() as p:
 browser=p.chromium.launch()
 page=browser.new_page(viewport={'width':1440,'height':1000})
 page.on('pageerror',lambda e:errors.append(str(e)))
 for width in [1440,390]:
  page.set_viewport_size({'width':width,'height':1000 if width==1440 else 844})
  for route in ['', '/data','/environment','/investigate','/diagnosis','/production','/autonomy','/research','/knowledge','/news','/forum']:
   page.goto('http://127.0.0.1:5173/platform'+route+'?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
   page.locator('.pz-workspace-page h1, .pz-workspace-page h2').first.wait_for()
   page.wait_for_timeout(400)
   assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),(width,route,'overflow')
   if not route:
    assert page.locator('.exact-metric-card').count()==5
    page.screenshot(path=str(out/f'dashboard-{width}.png'),full_page=True)
    page.get_by_role('button',name='现场异常排查',exact=True).click()
    page.wait_for_url('**/investigate?**')
    page.locator('.investigate-hero h1').wait_for()
    checks.append(f'{width}: dashboard inspection link')
   if route in ['/knowledge','/news','/forum','/investigate']:
    cards=page.locator('.pz-workspace-page .ant-card')
    for i in range(cards.count()):
     assert cards.nth(i).evaluate('(e)=>getComputedStyle(e).boxShadow')=='none'
   if route in ['/news','/knowledge','/forum','/investigate']:
    page.screenshot(path=str(out/f'{route[1:]}-{width}.png'),full_page=True)
   checks.append(f'{width}: {route or "/"} route, responsive layout')
   print(checks[-1],flush=True)
 assert not errors,errors
 browser.close()
(out/'checks.json').write_text(json.dumps({'checks':checks,'javascript_errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'{len(checks)} checks passed; {len(errors)} JavaScript errors',flush=True)
