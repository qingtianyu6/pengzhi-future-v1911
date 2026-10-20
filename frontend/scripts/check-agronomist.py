"""Run against the local Vite server: python frontend/scripts/check-agronomist.py."""
from datetime import datetime, timedelta
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

output = Path(__file__).resolve().parents[2] / '.run' / 'agronomist-check'
output.mkdir(parents=True, exist_ok=True)
errors = []
checks = []


def check(name, condition=True):
    assert condition, name
    checks.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:5173/platform/research?mode=guest&greenhouse_id=101', wait_until='networkidle')
    page.get_by_role('heading', name='AI 研究台').wait_for()
    page.get_by_role('button', name='记录作物观察').wait_for()
    page.wait_for_timeout(700)  # Allow the existing shell entry animation to settle before visual capture.
    page.screenshot(path=str(output/'archive-desktop.png'), full_page=True)
    check('research navigation and live archive load')
    page.get_by_role('tab', name='方案推演').click()
    page.get_by_role('button', name='生成方案比较').click()
    page.get_by_text('方案比较已保存', exact=True).wait_for()
    check('shared-baseline scenario comparison', page.locator('.ag-candidate-grid>div').count() == 3)
    page.get_by_role('button', name='围绕方案开展研究').click()
    page.get_by_placeholder('例如：清晨叶面潮湿，是否与灌溉和通风时间有关？').fill('清晨叶面湿润观察研究')
    page.get_by_role('button', name='生成研究草案').click()
    page.get_by_role('button', name='启动研究').click()
    page.get_by_role('button', name='添加关联观察').wait_for()
    check('study created with scenario snapshot and started')
    for phase, minutes, value in [('处理前', -90, '70'), ('处理后', -30, '35')]:
        page.get_by_role('button', name='添加关联观察').click()
        modal = page.get_by_role('dialog')
        modal.get_by_label('观察时间', exact=True).fill((datetime.now()+timedelta(minutes=minutes)).strftime('%Y-%m-%dT%H:%M'))
        modal.get_by_label('观察区域', exact=True).fill('东侧')
        modal.get_by_label('观察阶段', exact=True).locator('xpath=../..').click()
        page.locator('.ant-select-dropdown:visible').get_by_text(phase, exact=True).click()
        modal.get_by_label('观察内容', exact=True).fill(phase+'叶面湿润情况')
        modal.get_by_label('数值指标', exact=True).locator('xpath=../..').click()
        page.locator('.ant-select-dropdown:visible').get_by_text('叶面湿润比例（%）', exact=True).click()
        modal.get_by_label('观察数值', exact=True).fill(value)
        modal.get_by_role('button', name='保存观察').click()
        modal.wait_for(state='hidden')
    page.get_by_role('button', name='整理研究结果').click()
    page.get_by_role('cell', name='-35', exact=True).wait_for()
    check('before and after observations yield measured delta -35')
    page.screenshot(path=str(output/'research-desktop.png'), full_page=True)
    page.get_by_role('button', name='沉淀为技能').click()
    page.get_by_role('button', name='启用流程').wait_for()
    page.get_by_role('button', name='启用流程').click()
    page.get_by_role('button', name='用于目标编排').click()
    page.get_by_placeholder('例如：检查清晨湿度偏高问题，记录处理前后作物状态').fill('改善清晨湿度并记录作物变化')
    page.get_by_role('button', name='生成目标计划').click()
    page.get_by_role('button', name='生成农事任务').wait_for()
    page.get_by_role('button', name='生成农事任务').click()
    page.get_by_role('button', name='查看任务').first.wait_for()
    check('skill reuse and goal creates four real guest tasks', page.get_by_role('button', name='查看任务').count() == 4)
    page.reload(wait_until='networkidle')
    page.get_by_role('button', name='查看任务').first.wait_for()
    check('goal and task links survive refresh', page.get_by_role('button', name='查看任务').count() == 4)
    page.screenshot(path=str(output/'goals-desktop.png'), full_page=True)
    page.get_by_role('button', name='查看任务').first.click()
    page.wait_for_url('**/platform/production?**')
    check('task deep link reaches existing execution module')
    page.goto('http://127.0.0.1:5173/platform/research?greenhouse_id=102', wait_until='networkidle')
    page.get_by_role('tab', name='生产研究').click()
    page.get_by_text('创建第一个研究问题，开始积累本棚经验', exact=True).wait_for()
    check('switching greenhouses isolates research records')
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto('http://127.0.0.1:5173/platform/research?greenhouse_id=101', wait_until='networkidle')
    page.get_by_role('button', name='记录作物观察').wait_for()
    page.screenshot(path=str(output/'archive-mobile.png'), full_page=True)
    check('mobile page has no document overflow', page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
    page.get_by_role('tab', name='目标编排').click()
    page.get_by_role('button', name='查看任务').first.wait_for()
    page.screenshot(path=str(output/'goals-mobile.png'), full_page=True)
    check('mobile goals have no document overflow', page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
    check('no JavaScript page errors', not errors)
    browser.close()
output.joinpath('results.json').write_text(json.dumps({'checks': checks, 'page_errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': len(checks), 'page_errors': errors}, ensure_ascii=False))
