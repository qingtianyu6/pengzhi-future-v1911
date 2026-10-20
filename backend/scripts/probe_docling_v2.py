"""Run with an isolated Docling interpreter; DOCX parsing does not download PDF/OCR weights."""
from pathlib import Path
import json
import time
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat

root = Path(__file__).resolve().parents[2]
output = root / '.run' / 'v2-upgrade'
started = time.perf_counter()
try:
    result = DocumentConverter(allowed_formats=[InputFormat.DOCX]).convert(output / 'docling-fixture.docx')
    text = result.document.export_to_markdown()
    output.joinpath('docling-fixture.md').write_text(text, encoding='utf-8')
    checks = {'heading_preserved': 'Tomato observation' in text, 'table_preserved': 'East zone' in text and '70' in text and '35' in text}
    report = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
              'mode': 'isolated_docling_docx', 'elapsed_seconds': round(time.perf_counter()-started, 2),
              'pdf_ocr_tested': False, 'note': 'Synthetic DOCX table fixture; no claims about PDF OCR or agronomic accuracy.'}
except Exception as exc:
    report = {'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)[:500], 'pdf_ocr_tested': False}
output.joinpath('docling-probe-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
