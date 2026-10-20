from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect
out=Path(__file__).resolve().parents[2]/'.run/typography-refresh';out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
with sync_playwright() as p:
 b=p.chromium.launch();page=b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
 for width in [1440,390]:
  page.set_viewport_size({'width':width,'height':1000 if width==1440 else 844})
  for route in ['','data','environment','investigate','production','knowledge','news','forum']:
   page.goto('http://127.0.0.1:5173/platform'+('/'+route if route else '')+'?mode=guest&greenhouse_id=101')
   page.locator('.pz-workspace-page').wait_for();page.wait_for_timeout(650);page.evaluate('document.fonts.ready');page.wait_for_function("document.querySelector('#pengzhi-platform .pz-workspace-page')")
   data=page.evaluate('''()=>{const root=document.querySelector('#pengzhi-platform'),scope=document.querySelector('.pz-workspace-page');const font=e=>e?{size:getComputedStyle(e).fontSize,family:getComputedStyle(e).fontFamily,weight:getComputedStyle(e).fontWeight}:null;return {root:font(root),heading:font(scope.querySelector('h1')),input:font(scope.querySelector('input.ant-input')),body:font(scope.querySelector('p')),overflow:document.documentElement.scrollWidth>innerWidth+1,fontLoaded:document.fonts.check('15px "Noto Sans SC"')}}''')
   assert data['root']['size']=='15px' and 'Noto Sans SC' in data['root']['family'],(route,data)
   assert data['fontLoaded'],(route,'font missing')
   if width==1440: assert page.locator('.exact-side-menu .ant-menu-item').first.evaluate('e=>getComputedStyle(e).fontSize')=='15px'
   assert not data['overflow'],(route,width,'horizontal overflow')
   if data['heading'] and route!='news':assert data['heading']['size']==('32px' if width==1440 else '27px'),(route,data)
   checks.append({'route':route or 'overview','width':width,'computed':data});print('PASS',route or 'overview',width,flush=True)
   if route in ['forum','news','investigate']:page.screenshot(path=str(out/(route+('-desktop' if width==1440 else '-mobile')+'.png')))
 # Font and sizing also apply to the editor portal, without creating a post.
 page.set_viewport_size({'width':1440,'height':1000});page.get_by_role('button',name='发布帖子',exact=True).click()
 dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
 title=dialog.locator('.ant-modal-title,.ant-drawer-title').first
 assert title.evaluate('e=>getComputedStyle(e).fontSize')=='20px'
 checks.append({'check':'editor title 20px and opens successfully'});page.screenshot(path=str(out/'editor.png'))
 assert not errors,errors
 b.close()
(out/'results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf8')
print(len(checks),'typography checks passed')
