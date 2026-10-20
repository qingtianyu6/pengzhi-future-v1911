"""Real UI flows for the unified investigation workspace; no mocked responses."""
from pathlib import Path
import io
import json
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[2]
out=root/'.run/investigation-ui'
out.mkdir(parents=True,exist_ok=True)
checks=[]
errors=[]
formal_writes=[]
base='http://127.0.0.1:5173'

def check(label, condition=True):
    assert condition,label
    checks.append(label)
    print('PASS',label,flush=True)

def stored(page):
    return page.evaluate("JSON.parse(sessionStorage.getItem('pengzhi-investigations-v1')||'[]')[0]")

def settled(page, count=None, runs=None):
    if count is not None:
        page.wait_for_function('(n)=>JSON.parse(sessionStorage.getItem("pengzhi-investigations-v1"))?.[0]?.payload.evidence.length===n',arg=count)
    if runs is not None:
        page.wait_for_function('(n)=>(JSON.parse(sessionStorage.getItem("pengzhi-investigations-v1"))?.[0]?.payload.autonomy_runs?.length||0)===n',arg=runs)
    page.get_by_role('button',name='＋ 新建调查',exact=True).wait_for(state='visible')
    page.wait_for_function("!document.querySelector('.iw-hero .ant-btn-primary').disabled")

def choose(page, name, label):
    if name in ('照片观察动作','照片位置'):
        page.locator('.iw-photo-options').evaluate('(e)=>e.open=true')
    item=page.get_by_role('combobox',name=name,exact=True)
    item.evaluate("e=>{const d=e.closest('details');if(d)d.open=true}")
    item.scroll_into_view_if_needed()
    item.focus();item.press('ArrowDown')
    controls=item.get_attribute('aria-controls')
    popup=page.locator('.ant-select-dropdown').filter(has=page.locator('[id="'+controls+'"]'))
    active=popup.locator('.ant-select-item-option-active')
    for _ in range(20):
        if active.inner_text().strip()==label:
            item.press('Enter')
            return
        item.press('ArrowDown')
    raise AssertionError('Cannot select '+name+': '+label)

def close_drawer(page):
    page.locator('.ant-drawer-open .ant-drawer-close').last.click()
    page.locator('.ant-drawer-mask').wait_for(state='hidden')

