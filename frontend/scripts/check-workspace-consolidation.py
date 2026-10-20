"""Real browser checks for workspace consolidation; no API mocks or business writes."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.run/workspace-consolidation'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:5173'
checks, errors = [], []


def check(name, action):
    try:
        action()
        row = {'check': name, 'passed': True}
    except Exception as exc:
        row = {'check': name, 'passed': False, 'error': str(exc)[:1500]}
    checks.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.set_default_timeout(30000)
    page.on('pageerror', lambda error: errors.append(str(error)))

    def open_page(route='', extra=''):
        page.goto(f'{BASE}/platform{route}?mode=guest&greenhouse_id=101{extra}', wait_until='domcontentloaded')
        page.locator('.pz-workspace-page h1, .pz-workspace-page h2, .pz-workspace-page canvas').first.wait_for()

    main = ['生产工作台', '大棚管理', '三维大棚', '环境监测', '智能诊断', '生产管理', '知识社区']
    routes = [('', '生产工作台'), ('/data', '大棚管理'), ('/3d', '三维大棚'),
              ('/environment', '环境监测'), ('/investigate', '智能诊断'), ('/diagnosis', '智能诊断'),
              ('/disease-time-machine', '智能诊断'), ('/production', '生产管理'),
              ('/autonomy', '生产管理'), ('/research', '生产管理'),
              ('/knowledge', '知识社区'), ('/news', '知识社区'), ('/forum', '知识社区')]

    def route_check(route, group):
        open_page(route)
        require(page.locator('.exact-side-menu .ant-menu-item').all_text_contents() == main, 'main navigation is not seven workspaces including the independent 3D entry')
        require(page.locator('.exact-side-menu .ant-menu-item-selected').text_content().strip() == group, 'incorrect workspace selection')
        links = page.locator('.pz-section-links')
        if links.count():
            require(links.locator('[aria-current="page"]').count() == 1, 'secondary selection missing or duplicated')
        require(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'horizontal page overflow')

    for route, group in routes:
        check('desktop route ' + (route or '/'), lambda r=route, g=group: route_check(r, g))

    def main_navigation():
        open_page('', '&tab=alerts&view=history&task_id=77')
        for label, suffix in [('大棚管理', '/data'), ('环境监测', '/environment'), ('智能诊断', '/investigate'),
                              ('生产管理', '/production'), ('知识社区', '/knowledge'), ('生产工作台', '')]:
            page.locator('.exact-side-menu').get_by_text(label, exact=True).click()
            page.wait_for_url(f'**/platform{suffix}?**')
            require('greenhouse_id=101' in page.url and 'mode=guest' in page.url, 'shared context lost')
            require(all(key not in page.url for key in ['tab=', 'view=', 'task_id=']), 'unrelated page filter leaked')
    check('primary entries and context isolation', main_navigation)

    def diagnosis_history():
        open_page('/investigate')
        nav = page.get_by_role('navigation', name='智能诊断子功能', exact=True)
        nav.get_by_role('link', name='识别与复核记录', exact=True).click()
        page.get_by_role('heading', name='识别与复核记录', exact=True).wait_for()
        require('view=history' in page.url, 'history query missing')
        require(nav.locator('[aria-current="page"]').inner_text() == '识别与复核记录', 'history incorrectly selected')
        nav.get_by_role('link', name='叶片识别', exact=True).click()
        page.get_by_role('heading', name='病害辅助识别', exact=True).wait_for()
        require('view=' not in page.url, 'history filter leaked into identify')
        page.go_back()
        page.get_by_role('heading', name='识别与复核记录', exact=True).wait_for()
    check('diagnosis history, identify and browser back', diagnosis_history)

    def assets():
        open_page('/data')
        require(page.locator('.v17-asset-shell').count() == 1 and page.locator('.v17-connect-grid').count() == 0, 'asset and connection views mixed')
        page.get_by_role('button', name='设备与数据接入', exact=True).click()
        page.locator('.v17-connect-grid').wait_for()
        require(page.locator('.v17-asset-shell').count() == 0, 'asset view still displayed')
        page.get_by_role('button', name='大棚档案与批次', exact=True).click()
        page.locator('.v17-asset-shell').wait_for()
    check('assets and equipment are distinct usable views', assets)

    def settings():
        page.get_by_role('button', name='系统设置', exact=True).click()
        page.get_by_role('button', name='AI 能力与运行', exact=True).click()
        page.wait_for_url('**/platform/ai-quality?**')
        page.get_by_role('heading', name='AI 能力与运行', exact=True).wait_for()
        require(page.locator('.exact-side-menu .ant-menu-item-selected').count() == 0, 'AI operations incorrectly presented as production')
        require('greenhouse_id=101' in page.url, 'settings navigation lost greenhouse')
    check('AI operations is accessible from settings', settings)

    def search():
        page.keyboard.press('Control+k')
        field = page.get_by_label('搜索平台功能', exact=True)
        field.fill('复核')
        page.get_by_role('button', name='识别与复核记录 回看识别结果与人工复核记录', exact=False).click()
        page.get_by_role('heading', name='识别与复核记录', exact=True).wait_for()
        require(page.url.count('?') == 1 and 'view=history' in page.url, 'malformed URL in search result')
        page.keyboard.press('Control+k')
        field.fill('no-match-928374')
        page.get_by_text('没有找到相关功能，试试“环境”“研究”或“论坛”。', exact=True).wait_for()
        page.keyboard.press('Escape')
    check('global search finds nested view and handles empty results', search)

    def old_link():
        page.goto(BASE + '/platform/alerts?mode=guest&greenhouse_id=101', wait_until='domcontentloaded')
        page.wait_for_url('**/platform/environment?**')
        page.get_by_role('button', name='预警与处置', exact=True).wait_for()
        require('tab=alerts' in page.url and 'greenhouse_id=101' in page.url, 'legacy alias lost context')
    check('legacy alert URL retained', old_link)

    for route, group in [('/investigate', '智能诊断'), ('/news', '知识社区'), ('/production', '生产管理'), ('/data', '大棚管理'), ('/3d', '三维大棚')]:
        def mobile(r=route, g=group):
            page.set_viewport_size({'width': 390, 'height': 844})
            route_check(r, g)
            page.get_by_role('button', name='展开侧边栏', exact=True).click()
            page.locator('.exact-side-menu').get_by_text('环境监测', exact=True).click()
            page.wait_for_url('**/platform/environment?**')
            page.get_by_role('button', name='展开侧边栏', exact=True).wait_for()
            require(page.locator('.mobile-sider-backdrop').count() == 0, 'mobile menu did not close')
        check('mobile navigation ' + route, mobile)

    def scene():
        page.set_viewport_size({'width': 1440, 'height': 1000})
        open_page('/3d')
        size = page.locator('.pz-workspace-page').bounding_box()
        require(size and size['height'] > 500, '3D scene lost usable height')
        page.locator('.exact-side-menu').get_by_text('大棚管理', exact=True).click()
        page.get_by_role('heading', name='每一座大棚，管理有序', exact=True).wait_for()
    check('3D usable viewport and return to asset management', scene)

    for name, route, width in [('overview-desktop', '', 1440), ('knowledge-desktop', '/knowledge', 1440),
                               ('diagnosis-mobile', '/investigate', 390), ('greenhouse-3d', '/3d', 1440)]:
        page.set_viewport_size({'width': width, 'height': 1000 if width > 600 else 844})
        open_page(route)
        page.screenshot(path=str(OUT / f'{name}.png'), full_page=True)

    def auth():
        fresh = browser.new_page()
        fresh.goto(BASE + '/platform/research?greenhouse_id=101', wait_until='domcontentloaded')
        fresh.wait_for_url('**/login?next=**')
        fresh.close()
    check('unauthenticated direct link still requires sign-in', auth)
    browser.close()

report = {'checks': checks, 'javascript_errors': errors, 'passed': sum(r['passed'] for r in checks), 'failed': sum(not r['passed'] for r in checks)}
(OUT / 'browser-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False), flush=True)
assert report['failed'] == 0 and not errors
