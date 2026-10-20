"""Live WebGL identity/movement checks. No model calls or API interception."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parents[2]
out=root/'.run/mascot-refinement'
out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch()
    for width,height in [(1440,1000),(390,844)]:
        context=browser.new_context(viewport={'width':width,'height':height})
        context.add_init_script("sessionStorage.setItem('pengzhi_assistant_welcomed','1')")
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:5173/platform?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
        dock=page.locator('.pengxiaozhi-dock');view=dock.locator('.mascot-three-view')
        expect(view).to_have_attribute('data-ready','true',timeout=45000)
        assert view.locator('canvas').evaluate('(c)=>!c.getContext("webgl2").isContextLost()')
        checks.append(f'live WebGL model {width}')
        expect(dock).to_have_attribute('data-state','idle',timeout=15000)
        page.mouse.move(10,10)
        trigger=page.get_by_role('button',name='打开棚小智',exact=True)
        trigger.hover();expect(view).to_have_attribute('data-action','wave')
        page.wait_for_timeout(700)
        dock.screenshot(path=str(out/f'wave-{width}.png'))
        checks.append(f'hover drives actual wave {width}')
        page.mouse.move(10,10)
        page.get_by_role('button',name='棚小智设置',exact=True).click()
        page.get_by_role('menuitem',name='坐下休息',exact=True).click()
        expect(view).to_have_attribute('data-action','sitting')
        page.wait_for_timeout(1800)
        dock.screenshot(path=str(out/f'sitting-{width}.png'))
        trigger.hover();expect(view).to_have_attribute('data-action','wave')
        page.wait_for_timeout(700)
        checks.append(f'sit then interrupted wake {width}')
        # Only open/close the real conversation; do not submit or call a model.
        trigger.click()
        page.get_by_role('textbox',name='向棚小智提问',exact=True).wait_for()
        expect(page.locator('.assistant-live-companion .mascot-three-view')).to_have_attribute('data-ready','true',timeout=45000)
        assert page.locator('.mascot-three-view canvas').count()==1
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.get_by_role('button',name='关闭棚小智',exact=True).click()
        expect(page.locator('.pengxiaozhi-dock .mascot-three-view')).to_have_attribute('data-ready','true',timeout=45000)
        checks.append(f'conversation keeps same 3D identity and one viewport {width}')
        context.close()
    context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
    page=context.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:5173/platform?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
    expect(page.locator('.mascot-three-view')).to_have_attribute('data-ready','true',timeout=45000)
    assert page.locator('.mascot-three-view').get_attribute('data-renderer')=='three'
    # A large QA render uses the same live canvas, not a replacement picture.
    page.evaluate('''()=>{const dock=document.querySelector('.pengxiaozhi-dock');document.body.appendChild(dock);dock.style.cssText='position:fixed!important;left:400px!important;top:160px!important;bottom:auto!important;right:auto!important;width:400px!important;background:#f5f5ef';document.querySelectorAll('.assistant-welcome,.assistant-companion-hint').forEach(e=>e.remove());for(const e of [dock.querySelector('.assistant-character-trigger'),dock.querySelector('.mascot-three-view')]){e.style.setProperty('width','400px','important');e.style.setProperty('height','480px','important')}}''')
    page.wait_for_timeout(500)
    page.locator('.mascot-three-view').screenshot(path=str(out/'model-preview.png'))
    checks.append('reduced motion retains real 3D model')
    context.close();browser.close()
assert not errors,errors
report={'passed':len(checks),'checks':checks,'javascript_errors':errors,'model_calls':0}
(out/'browser-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
