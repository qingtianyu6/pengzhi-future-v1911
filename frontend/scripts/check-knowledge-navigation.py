"""Real browser checks for independent community title and expansion controls."""
from pathlib import Path
import json
import re
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect

out=Path(__file__).resolve().parents[2]/'.run/knowledge-navigation'
out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
def check(name,condition=True):
    assert condition,name
    checks.append(name);print('PASS',name,flush=True)
def route(page,path):
    page.wait_for_url('**/platform/'+path+'?**')
    q=parse_qs(urlparse(page.url).query)
    assert q['greenhouse_id']==['101'] and q['mode']==['guest']

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.set_default_timeout(20000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:5173/platform/news?greenhouse_id=101&mode=guest')
    expect(page.get_by_role('button',name='收起知识社区',exact=True)).to_be_visible()
    check('news opens with community subpages visible')
    page.get_by_role('button',name='收起知识社区',exact=True).click()
    toggle=page.get_by_role('button',name='展开知识社区',exact=True)
    toggle.wait_for()
    check('community starts collapsed',toggle.get_attribute('aria-expanded')=='false')
    before=page.url;toggle.click()
    page.get_by_role('button',name='收起知识社区',exact=True).wait_for()
    check('arrow expands without navigating',page.url==before)
    group=page.locator('.pz-knowledge-nav')
    for label in ['农业知识库','棚智农讯','棚友论坛']:
        group.get_by_role('menuitem',name=label,exact=True).wait_for()
    check('three requested subpages visible')
    group.get_by_role('menuitem',name='棚友论坛',exact=True).click();route(page,'forum')
    check('forum selection preserves greenhouse and guest context')
    expect(group.get_by_role('menuitem',name='棚友论坛',exact=True)).to_have_class(re.compile('ant-menu-item-selected'))
    check('selected child is highlighted')
    title=group.locator('.ant-menu-submenu-title')
    title.get_by_text('知识社区',exact=True).click();route(page,'knowledge')
    check('title always opens knowledge library inside community')
    check('title does not toggle expanded state',page.get_by_role('button',name='收起知识社区',exact=True).get_attribute('aria-expanded')=='true')
    group.get_by_role('menuitem',name='棚智农讯',exact=True).click();route(page,'news')
    title.locator(':scope > .anticon').first.click();route(page,'knowledge')
    check('main icon opens library')
    before=page.url;page.get_by_role('button',name='收起知识社区',exact=True).click()
    group.get_by_role('menuitem',name='棚友论坛',exact=True).wait_for(state='hidden')
    check('arrow collapses without navigation',page.url==before)
    toggle=page.get_by_role('button',name='展开知识社区',exact=True)
    toggle.focus();toggle.press('Enter')
    page.get_by_role('button',name='收起知识社区',exact=True).wait_for()
    check('keyboard arrow expansion stays on current page',page.url==before)
    check('old duplicate community tab row removed',page.locator('.pz-section-nav').count()==0)
    page.screenshot(path=str(out/'desktop-expanded.png'))
    page.get_by_role('button',name='收起侧边栏',exact=True).click()
    page.get_by_role('button',name='展开侧边栏',exact=True).wait_for()
    page.get_by_role('menuitem',name='知识社区',exact=True).click();route(page,'knowledge')
    check('collapsed sidebar icon still opens library')
    page.get_by_role('button',name='展开侧边栏',exact=True).click()
    page.get_by_role('button',name='收起知识社区',exact=True).wait_for()
    check('sidebar restoration retains submenu expansion')
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='展开侧边栏',exact=True).wait_for()
    page.get_by_role('button',name='展开侧边栏',exact=True).click()
    page.locator('.pz-knowledge-nav').get_by_role('menuitem',name='棚智农讯',exact=True).click();route(page,'news')
    page.get_by_role('button',name='展开侧边栏',exact=True).wait_for()
    check('mobile child selection navigates and closes sidebar')
    check('mobile has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
    check('no JavaScript errors',not errors)
    browser.close()
(out/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
print(len(checks),'navigation checks passed')
