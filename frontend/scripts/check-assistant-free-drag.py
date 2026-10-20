from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import json
out=Path(__file__).resolve().parents[2]/'.run/assistant-free-drag';out.mkdir(parents=True,exist_ok=True);checks=[];errors=[]
def pos(page):return page.locator('.pengxiaozhi-dock').evaluate('e=>({right:parseFloat(getComputedStyle(e).right),bottom:parseFloat(getComputedStyle(e).bottom),x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,width:e.offsetWidth,height:e.offsetHeight})')
def same(a,b):return abs(a['right']-b['right'])<2 and abs(a['bottom']-b['bottom'])<2
with sync_playwright() as p:
 b=p.chromium.launch();page=b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:5173/platform/data?mode=guest&greenhouse_id=101');page.evaluate('document.fonts.ready');page.get_by_role('button',name='打开棚小智',exact=True).wait_for();page.wait_for_timeout(700)
 trigger=page.get_by_role('button',name='打开棚小智',exact=True);old=pos(page);box=trigger.bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
 page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-250,y-180,steps=12);page.mouse.up();page.mouse.move(0,0);page.wait_for_timeout(600);moved=pos(page)
 assert abs(moved['right']-old['right']-250)<3 and abs(moved['bottom']-old['bottom']-180)<3,(old,moved);checks.append('Mouse freely drags to the requested position')
 assert not page.locator('.shelly-assistant-drawer.ant-drawer-open').count();checks.append('Drag does not open chat')
 page.evaluate('window.scrollTo(0,200)');page.wait_for_timeout(700);assert same(moved,pos(page));checks.append('Does not snap back after scrolling')
 page.get_by_role('menuitem',name='环境监测',exact=True).click();page.wait_for_timeout(1000);assert same(moved,pos(page));checks.append('Position retained across page changes')
 page.reload();page.get_by_role('button',name='打开棚小智',exact=True).wait_for();page.wait_for_timeout(800);assert same(moved,pos(page));checks.append('Position retained after reload')
 trigger=page.get_by_role('button',name='打开棚小智',exact=True);trigger.focus();trigger.press('ArrowUp');page.wait_for_timeout(250);assert abs(pos(page)['bottom']-moved['bottom']-12)<2;checks.append('Keyboard arrows adjust position')
 trigger.click();expect(page.locator('.shelly-assistant-drawer.ant-drawer-open')).to_be_visible();page.get_by_role('button',name='关闭棚小智',exact=True).click();checks.append('Normal click still opens conversation')
 page.screenshot(path=str(out/'desktop.png'))
 mobile=b.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True);phone=mobile.new_page();phone.on('pageerror',lambda e:errors.append(str(e)));phone.goto('http://127.0.0.1:5173/platform/data?mode=guest&greenhouse_id=101');phone.get_by_role('button',name='打开棚小智',exact=True).wait_for();phone.wait_for_timeout(600)
 box=phone.get_by_role('button',name='打开棚小智',exact=True).bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2;before=pos(phone);cdp=mobile.new_cdp_session(phone)
 cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
 for n in range(1,9):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x-120*n/8,'y':y-170*n/8}]})
 cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});phone.wait_for_timeout(500);after=pos(phone)
 assert abs(after['right']-before['right']-120)<3 and abs(after['bottom']-before['bottom']-170)<3,(before,after);checks.append('Real touch events drag the mobile character')
 assert after['x']>=0 and after['y']>=0 and after['x']+after['width']<=390 and after['y']+after['height']<=844;checks.append('Character remains inside the viewport')
 phone.screenshot(path=str(out/'mobile.png'));assert not errors,errors;mobile.close();b.close()
(out/'results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf8');print(len(checks),'free movement checks passed')
