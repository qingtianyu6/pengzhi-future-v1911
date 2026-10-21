"""Audit actual loaded type and responsive layout across all current routes."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect

out=Path(__file__).resolve().parents[2]/'.run'/'typography-polish'
out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];external_fonts=[]
platform=['','data','3d','environment','investigate','production','autonomy','research','knowledge','news','forum','ai-quality']
public=['/home','/introduction','/features','/highlights','/scenarios','/login','/register']
with sync_playwright() as p:
    b=p.chromium.launch(channel='msedge')
    c=b.new_context(reduced_motion='reduce',timezone_id='Asia/Shanghai')
    page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda req:external_fonts.append(req.url) if 'fonts.googleapis.com' in req.url or 'fonts.gstatic.com' in req.url else None)
    for width in (1680,1024,390):
        page.set_viewport_size({'width':width,'height':1050 if width>620 else 844})
        for path in ['/platform'+('/'+x if x else '') for x in platform]+public:
            is_platform=path.startswith('/platform')
            page.goto('http://127.0.0.1:5173'+path+('?mode=guest&greenhouse_id=101' if is_platform else ''),wait_until='domcontentloaded')
            scope=page.locator('.pz-workspace-page' if is_platform else '.auth-page' if path in ('/login','/register') else '.reference-site-home')
            scope.wait_for();page.wait_for_timeout(650);page.evaluate('document.fonts.ready')
            data=scope.evaluate('''scope=>{const font=e=>e?{size:getComputedStyle(e).fontSize,family:getComputedStyle(e).fontFamily,weight:getComputedStyle(e).fontWeight,line:getComputedStyle(e).lineHeight}:null;return {root:font(scope),heading:font(scope.querySelector('h1')),body:font(scope.querySelector('p')),overflow:document.documentElement.scrollWidth-innerWidth,fontLoaded:document.fonts.check('15px "Noto Sans SC"')}}''')
            assert data['fontLoaded'],(path,width,'local font missing')
            assert 'Noto Sans SC' in data['root']['family'],(path,width,data)
            assert data['overflow']<=1,(path,width,data)
            if is_platform:
                assert data['root']['size']=='15px',(path,width,data)
                if data['heading']:
                    expected=('32px' if width<=760 else '42px') if path.endswith('/news') else ('28px' if width<=760 else '32px' if path=='/platform' else '34px')
                    assert data['heading']['size']==expected,(path,width,data)
                    assert data['heading']['weight']=='650',(path,width,data)
                if width>620:
                    assert page.locator('.exact-side-menu .ant-menu-item').first.evaluate('e=>getComputedStyle(e).fontSize')=='16px'
            checks.append({'route':path,'width':width,'computed':data})
            print('PASS',path,width,flush=True)
            if width in (1680,390) and path in ('/platform/production','/platform/autonomy','/platform/knowledge','/home','/login'):
                page.screenshot(path=str(out/(path.strip('/').replace('/','-')+f'-{width}.png')))
    page.set_viewport_size({'width':1680,'height':1050})
    page.goto('http://127.0.0.1:5173/platform/forum?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
    page.get_by_role('button',name='发布帖子',exact=False).click()
    dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
    title=dialog.locator('.ant-modal-title,.ant-drawer-title').first
    assert title.evaluate('e=>getComputedStyle(e).fontSize')=='20px'
    assert 'Noto Sans SC' in title.evaluate('e=>getComputedStyle(e).fontFamily')
    checks.append({'check':'Portal editor shares local font and 20px title'})
    page.goto('http://127.0.0.1:5173/platform/research?mode=guest&greenhouse_id=101',wait_until='domcontentloaded')
    page.get_by_role('tab',name='方案推演',exact=True).click()
    page.get_by_role('button',name='生成方案比较',exact=True).click()
    expect(page.locator('.ag-chart:visible')).to_have_count(1)
    assert page.locator('.ant-tabs-tabpane-hidden:visible').count()==0
    checks.append({'check':'Research view only shows the active tab after switching'})
    assert not external_fonts,external_fonts
    assert not errors,errors
    b.close()
(out/'results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,'external_font_requests':external_fonts},ensure_ascii=False,indent=2),encoding='utf-8')
print(len(checks),'typography and layout checks passed')
