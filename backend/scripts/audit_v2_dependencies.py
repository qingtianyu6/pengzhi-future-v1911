"""Record public package metadata, installed licenses, upstream state, and OSV results."""
from importlib import metadata
from pathlib import Path
import json
import httpx

root = Path(__file__).resolve().parents[2]
out = root / '.run' / 'v2-upgrade'
out.mkdir(parents=True, exist_ok=True)
packages = ['feedparser', 'trafilatura', 'python-docx', 'defusedxml', 'pypdf', 'lxml']
report = {'packages': [], 'upstream': [], 'vulnerability_check': {}}
with httpx.Client(timeout=20, follow_redirects=True) as client:
    for name in packages:
        d = metadata.distribution(name)
        entry = {'name': name, 'installed_version': d.version, 'requires_python': d.metadata.get('Requires-Python'),
                 'license_expression': d.metadata.get('License-Expression'), 'license': d.metadata.get('License', '')[:300],
                 'license_files': [str(f) for f in d.files or [] if 'license' in str(f).lower()][:15]}
        try:
            p = client.get(f'https://pypi.org/pypi/{name}/json'); p.raise_for_status(); data = p.json()
            entry.update(latest_version=data['info']['version'], installed_release_time=max(f['upload_time_iso_8601'] for f in data['releases'][d.version]))
        except Exception as e: entry['metadata_error'] = type(e).__name__
        report['packages'].append(entry)
    for repo in ['apache/answer', 'kurtmckee/feedparser', 'adbar/trafilatura', 'docling-project/docling', 'langfuse/langfuse']:
        try:
            response = client.get('https://api.github.com/repos/' + repo); response.raise_for_status(); data = response.json()
            report['upstream'].append({'repository': repo, 'archived': data['archived'], 'pushed_at': data['pushed_at'],
                                      'license': (data.get('license') or {}).get('spdx_id'), 'language': data['language']})
        except Exception as e: report['upstream'].append({'repository': repo, 'error': type(e).__name__})
    try:
        queries = [{'package': {'name': p['name'], 'ecosystem': 'PyPI'}, 'version': p['installed_version']} for p in report['packages']]
        response = client.post('https://api.osv.dev/v1/querybatch', json={'queries': queries}); response.raise_for_status()
        report['vulnerability_check'] = {'service': 'OSV', 'results': [{'package': p['name'], 'vulnerabilities': row.get('vulns', [])} for p, row in zip(report['packages'], response.json()['results'])],
                                         'scope': 'Selected direct parser dependencies only; not a full application security certification'}
    except Exception as e: report['vulnerability_check'] = {'status': 'unavailable', 'reason': type(e).__name__}
out.joinpath('dependency-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'packages': len(report['packages']), 'upstream': len(report['upstream']), 'osv_status': report['vulnerability_check'].get('status', 'queried')}, ensure_ascii=False))
