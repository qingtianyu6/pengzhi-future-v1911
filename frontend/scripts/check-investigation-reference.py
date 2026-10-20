"""Check measured layout anchors against the approved 1586x992 reference.

Uses a real fresh guest investigation; no fabricated context or API responses.
These geometry checks do not imply pixel-identical photos, glyphs, or results.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

out=Path(__file__).resolve().parents[2]/'.run/investigation-fidelity'
out.mkdir(parents=True,exist_ok=True)
anchors=[
    ('.exact-sider','width',233,0),
    ('.exact-header','height',44,0),
    ('.exact-header','x',233,0),
    ('.iw-hero','x',267,0),
    ('.iw-entry','y',190,1),
    ('.iw-context-strip','y',382,4),
    ('.iw-candidates','x',660,3),
    ('.iw-autonomy','x',1089,1),
    ('.iw-autonomy','y',190,1),
    ('.iw-autonomy','width',467,2),
    ('.iw-autonomy','height',630,2),
    ('.iw-progress','y',838,2),
]
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1586,'height':992},device_scale_factor=1,timezone_id='Asia/Shanghai')
    page.goto('http://127.0.0.1:5173/platform/investigate?mode=guest&greenhouse_id=101')
    page.get_by_label('农业问题',exact=True).fill('东侧番茄叶片出现黄斑，中央传感器湿度正常。')
    page.get_by_role('button',name='开始调查 →',exact=True).click()
    page.wait_for_function("!!JSON.parse(sessionStorage.getItem('pengzhi-investigations-v1'))?.[0]?.payload.autonomy_runs?.length")
    page.evaluate('document.fonts.ready')
    results=[]
    for selector,dimension,expected,tolerance in anchors:
        actual=page.locator(selector).bounding_box()[dimension]
        assert abs(actual-expected)<=tolerance, f'{selector}.{dimension}: {actual} vs {expected} ±{tolerance}'
        results.append({'selector':selector,'dimension':dimension,'actual':actual,'reference':expected,'tolerance':tolerance})
    page.screenshot(path=str(out/'actual-1586x992.png'))
    (out/'reference-results.json').write_text(json.dumps({'passed':len(results),'anchors':results},ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
print(f'{len(results)} reference layout anchors passed')
