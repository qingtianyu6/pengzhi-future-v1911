from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import json
out=Path(__file__).resolve().parents[2]/'.run/site-polish-20261019';out.mkdir(parents=True,exist_ok=True);checks=[]
def clear_controls(page):
 return page.evaluate('''()=>[...document.querySelectorAll('#pengzhi-platform button,#pengzhi-platform input')].filter(e=>{const r=e.getBoundingClientRect();if(!r.width||!r.height||r.top<0||r.bottom>innerHeight||e.disabled)return false;const t=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return t&&!e.contains(t)&&t.closest('.pengxiaozhi-dock')}).map(e=>e.getAttribute('aria-label')||e.innerText)''')
with sync_playwright() as p:
 b=p.chromium.launch();page=b.new_page(viewport={'width':1440,'height':1000});page.add_init_script("localStorage.setItem('pengzhi_assistant_prefs_v1:guest',JSON.stringify({manualPosition:false}));localStorage.setItem('pengzhi_assistant_prefs_v1:guest:floating-restored-v1','1');");errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:5173/platform/environment?mode=guest&greenhouse_id=101');page.evaluate('document.fonts.ready');page.wait_for_timeout(2600)
 assert not clear_controls(page),(clear_controls(page),page.locator('.pengxiaozhi-dock').get_attribute('style'));page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');page.wait_for_timeout(700);assert not clear_controls(page),(clear_controls(page),page.locator('.pengxiaozhi-dock').get_attribute('style'));checks.append('Automatic placement clears controls after scrolling')
 trigger=page.get_by_role('button',name='打开棚小智',exact=True);expect(trigger).to_be_visible();assert page.locator('.pengxiaozhi-dock .mascot-three-view').count()==1;checks.append('Independent 3D character remains present')
 box=trigger.bounding_box();page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);page.mouse.down();page.mouse.move(box['x']+box['width']/2-60,box['y']+box['height']/2-25,steps=8);page.mouse.up();page.wait_for_timeout(200)
 pref=json.loads(page.evaluate("localStorage.getItem('pengzhi_assistant_prefs_v1:guest')"));assert pref['right']!=24 or pref['bottom']!=24;assert not page.locator('.shelly-assistant-drawer.ant-drawer-open').count();checks.append('Dragging saves position without opening conversation')
 page.mouse.move(0,0);trigger.click();expect(page.locator('.shelly-assistant-drawer.ant-drawer-open')).to_be_visible();page.get_by_role('button',name='关闭棚小智',exact=True).click();checks.append('Character opens and closes conversation')
 page.set_viewport_size({'width':390,'height':844});page.goto('http://127.0.0.1:5173/platform/investigate?mode=guest&greenhouse_id=101');page.wait_for_timeout(1600)
 field=page.locator('textarea').first;field.focus();page.wait_for_timeout(200);expect(page.locator('.pengxiaozhi-dock')).to_have_attribute('data-editing','true');assert page.locator('.pengxiaozhi-dock').evaluate('e=>getComputedStyle(e).visibility')=='hidden';checks.append('Mobile typing hides the character temporarily')
 page.goto('http://127.0.0.1:5173/platform/research?mode=guest&greenhouse_id=101');expect(page.get_by_role('heading',name='AI 研究台',exact=True)).to_be_visible();assert not page.locator('.pz-section-heading').count();expect(page.get_by_role('link',name='棚智自治',exact=True)).to_be_visible();checks.append('Compact production navigation retains all subpages')
 assert not errors,errors;b.close()
(out/'assistant-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf8');print(len(checks),'assistant and layout checks passed')
