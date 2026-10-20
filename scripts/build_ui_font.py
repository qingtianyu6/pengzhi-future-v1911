"""Build the locally hosted UI font from an OFL Noto Sans SC variable TTF.

Usage: python scripts/build_ui_font.py path/to/NotoSansSC.ttf path/to/OFL.txt
Build-time only: requires fontTools; browser/runtime has no extra dependency.
"""
from pathlib import Path
import hashlib
import json
import sys
from fontTools import subset
from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1]
source, license_path = map(Path, sys.argv[1:3])
chars = set(range(32, 127)) | set(range(0x3000, 0x3040)) | set(range(0xFF00, 0xFFF0))
# GB2312's common simplified Chinese characters, plus current UI vocabulary.
for lead in range(0xB0, 0xF8):
    for trail in range(0xA1, 0xFF):
        try:
            chars.update(map(ord, bytes([lead, trail]).decode('gb2312')))
        except UnicodeDecodeError:
            pass
for path in (root / 'frontend/src').rglob('*'):
    if path.suffix in {'.tsx', '.ts', '.css'}:
        chars.update(ord(c) for c in path.read_text(encoding='utf-8') if ord(c) > 127)
font = TTFont(source)
version = font['name'].getDebugName(5)
options = subset.Options()
options.flavor = 'woff'
options.layout_features = ['*']
subsetter = subset.Subsetter(options=options)
subsetter.populate(unicodes=chars)
subsetter.subset(font)
font.flavor = 'woff'
out = root / 'frontend/public/fonts'
out.mkdir(exist_ok=True)
font.save(out / 'pengzhi-ui-sc.woff')
(out / 'OFL-NotoSansSC.txt').write_bytes(license_path.read_bytes())
(out / 'font-manifest.json').write_text(json.dumps({
    'family': 'Noto Sans SC', 'version': version, 'license': 'SIL OFL 1.1',
    'source': 'https://github.com/google/fonts/tree/main/ofl/notosanssc',
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'output_sha256': hashlib.sha256((out / 'pengzhi-ui-sc.woff').read_bytes()).hexdigest(),
    'glyphs': len(font.getBestCmap()), 'weight_axis': '100–900',
    'subset': 'GB2312 Chinese + current frontend vocabulary + Latin/punctuation; system fallback for other characters',
}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Generated {out.name}/pengzhi-ui-sc.woff: {(out / "pengzhi-ui-sc.woff").stat().st_size} bytes')