def screenshot(page,name):
    page.evaluate("() => {window.scrollTo(0,0);document.querySelectorAll('.ant-layout,.app-content').forEach(e=>e.scrollTop=0)}")
    page.screenshot(path=str(out/name),full_page=True)

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1600,'height':1000},timezone_id='Asia/Shanghai')
    page.set_default_timeout(30000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:formal_writes.append(r.url) if '/api/investigate/' in r.url and r.method=='POST' else None)
    page.goto(base+'/platform/investigate?mode=guest&greenhouse_id=101')
    page.get_by_label('农业问题',exact=True).wait_for()
    page.evaluate('document.fonts.ready')
    check('unified navigation and empty state',page.get_by_role('heading',name='棚智探因',exact=True).count()==1 and page.locator('.pz-section-nav').count()==0)
    check('local variable Chinese font loads',page.evaluate("document.fonts.check('600 16px \"Noto Sans SC\"')"))
    screenshot(page,'desktop-empty.png')
    page.get_by_label('农业问题',exact=True).fill('为什么东侧番茄叶片出现异常，但中央传感器湿度显示正常？')
    page.get_by_role('button',name='开始调查 →',exact=True).click()
    settled(page,0,1)
    initial=stored(page)
    check('real backend recommendation',len(initial['payload']['analysis']['candidates'])>=3 and bool(initial['payload']['analysis']['next']['target']))
    page.locator('.iw-spatial-selector').get_by_role('button',name='中央',exact=True).click()
    page.locator('.ant-modal-confirm .ant-btn-primary').click()
    check('spatial selection opens measurement form',page.locator('.iw-observation-form').get_attribute('open') is not None)
    page.get_by_role('button',name='暂停自动更新',exact=True).click()
    choose(page,'本次检查','测量异常区域温湿度')
    page.get_by_label('湿度（%RH）',exact=True).fill('45')
    page.get_by_label('观察说明',exact=True).fill('异常叶片附近同高度实际补测45%RH')
    page.get_by_role('button',name='提交证据并重新分析',exact=True).click()
    settled(page,1,1)
    check('pause prevents automatic follow-up',len(stored(page)['payload']['autonomy_runs'])==1)
    page.get_by_role('button',name='继续自主排查',exact=True).click()
    settled(page,1,2)
    check('resume performs an actual backend calculation',len(stored(page)['payload']['autonomy_runs'])==2)
    page.locator('.iw-observation-form').evaluate('(e)=>e.open=true')
    choose(page,'本次检查','拍摄异常叶片背面')
    choose(page,'叶背蛛网/活动小点','是 / 看到了')
    choose(page,'叶背霉层','否 / 已检查未见')
    page.get_by_label('观察说明',exact=True).fill('叶背有细蛛网和活动小点，未见霉层')
    page.get_by_role('button',name='提交证据并重新分析',exact=True).click()
    settled(page,2,3)
    changed=stored(page)
    check('evidence changes priority and next observation',changed['payload']['analysis']['candidates'][0]['id']=='mites' and changed['payload']['analysis']['next']['id']!=initial['payload']['analysis']['next']['id'])
    check('completed checks excluded',not any(a['id'] in {'back','local'} for a in changed['payload']['analysis']['rankings']))
    check('real judgment history retained',len(changed['payload']['history'])==3 and changed['payload']['history'][-1]['previous_leader']!=changed['payload']['history'][-1]['leader'])
    page.get_by_text('引导排查',exact=True).click()
    page.locator('.iw-observation-form').evaluate('(e)=>e.open=true')
    choose(page,'本次检查','拍摄异常叶片正面')
    page.get_by_label('观察说明',exact=True).fill('叶片正面点状失绿，供人工复查')
    page.get_by_role('button',name='提交证据并重新分析',exact=True).click()
    settled(page,3,3)
    check('budget exhausted and guided mode makes no autonomous request',stored(page)['payload']['analysis']['remaining']==0 and page.locator('.iw-observation-form').count()==0)
    page.get_by_role('button',name='查看执行记录',exact=True).click()
    check('execution log reflects actual runs',page.locator('.iw-process-log .iw-run-log-entry').count()==3)
    close_drawer(page)
    page.get_by_role('button',name='调查记录 · 1',exact=True).click()
    page.get_by_label('最终排查记录',exact=True).fill('现场线索倾向叶螨，需农艺师复核后处理')
    page.get_by_role('button',name='记录并归档',exact=True).click()
    page.wait_for_function("JSON.parse(sessionStorage.getItem('pengzhi-investigations-v1'))[0].status==='completed'")
    close_drawer(page)
    page.reload();page.locator('.iw-candidates').wait_for()
    check('reload restores archived case',stored(page)['status']=='completed' and len(stored(page)['payload']['history'])==4)
    # A different real image file starts a photo-only case and runs the actual local CV service.
    page.get_by_role('button',name='＋ 新建调查',exact=True).click()
    rng=np.random.default_rng(73)
    arr=rng.integers(25,100,(300,400,3),dtype=np.uint8)
    arr[60:240,90:300]=[210,190,30]
    blob=io.BytesIO();Image.fromarray(arr).save(blob,format='PNG')
    page.locator('input[type=file]').set_input_files({'name':'pixel-test-fixture.png','mimeType':'image/png','buffer':blob.getvalue()})
    settled(page,1,1)
    photo=stored(page)
    check('photo-only entry runs actual image analysis',photo['payload']['question']=='请排查这张番茄叶片照片中的异常' and photo['payload']['evidence'][0]['visual']['width']==400)
    page.get_by_role('button',name='查看图片分析与修正 →',exact=True).click()
    card=page.locator('.investigate-visual-card').first
    card.get_by_text('确认、修正或拒绝视觉证据',exact=True).click()
    choose(page,'蛛网状结构','已核查：有');choose(page,'疑似霉层','已核查：未见')
    card.get_by_role('button',name='保存人工核查并重算',exact=True).click()
    settled(page,1,2)
    check('visual correction updates ranking without spending another check',stored(page)['payload']['analysis']['candidates'][0]['id']=='mites' and stored(page)['payload']['analysis']['remaining']==2)
    close_drawer(page)
    screenshot(page,'desktop-result.png')
    # Upload a second photo. Prior correction history must survive.
    choose(page,'照片观察动作','叶片背面')
    second=io.BytesIO();Image.fromarray(np.clip(arr.astype(int)+4,0,255).astype(np.uint8)).save(second,format='PNG')
    page.locator('input[type=file]').set_input_files({'name':'second-pixel-test.png','mimeType':'image/png','buffer':second.getvalue()})
    settled(page,2,3)
    check('follow-up photo preserves prior visual review and history',len(stored(page)['payload']['history'])==4 and stored(page)['payload']['evidence'][0]['visual_review']['webbing'] is True)
    page.reload();page.locator('.iw-candidates').wait_for()
    check('photo session restores without formal writes',len(stored(page)['payload']['evidence'])==2 and not formal_writes)
    # Legacy routes point into the same workspace; risk and old classifier reviews still work.
    page.goto(base+'/platform/disease-time-machine?mode=guest&greenhouse_id=101')
    page.locator('.ant-drawer-open .ant-drawer-title').get_by_text('环境风险参考 · 病害时间机',exact=True).wait_for()
    check('old time-machine route opens integrated risk panel','/platform/investigate?' in page.url)
    close_drawer(page)
    page.goto(base+'/platform/diagnosis?view=history&mode=guest&greenhouse_id=101')
    page.locator('.disease-page[data-view=history]').wait_for()
    check('old review records remain accessible',page.locator('.disease-page[data-view=history]').count()==1)
    close_drawer(page)
    page.goto(base+'/platform/diagnosis?mode=guest&greenhouse_id=101')
    page.locator('#investigation-vision').wait_for()
    check('old photo-recognition route enters unified workspace','/platform/investigate?' in page.url)
    # Mobile width and all drawers use the real same state.
    page.set_viewport_size({'width':390,'height':844})
    screenshot(page,'mobile-result.png')
    check('mobile has no horizontal page overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
    page.get_by_role('button',name='查看执行记录',exact=True).click()
    check('mobile drawer fits viewport',page.locator('.ant-drawer-open .ant-drawer-content').bounding_box()['width']<=390)
    close_drawer(page)
    # Different greenhouse uses independent guest records.
    page.goto(base+'/platform/investigate?mode=guest&greenhouse_id=102')
    page.get_by_label('农业问题',exact=True).wait_for()
    check('guest cases remain isolated by greenhouse',page.locator('.iw-candidates').count()==0)
    check('no JavaScript runtime errors',not errors)
    browser.close()

(out/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,'formal_writes':formal_writes},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'{len(checks)} browser checks passed')
