"""Shared navigation geometry, empty/mobile pages and marketing typography.

Guest fixtures only; network APIs are disabled for layout checks. Business flows
are covered separately by pytest with a temporary database.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect

OUT = Path(__file__).resolve().parents[2]/'.run'/'operations-optimization'
OUT.mkdir(parents=True,exist_ok=True)
routes = ['', 'data', '3d', 'environment', 'investigate', 'production', 'autonomy', 'research', 'knowledge', 'news', 'forum', 'ai-quality']
checks, errors = [], []
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge')
    context = browser.new_context(reduced_motion='reduce')
    context.route('http://127.0.0.1:5173/api/**',lambda route:route.fulfill(status=503,json={'message':'Layout-only isolated network'}))
    page = context.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)))
    for width in (1586,1024,390):
        page.set_viewport_size({'width':width,'height':992 if width>620 else 844})
        for route in routes:
            page.goto('http://127.0.0.1:5173/platform'+('/'+route if route else '')+'?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
            page.locator('.exact-header').wait_for()
            page.wait_for_timeout(400)
            geometry = page.evaluate("""()=>({header:document.querySelector('.exact-header').getBoundingClientRect().height,sider:document.querySelector('.exact-sider').getBoundingClientRect().width,overflow:document.documentElement.scrollWidth-innerWidth})""")
            assert geometry['header']==(60 if width<=620 else 62),(route,width,geometry)
            assert geometry['sider']==(72 if width<=620 else 240),(route,width,geometry)
            assert geometry['overflow']<=1,(route,width,geometry)
            checks.append({'route':route or 'overview','width':width,'geometry':geometry})
        if width==1586:
            page.get_by_role('button',name='收起侧边栏',exact=True).click()
            expect(page.locator('.exact-sider')).to_have_css('width','72px')
            page.get_by_role('button',name='展开侧边栏',exact=True).click()
            expect(page.locator('.exact-sider')).to_have_css('width','240px')
        elif width==390:
            page.get_by_role('button',name='展开侧边栏',exact=True).click()
            expect(page.locator('.mobile-sider-backdrop')).to_be_visible()
            page.get_by_role('menuitem',name='AI 研究台',exact=True).click()
            expect(page.locator('.mobile-sider-backdrop')).to_have_count(0)
    for width in (320,375,390):
        page.set_viewport_size({'width':width,'height':844})
        page.goto('http://127.0.0.1:5173/features',wait_until='domcontentloaded')
        heading = page.locator('.hero-copy h1')
        expect(heading).to_be_visible()
        lines = heading.evaluate("""e=>{let walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT),node,lines=[];while(node=walker.nextNode()){for(let i=0;i<node.length;i++){if(!node.textContent[i].trim())continue;let range=document.createRange();range.setStart(node,i);range.setEnd(node,i+1);let rect=range.getBoundingClientRect(),center=rect.y+rect.height/2,line=lines.find(l=>Math.abs(l.y-center)<Math.max(12,rect.height*.45));if(line)line.text+=node.textContent[i];else lines.push({y:center,text:node.textContent[i]})}}return lines.sort((a,b)=>a.y-b.y).map(l=>l.text)}""")
        assert all(len(line)>1 for line in lines),(width,lines)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(OUT/f'features-{width}.png'))
        checks.append({'marketing_width':width,'heading_lines':lines})
    assert not errors,errors
    browser.close()
(OUT/'layouts.json').write_text(json.dumps({'checks':checks,'errors':errors,'scope':'36 navigation viewport combinations, sidebar controls, 3 marketing widths; isolated guest layout fixtures'},ensure_ascii=False,indent=2),encoding='utf-8')
print('36 navigation combinations, sidebar interactions and 3 mobile heading widths passed')
