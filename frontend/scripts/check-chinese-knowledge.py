"""Verify expanded public references and actual Chinese ministry indexes in the browser."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out=Path(__file__).resolve().parents[2]/'.run/chinese-knowledge'
checks=[];errors=[]
def passed(name):checks.append(name);print('PASS '+name,flush=True)
with sync_playwright() as p:
    api=p.request.new_context(base_url='http://127.0.0.1:8001')
    refs=api.get('/api/community-public/knowledge').json()['data']['items']
    assert len(refs)==52
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000})
    page.set_default_timeout(30000);page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('http://127.0.0.1:5173/api/**',lambda route:route.continue_(url=route.request.url.replace('http://127.0.0.1:5173/api/','http://127.0.0.1:8001/api/',1)))
    def visit(name):page.goto(f'http://127.0.0.1:5173/platform/{name}?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
    visit('knowledge');page.get_by_role('button',name='全部主题',exact=True).wait_for()
    page.get_by_text('共 52 条',exact=True).wait_for()
    assert page.locator('.community-source-result').count()==8
    first=page.locator('.community-source-result h3').first.inner_text()
    page.locator('.ant-pagination-item-2').click()
    assert page.locator('.community-source-result h3').first.inner_text()!=first
    passed('52 real reference entries are paginated, not one long placeholder page')
    page.get_by_role('button',name='整枝与授粉 · 4',exact=True).click()
    assert page.locator('.community-source-result').count()==4
    page.locator('.community-source-result').filter(has_text='甜瓜授粉日期记录与采收判断').get_by_text('适用条件：上海春季大棚技术；品种、整枝方式和留果方案需核对。',exact=True).wait_for()
    passed('topic browsing displays sweet-melon context and original source')
    page.get_by_role('button',name='全部主题',exact=True).click()
    page.get_by_label('农业知识问题',exact=True).fill('番茄脐腐')
    page.get_by_role('button',name='检索知识',exact=True).click()
    page.locator('.community-source-result').filter(has_text='番茄脐部凹陷干腐与生理性脐腐').wait_for()
    passed('expanded references participate in actual search')
    page.get_by_role('button',name='返回参考目录',exact=True).click()
    field=page.get_by_role('combobox',name='知识作物',exact=True);field.focus();field.press('ArrowDown')
    page.locator('.ant-select-dropdown:visible').get_by_text('甜瓜',exact=True).click()
    assert '番茄脐部凹陷干腐与生理性脐腐' not in page.locator('.community-source-result').all_inner_texts()
    passed('crop filter separates tomato-specific guidance from sweet melon')
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(350)
    page.screenshot(path=str(out/'knowledge-mobile-debug.png'),full_page=True)
    print('overflow',page.evaluate('Array.from(document.querySelectorAll("body *")).filter(e=>e.getBoundingClientRect().right>innerWidth+2&&getComputedStyle(e).visibility!=="hidden").slice(0,6).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right}))'),flush=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
    page.screenshot(path=str(out/'knowledge-mobile.png'),full_page=True)
    passed('expanded knowledge page fits 390px viewport')
    visit('news')
    page.get_by_text('中文农业资讯 · 官方标题速览',exact=True).wait_for()
    preview=page.locator('.ant-card').filter(has=page.get_by_text('中文农业资讯 · 官方标题速览',exact=True))
    preview.locator('a[href*="moa.gov.cn"]').first.wait_for()
    assert preview.locator('a[href*="moa.gov.cn"]').count()>0
    passed('guest can read actual public Chinese headlines with original links')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
    page.screenshot(path=str(out/'chinese-news-mobile.png'),full_page=True)
    passed('Chinese headlines retain mobile layout')
    assert not errors,errors
    passed('no JavaScript runtime errors')
    browser.close()
(out/'browser-result.json').write_text(json.dumps({'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
