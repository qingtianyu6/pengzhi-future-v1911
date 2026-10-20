"""Real guest-route layout checks. No API interception or production writes."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[2]
out=root/'.run/ui-refresh';out.mkdir(parents=True,exist_ok=True)
routes=['','environment','production','3d','investigate','diagnosis','disease-time-machine','research','knowledge','news','forum','data','ai-quality']
results=[];errors=[]
parser=argparse.ArgumentParser()
parser.add_argument('--skip-workbench',action='store_true')
args=parser.parse_args()
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.set_default_timeout(45000)
    page.on('pageerror',lambda error:errors.append(str(error)))
    for width in (() if args.skip_workbench else (1440,390)):
        page.set_viewport_size({'width':width,'height':1000 if width==1440 else 844})
        for route in routes:
            url='http://127.0.0.1:5173/platform'+('/'+route if route else '')+'?mode=guest&greenhouse_id=101'
            try:
                page.goto(url,wait_until='domcontentloaded')
                if route=='3d': page.locator('.wb-route-body canvas').first.wait_for()
                else: page.locator('.wb-route-body h1').first.wait_for()
                page.wait_for_timeout(450)
                assert not page.locator('.route-loading').count(),'route stuck in loading'
                overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                if overflow:
                    offenders=page.locator('body *').evaluate_all('(nodes)=>nodes.filter(e=>e.getBoundingClientRect().right>innerWidth+2&&getComputedStyle(e).position!=="fixed").slice(0,8).map(e=>e.className)')
                    raise AssertionError('horizontal overflow '+str(offenders))
                assert page.locator('.pz-ui').count()==1
                results.append({'route':route or 'overview','width':width,'passed':True})
            except Exception as error:
                results.append({'route':route or 'overview','width':width,'passed':False,'error':str(error)[:600]})
            page.screenshot(path=str(out/f'{route or "overview"}-{width}.png'),full_page=True)
            out.joinpath('workbench-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    # Real functional navigation, including keyboard shortcut and context retention.
    page.set_viewport_size({'width':1440,'height':1000})
    page.goto('http://127.0.0.1:5173/platform?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
    page.locator('.wb-route-body h1').first.wait_for()
    page.keyboard.press('Control+k')
    page.get_by_label('搜索平台功能',exact=True).fill('探因')
    page.get_by_role('button',name='棚智探因 AI看图、主动观察与动态证据排查',exact=False).click()
    page.wait_for_url('**/platform/investigate?**')
    assert 'greenhouse_id=101' in page.url and 'mode=guest' in page.url
    results.append({'interaction':'search-navigation-keeps-greenhouse','passed':True})
    page.get_by_role('button',name='打开功能导航').click()
    page.get_by_label('搜索平台功能',exact=True).fill('no-such-function-928374')
    page.get_by_text('没有找到相关功能，试试“环境”“研究”或“论坛”。',exact=True).wait_for()
    page.keyboard.press('Escape')
    results.append({'interaction':'navigation-empty-state-and-escape','passed':True})
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='展开侧边栏').click()
    page.locator('.exact-side-menu').get_by_text('监测与预警',exact=True).click()
    page.wait_for_url('**/platform/environment?**')
    page.get_by_role('button',name='展开侧边栏').wait_for(state='visible')
    results.append({'interaction':'mobile-navigation-closes-after-selection','passed':True})
    page.set_viewport_size({'width':1920,'height':1080})
    page.locator('.wb-assistant-rail').wait_for()
    assert page.locator('.mascot-three-view').count()>0
    results.append({'interaction':'ultrawide-assistant-and-original-3d-character','passed':True})
    # Public and auth pages inherit brand tokens but keep their content and flows.
    for width in (1440,390):
        page.set_viewport_size({'width':width,'height':1000 if width==1440 else 844})
        for route in ('home','introduction','features','highlights','scenarios','login','register'):
            try:
                page.goto('http://127.0.0.1:5173/'+route,wait_until='domcontentloaded')
                if route in ('login','register'):page.locator('.auth-form-heading').wait_for()
                elif route=='home':page.locator('.hero-copy').wait_for()
                else:page.locator('h1').first.wait_for()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                results.append({'route':route,'width':width,'passed':True})
            except Exception as error:
                results.append({'route':route,'width':width,'passed':False,'error':str(error)[:600]})
            if route in ('home','login'):page.screenshot(path=str(out/f'{route}-{width}.png'),full_page=True)
    browser.close()
report={'checks':results,'javascript_errors':errors,'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results)}
out.joinpath('browser-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
assert report['failed']==0 and not errors
