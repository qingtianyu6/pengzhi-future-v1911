"""Create a WOFF2 copy of the existing OFL font; preserve its glyphs and weight axis."""
from pathlib import Path
import hashlib
import json
from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1]
folder = root / 'frontend/public/fonts'
source = folder / 'pengzhi-ui-sc.woff'
target = folder / 'pengzhi-ui-sc.woff2'
font = TTFont(source, recalcTimestamp=False)
font.flavor = 'woff2'
font.save(target)
with TTFont(source) as original, TTFont(target) as compressed:
    assert original.getBestCmap() == compressed.getBestCmap(), 'Character coverage changed'
    assert original.getGlyphOrder() == compressed.getGlyphOrder(), 'Glyph order changed'
    assert [(a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in original['fvar'].axes] == [(a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in compressed['fvar'].axes], 'Weight axis changed'
manifest = folder / 'font-manifest.json'
data = json.loads(manifest.read_text(encoding='utf-8'))
data['woff2'] = {'file': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'bytes': target.stat().st_size, 'source_bytes': source.stat().st_size, 'glyph_coverage_verified': True, 'weight_axis_verified': True}
manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(data['woff2']))
