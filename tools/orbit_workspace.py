"""Private department-orbit data. No embedded business data in the page template."""
import datetime as dt
import re
from zoneinfo import ZoneInfo
from marketing_workspace import next_schedule, text


def snapshot(root, manifest, states, outputs, jobs, job_states, reports, now=None):
    now = now or dt.datetime.now(ZoneInfo('Asia/Dubai'))
    centre = manifest.get('centre', {'id': 'moonshelter', 'name': 'Moon Shelter', 'folder': 'moonshelter'})
    departments = []
    for d in [centre] + manifest.get('departments', []):
        base = root / d['folder']
        resources = []
        for label, path in outputs.get(d['id'], []):
            p = base / path
            if p.exists():
                resources.append({'label': label, 'path': path, 'directory': p.is_dir()})
        roles = []
        for p in sorted((base / 'do').glob('*.md')):
            recipe = 'do/' + p.name
            roles.append({'id': p.stem, 'name': p.stem.replace('-', ' ').title(), 'recipe': recipe,
                          'next': next_schedule([s for s in d.get('schedule', []) if s['recipe'] == recipe], now),
                          'job': next((k for k, j in jobs.items() if j['dept'] == d['id'] and j['recipe'] == recipe), None)})
        available_jobs = [{ 'id': k, 'label': j['label'], 'description': j['what'], **job_states.get(k, {})}
                          for k, j in jobs.items() if j['dept'] == d['id']]
        departments.append({'id': d['id'], 'name': d['name'], 'engine': d.get('engine'), 'roles': roles,
                            'resources': resources, 'jobs': available_jobs, 'status': states.get(d['id'], {}),
                            'report': reports.get(d['id']), 'has_report': (base / 'live/report.md').is_file(),
                            'next': next_schedule(d.get('schedule', []), now)})
    folders = {d['id']: root / d['folder'] for d in manifest.get('departments', [])}
    functions = []
    for index, f in enumerate(manifest.get('functions', [])):
        if f['from'] not in folders or f['to'] not in folders:
            continue
        path = 'live/handoffs/' + f['to'] + '.md'
        p = folders[f['from']] / path
        content = text(p)
        stamp = re.search(r'\d{4}-\d{2}-\d{2}', content)
        functions.append({**f, 'id': str(index), 'path': path, 'available': p.is_file(),
                          'date': stamp.group() if stamp else ''})
    return {'checked': now.isoformat(), 'centre': centre['id'], 'departments': departments,
            'functions': functions, 'paused': manifest.get('paused', [])}
