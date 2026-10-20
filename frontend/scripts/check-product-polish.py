"""UI refinement checks with real guest APIs; no production writes/model calls."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[2]
out = root / '.run/product-polish'
out.mkdir(parents=True, exist_ok=True)
checks, errors, writes = [], [], []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.set_default_timeout(30000)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: writes.append(r.url) if r.method == 'POST' and '/api/investigate/' in r.url else None)

    def passed(name):
        checks.append(name)
        print(name, flush=True)

    def open_page(route):
        page.goto('http://127.0.0.1:5173/platform' + route + '?mode=guest&greenhouse_id=101', wait_until='domcontentloaded')

    def no_overflow():
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')

    open_page('')
    page.locator('.pz-today-focus').wait_for()
    assert page.locator('.pz-command-hero h1').inner_text().replace('\n', '') == '让每一棚生长，都有据可循。'
    assert page.locator('.exact-metric-card').count() == 5
    assert page.locator('.wb-priority-card, .wb-priority-notice').count() == 0
    no_overflow()
    page.screenshot(path=str(out / 'dashboard-desktop.png'), full_page=True)
    passed('dashboard: one priority focus, five actual metrics, no duplicate notices')
    page.locator('.pz-today-focus .ant-btn').click()
    page.wait_for_url('**/platform/environment?**')
    assert 'greenhouse_id=101' in page.url
    passed('dashboard: focus action reaches current greenhouse environment')

    open_page('/investigate')
    page.locator('.investigate-hero h1').wait_for()
    page.get_by_role('button', name='开始调查', exact=True).click()
    page.locator('.pz-investigation-result').wait_for()
    assert page.locator('.investigate-candidate').count() > 1
    assert page.locator('.investigate-candidate[open]').count() == 1
    assert not page.locator('.pz-investigation-setup').first.evaluate('(e)=>e.open')
    before = page.evaluate('JSON.parse(sessionStorage.getItem("pengzhi-investigations-v1"))[0]')
    passed('investigation: real analysis, collapsible setup and focused leading candidate')

    page.get_by_role('combobox', name='本次检查', exact=True).focus()
    page.get_by_role('combobox', name='本次检查', exact=True).press('ArrowDown')
    page.locator('.ant-select-dropdown:visible').get_by_text('拍摄异常叶片背面', exact=True).click()
    for label, option in [('叶背蛛网/活动小点', '是 / 看到了'), ('叶背霉层', '否 / 已检查未见')]:
        field = page.get_by_label(label, exact=True)
        field.focus()
        field.press('ArrowDown')
        if option.startswith('否'):
            field.press('ArrowDown')
        field.press('Enter')
    page.get_by_label('观察说明', exact=True).fill('叶背见细蛛网与活动小点；已检查未见霉层。')
    page.get_by_role('button', name='提交证据并重新分析', exact=True).click()
    page.locator('.pz-investigation-result.has-change').wait_for()
    after = page.evaluate('JSON.parse(sessionStorage.getItem("pengzhi-investigations-v1"))[0]')
    assert before['payload']['analysis']['candidates'][0]['id'] != after['payload']['analysis']['candidates'][0]['id']
    assert after['payload']['evidence'] and after['payload']['analysis']['remaining'] < before['payload']['analysis']['remaining']
    assert page.locator('.pz-investigation-steps [aria-current="step"]').inner_text().startswith('03')
    passed('investigation: new evidence changes leader, progress and remaining budget')
    page.get_by_role('button', name='上传照片作为新证据', exact=True).click()
    assert page.locator('#pz-vision-details').evaluate('(e)=>e.open')
    page.locator('input[type=file]').wait_for(state='attached')
    passed('investigation: follow-up photo entry expands actual upload panel')
    no_overflow()
    page.screenshot(path=str(out / 'investigation-desktop.png'), full_page=True)
    page.reload(wait_until='domcontentloaded')
    page.locator('.pz-investigation-result.has-change').wait_for()
    passed('investigation: refreshed session retains dynamic analysis')
    page.set_viewport_size({'width': 390, 'height': 844})
    no_overflow()
    page.get_by_label('观察说明', exact=True).focus()
    page.wait_for_function('document.querySelector(".pengxiaozhi-dock")?.dataset.editing === "true"')
    assert page.locator('.pengxiaozhi-dock').evaluate('(e)=>getComputedStyle(e).visibility') == 'hidden'
    page.locator('.investigate-hero h1').click()
    page.wait_for_function('document.querySelector(".pengxiaozhi-dock")?.dataset.editing === "false"')
    assert page.locator('.mascot-three-view').count() > 0
    page.screenshot(path=str(out / 'investigation-mobile.png'), full_page=True)
    passed('mobile: no overflow, mascot yields during input and returns as 3D character')

    page.set_viewport_size({'width': 1440, 'height': 1000})
    open_page('/3d')
    page.locator('.g3d-scene-title').wait_for()
    page.locator('.pz-workspace-page canvas').first.wait_for()
    no_overflow()
    page.screenshot(path=str(out / 'greenhouse-desktop.png'), full_page=False)
    page.get_by_role('button', name='点击进入数字孪生', exact=False).click()
    page.locator('.g3d-enter-card').wait_for()
    page.get_by_role('button', name='进入大棚', exact=False).click()
    page.locator('.g3d-inside-nav').wait_for()
    passed('3D: updated scene renders and original entrance walkthrough works')
    page.get_by_role('button', name='退出大棚', exact=False).click()
    page.locator('.g3d-scene-hint').wait_for()
    page.set_viewport_size({'width': 390, 'height': 844})
    no_overflow()
    page.screenshot(path=str(out / 'greenhouse-mobile.png'), full_page=False)
    passed('3D: return outside and mobile viewport remain usable')

    open_page('')
    page.locator('.pz-today-focus').wait_for()
    no_overflow()
    page.screenshot(path=str(out / 'dashboard-mobile.png'), full_page=True)
    assert not errors, errors
    assert not writes, writes
    passed('guest: no formal investigation writes, no JavaScript errors, mobile dashboard fits')
    browser.close()

report = {'passed': len(checks), 'checks': checks, 'javascript_errors': errors, 'formal_investigation_writes': writes}
(out / 'browser-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False), flush=True)
