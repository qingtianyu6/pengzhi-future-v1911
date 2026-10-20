from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import json
out=Path(__file__).resolve().parents[2]/'.run/site-polish-20261019';out.mkdir(parents=True,exist_ok=True);checks=[];settled=[]
with sync_playwright() as p:
 b=p.chromium.launch()
 for width in [1440,390]:
  context=b.new_context(viewport={'width':width,'height':1000 if width==1440 else 844},reduced_motion='reduce')
  context.add_init_script("localStorage.setItem('pengzhi_assistant_prefs_v1:guest',JSON.stringify({manualPosition:false}));localStorage.setItem('pengzhi_assistant_prefs_v1:guest:floating-restored-v1','1');sessionStorage.setItem('pengzhi_assistant_welcomed','1')")
  page=context.new_page()
  for route in ['data','environment','knowledge','news','forum','3d']:
   page.goto('http://127.0.0.1:5173/platform/'+route+'?mode=guest&greenhouse_id=101');page.locator('#pengzhi-platform').wait_for();page.evaluate('document.fonts.ready');page.wait_for_timeout(2600)
   data=page.evaluate('''()=>{const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.top<innerHeight&&r.bottom>0};return {covered:[...document.querySelectorAll('#pengzhi-platform button,#pengzhi-platform input')].filter(e=>visible(e)&&!e.disabled).filter(e=>{const r=e.getBoundingClientRect(),t=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return t&&!e.contains(t)&&t.closest('.pengxiaozhi-dock')}).map(e=>e.getAttribute('aria-label')||e.innerText),welcome:!!document.querySelector('.assistant-welcome'),warning:document.querySelector('.g3d-warning')?{children:[...document.querySelector('.g3d-warning').children].map(e=>({tag:e.tagName,display:getComputedStyle(e).display,width:e.getBoundingClientRect().width})),columns:getComputedStyle(document.querySelector('.g3d-warning')).gridTemplateColumns}:null}}''')
   print('LAYOUT',width,route,'covered',data['covered'],flush=True)
   page.screenshot(path=str(out/f'checking-{route}-{width}.png'))
   assert not data['covered'],(width,route,data['covered'],page.locator('.pengxiaozhi-dock').get_attribute('style'))
   if route=='3d' and width==390: assert data['warning']['children'][1]['width']>100
   assert page.locator('.pz-command-trigger .anticon').is_visible(),(width,route,'search icon')
   settled.append({'width':width,'route':route,**data});page.screenshot(path=str(out/f'settled-{route}-{width}.png'))
  context.close()
 (out/'settled.json').write_text(json.dumps(settled,ensure_ascii=False,indent=2),encoding='utf8')
 context=b.new_context(viewport={'width':1440,'height':1000});context.add_init_script("localStorage.setItem('pengzhi_assistant_prefs_v1:guest',JSON.stringify({manualPosition:false}));localStorage.setItem('pengzhi_assistant_prefs_v1:guest:floating-restored-v1','1');sessionStorage.setItem('pengzhi_assistant_welcomed','1')");page=context.new_page()
 page.goto('http://127.0.0.1:5173/platform/knowledge?mode=guest&greenhouse_id=101');expect(page.get_by_role('heading',name='农业知识库',exact=True)).to_be_visible()
 page.keyboard.press('Control+k');expect(page.get_by_label('搜索平台功能',exact=True)).to_be_visible();page.get_by_label('搜索平台功能',exact=True).fill('论坛');page.locator('.pz-navigation-group').get_by_role('button',name='棚友论坛',exact=False).click();page.wait_for_url('**/platform/forum?**');checks.append('Ctrl K search opens forum and preserves greenhouse context')
 page.locator('.forum-search input').fill('不存在的审查关键词XYZ');page.locator('.forum-search input').press('Enter');expect(page.locator('.forum-empty')).to_be_visible();checks.append('Forum search has a usable empty state')
 page.goto('http://127.0.0.1:5173/platform/knowledge?mode=guest&greenhouse_id=101');page.get_by_role('textbox',name='农业知识问题').fill('番茄');page.get_by_role('button',name='检索知识',exact=True).click();expect(page.get_by_role('button',name='返回参考目录',exact=True)).to_be_visible();expect(page.locator('.knowledge-row').first).to_be_visible();checks.append('Knowledge query returns real catalogue results')
 page.get_by_role('button',name='资料目录',exact=True).click();expect(page.get_by_role('dialog',name='资料目录',exact=True)).to_be_visible();checks.append('Knowledge directory opens');page.locator('.ant-modal-close:visible').click()
 page.goto('http://127.0.0.1:5173/platform/news?mode=guest&greenhouse_id=101');page.get_by_role('button',name='我的收藏与关注',exact=True).click();expect(page.get_by_role('button',name='收藏资讯',exact=True)).to_be_visible();checks.append('News favorites and following page is reachable')
 page.get_by_role('button',name='今日快讯',exact=True).click();expect(page.locator('.news-feature')).to_be_visible();checks.append('News returns to headline layout')
 page.get_by_role('button',name='系统设置',exact=True).click();expect(page.locator('.ant-drawer-open')).to_be_visible();page.locator('.ant-drawer-open').get_by_role('button',name='AI 能力与运行',exact=True).click();page.wait_for_url('**/platform/ai-quality?**');expect(page.get_by_role('heading',name='AI 能力与运行',exact=True)).to_be_visible();checks.append('AI quality page reachable from settings')
 context.close()
 anonymous=b.new_context();page=anonymous.new_page();page.goto('http://127.0.0.1:5173/platform/research');page.wait_for_url('**/login?next=**');checks.append('Fresh unauthenticated protected route redirects to login');anonymous.close();b.close()
(out/'interactions.json').write_text(json.dumps({'checks':checks,'passed':len(checks),'settled':settled},ensure_ascii=False,indent=2),encoding='utf8')
print('PASS',len(checks),'read-only interaction checks; settled layouts',len(settled))
