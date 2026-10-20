"""Check the shared navigation across routes, sidebar sizes and mobile drawer."""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import json
out=Path(__file__).resolve().parents[2]/'.run/navigation-refresh'; out.mkdir(parents=True,exist_ok=True); errors=[]; results=[]
with sync_playwright() as p:
 b=p.chromium.launch(); page=b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
 for route in ['','data','environment','investigate','production','knowledge','news','forum']:
  page.goto('http://127.0.0.1:5173/platform'+('/'+route if route else '')+'?mode=guest&greenhouse_id=101');page.locator('.exact-side-menu').wait_for();page.wait_for_timeout(550)
  m=page.evaluate('''()=>{const s=document.querySelector('.exact-sider'),h=document.querySelector('.exact-header'),menu=document.querySelector('.exact-side-menu');return {width:s.getBoundingClientRect().width,header:h.getBoundingClientRect().height,menuFont:getComputedStyle(menu.querySelector('.ant-menu-item')).fontSize,groupTitles:[...menu.querySelectorAll('.ant-menu-item-group-title')].map(e=>e.textContent),headerLeft:h.getBoundingClientRect().left}}''')
  assert m['width']==240 and m['header']==68 and m['menuFont']=='15px' and m['headerLeft']==240,(route,m)
  results.append({'route':route or 'overview','layout':m})
 page.screenshot(path=str(out/'desktop.png'))
 page.set_viewport_size({'width':1280,'height':650});page.get_by_role('button',name='展开知识社区',exact=True).click() if page.get_by_role('button',name='展开知识社区',exact=True).count() else None
 page.locator('.pz-knowledge-nav').get_by_role('menuitem',name='棚友论坛',exact=True).scroll_into_view_if_needed()
 assert page.get_by_role('button',name='系统设置',exact=True).is_visible()
 page.screenshot(path=str(out/'short-desktop.png'));results.append({'check':'short viewport scrollable menu and visible footer'})
 page.get_by_role('button',name='收起侧边栏',exact=True).click();page.wait_for_timeout(350)
 assert page.locator('.exact-sider').bounding_box()['width']==72
 page.screenshot(path=str(out/'collapsed.png'));results.append({'check':'collapsed 72px'})
 page.set_viewport_size({'width':390,'height':844});page.get_by_role('button',name='展开侧边栏',exact=True).click();page.wait_for_timeout(350)
 page.screenshot(path=str(out/'mobile-open.png'));assert page.locator('.exact-sider').bounding_box()['width']==240
 page.get_by_role('button',name='关闭导航',exact=True).click(position={'x':370,'y':400});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 results.append({'check':'mobile drawer and overflow'});assert not errors,errors
 b.close()
(out/'layout-results.json').write_text(json.dumps({'passed':len(results),'results':results,'errors':errors},ensure_ascii=False,indent=2),encoding='utf8')
print(len(results),'layout checks passed')

