"""Approved library reference: real public API, visual anchors and user flows."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect
out=Path(__file__).resolve().parents[2]/'.run/knowledge-reference';out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];writes=[]
def check(name,condition=True):
 assert condition,name
 checks.append(name);print('PASS',name,flush=True)
def choose(page,label,text):
 page.locator('.ant-select').filter(has=page.get_by_role('combobox',name=label,exact=True)).locator('.ant-select-selector').click()
 page.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).last.click()
with sync_playwright() as p:
 browser=p.chromium.launch();context=browser.new_context(viewport={'width':1600,'height':1000});page=context.new_page()
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:writes.append(r.url) if '/api/community/' in r.url and r.method not in ('GET','OPTIONS') else None)
 page.goto('http://127.0.0.1:5173/platform/knowledge?greenhouse_id=101&mode=guest')
 expect(page.locator('.knowledge-row')).to_have_count(3)
 api=page.request.get('http://127.0.0.1:8000/api/community-public/knowledge').json()['data']['items']
 check('真实目录参与展示',len(api)>3)
 check('游客导入权限保持',page.get_by_role('button',name='导入文档',exact=True).is_disabled())
 geometry=page.evaluate('''()=>{let rect=s=>{let r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}};return {sider:rect('.exact-sider'),search:rect('.knowledge-search-band'),toolbar:rect('.knowledge-toolbar'),row:rect('.knowledge-row'),rail:!!document.querySelector('.wb-assistant-rail')}}''')
 check('参考图侧栏与搜索区域对齐',abs(geometry['sider']['width']-240)<1 and abs(geometry['search']['x']-296)<3 and abs(geometry['search']['y']-210)<8)
 check('列表起点对齐且无右侧固定栏',abs(geometry['row']['y']-509)<8 and not geometry['rail'])
 check('所有列表缩略图加载',page.locator('.knowledge-thumbnail').evaluate_all('(els)=>els.every(e=>e.complete&&e.naturalWidth>0)'))
 title=page.locator('.knowledge-row h2').first.inner_text()
 page.locator('.knowledge-row-actions .ant-btn').first.click();expect(page.locator('.knowledge-reference-detail')).to_be_visible()
 check('展开资料保留来源与管理要点',page.locator('.knowledge-reference-detail a[href^="https://"]').count()>0 and bool(page.locator('.knowledge-reference-detail').inner_text()))
 page.locator('.knowledge-row-actions .ant-btn').first.click();expect(page.locator('.knowledge-reference-detail')).to_have_count(0)
 page.locator('.ant-pagination-item-2').click();expect(page.locator('.knowledge-row h2').first).not_to_have_text(title);check('真实分页')
 page.get_by_role('button',name='病害防治',exact=True).click();expect(page.locator('.ant-pagination-item-active')).to_have_text('1')
 check('分类映射与分页复位',all('病害与虫害' in row for row in page.locator('.knowledge-row').all_inner_texts()))
 choose(page,'知识作物','甜瓜');check('作物筛选',all('甜瓜' in row for row in page.locator('.knowledge-tags').all_inner_texts()) and bool(page.locator('.knowledge-tags').count()))
 page.get_by_role('button',name='全部资料',exact=True).click()
 choose(page,'知识生育阶段','苗期');check('生育期筛选无错误',not errors)
 # reset by visiting the same real route
 page.goto('http://127.0.0.1:5173/platform/knowledge?greenhouse_id=101&mode=guest');expect(page.locator('.knowledge-row')).to_have_count(3)
 page.get_by_role('textbox',name='农业知识问题',exact=True).fill('番茄脐腐');page.get_by_role('button',name='检索知识',exact=True).click()
 expect(page.get_by_role('button',name='返回参考目录',exact=True)).to_be_visible();expect(page.locator('.knowledge-row').filter(has_text='番茄脐部凹陷干腐与生理性脐腐')).to_be_visible();check('真实关键词检索')
 page.get_by_role('button',name='返回参考目录',exact=True).click()
 page.get_by_role('textbox',name='农业知识问题',exact=True).fill('unknownxyz728369');page.get_by_role('button',name='检索知识',exact=True).click();expect(page.locator('.knowledge-empty')).to_be_visible();check('空结果不填充无关资料')
 page.get_by_role('button',name='清除筛选条件',exact=True).click();expect(page.locator('.knowledge-row')).to_have_count(3)
 page.get_by_role('button',name='资料目录',exact=True).click();page.get_by_role('button',name='整枝与授粉 · 4',exact=True).click();check('目录选择真实主题',all('整枝与授粉' in row for row in page.locator('.knowledge-row').all_inner_texts()))
 page.get_by_role('button',name='组织文档',exact=True).click();expect(page.locator('.knowledge-documents')).to_be_visible();check('组织文档独立空状态',page.locator('.knowledge-row').count()==0)
 page.get_by_role('button',name='公共资料',exact=True).click();page.get_by_role('button',name='全部资料',exact=True).click()
 choose(page,'资料排序','标题排序');titles=page.locator('.knowledge-row h2').all_inner_texts();check('标题排序真实改变顺序',len(titles)==3 and titles[0]!=title)
 choose(page,'资料排序','最近更新')
 page.locator('.knowledge-row-actions .ant-btn').first.click();page.get_by_role('button',name='带着这条资料去论坛提问').click();page.wait_for_url('**/platform/forum?**');check('论坛关联保留上下文与出处','greenhouse_id=101' in page.url and 'mode=guest' in page.url and 'reference_url=' in page.url)
 page.goto('http://127.0.0.1:5173/platform/knowledge?greenhouse_id=101&mode=guest');expect(page.locator('.knowledge-row')).to_have_count(3);page.locator('.pengxiaozhi-dock canvas').wait_for();page.wait_for_timeout(1200)
 page.screenshot(path=str(out/'desktop.png'),full_page=True);check('桌面无横向溢出',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
 page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(500)
 page.screenshot(path=str(out/'mobile.png'),full_page=True);check('手机无横向溢出',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
 expect(page.get_by_role('button',name='检索知识',exact=True)).to_be_visible();expect(page.get_by_role('button',name='组织文档',exact=True)).to_be_visible();check('手机关键入口可见')
 check('独立三维角色保留',page.locator('.pengxiaozhi-dock').evaluate('(e)=>getComputedStyle(e).position==="fixed"&&!e.classList.contains("is-compact")'))
 check('游客不会写入正式接口',not writes);check('无JavaScript运行错误',not errors)
 (out/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'geometry':geometry,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8');browser.close()
