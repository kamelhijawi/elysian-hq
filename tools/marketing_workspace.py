"""Read-only, private marketing workspace assembled from department source files."""
import datetime as dt
import pathlib
import re
from zoneinfo import ZoneInfo

DUBAI = ZoneInfo('Asia/Dubai')


def text(path):
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def plain(value):
    return re.sub(r'\*\*|`', '', value).strip()


def rows(value, columns):
    """Accept both Markdown tables and dated pipe logs; skip prose and headers."""
    result = []
    for line in value.splitlines():
        cells = [c.strip() for c in re.split(r'(?<!\\)\|', line.strip().strip('|'))]
        if len(cells) >= len(columns) - 1 and re.fullmatch(r'\d{4}-\d{2}-\d{2}', cells[0]):
            cells += [''] * (len(columns) - len(cells))
            result.append(dict(zip(columns, cells)))
    return result


def section(value, prefix):
    found, output = False, []
    for line in value.splitlines():
        if line.startswith('## '):
            if found:
                break
            found = line[3:].lower().startswith(prefix.lower())
        elif found:
            output.append(line)
    return '\n'.join(output).strip()


def next_schedule(schedules, now):
    candidates = []
    for s in schedules:
        for offset in range(8):
            at = (now + dt.timedelta(days=offset)).replace(hour=s['hour'], minute=s['minute'], second=0, microsecond=0)
            if (at.weekday() + 1) % 7 in s['days'] and at > now:
                candidates.append((at, s['label']))
                break
    if not candidates:
        return None
    at, label = min(candidates)
    return {'at': at.isoformat(), 'label': label}


def snapshot(root, manifest, states, queue, job_states, now=None):
    now = now or dt.datetime.now(DUBAI)
    today = now.date().isoformat()
    base = root / 'marketing-brain'
    live = base / 'live'
    ideas = rows(text(live / 'ideas.md'), ['date', 'name', 'hook', 'audience', 'proof', 'cost', 'status', 'result'])
    ideas = list({i['name']: i for i in ideas}.values())
    production = rows(text(live / 'production.md'), ['date', 'id', 'name', 'type', 'channel', 'due', 'owner', 'status', 'result'])
    production = list({r['id']: r for r in production if re.fullmatch(r'[VB]-\d+', r['id'])}.values())
    for r in production:
        r['state'] = r['status'].split()[0] if r['status'] else 'UNKNOWN'
        r['unassigned'] = not r['owner'] or '<<' in r['owner']
        try:
            due = dt.date.fromisoformat(r['due'])
        except ValueError:
            due = None
        r['overdue'] = r['state'] == 'OPEN' and due is not None and due < now.date()
    actions = rows(text(live / 'actions.md'), ['date', 'owner', 'name', 'due', 'status', 'result'])
    report = text(live / 'report.md')
    stamp = re.search(r'\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?', report.splitlines()[0] if report else '')
    findings = [plain(re.sub(r'^\d+[.)]\s*', '', l)) for l in section(report, 'Three findings').splitlines() if re.match(r'^\d+[.)]', l)]
    decisions = [plain(re.sub(r'^\d+[.)]\s*', '', l)) for l in section(report, 'Needs a decision').splitlines() if re.match(r'^\d+[.)]', l)]
    report_status = next((plain(l[3:].replace('Status:', '').strip()) for l in report.splitlines() if l.startswith('## Status')), 'No report')
    plans = []
    for p in sorted((live / 'plans').glob('*.md'), reverse=True):
        content = text(p)
        title = next((plain(l[2:]) for l in content.splitlines() if l.startswith('# ')), p.stem)
        headings = [plain(l[3:]) for l in content.splitlines() if l.startswith('## ')]
        summary = next((plain(l.split('**Summary:**', 1)[1]) for l in content.splitlines() if '**Summary:**' in l), '')
        plans.append({'title': title, 'path': str(p.relative_to(base)), 'date': p.name[:10], 'outline': headings,
                      'summary': summary or plain(section(content, '1. Objective')),
                      'blanks': len(re.findall(r'<<\s*fill', content)), 'template': 'template' in title.lower()})
    posts = []
    for r in queue:
        if not re.fullmatch(r'P-\d+', r.get('id', '')):
            continue
        content = text(live / 'posts' / (r['id'] + '.md'))
        posts.append({**r, 'body': section(content, 'Post'), 'carousel': (live / 'posts' / (r['id'] + '-carousel.pdf')).is_file()})
    dept = next((d for d in manifest.get('departments', []) if d['id'] == 'marketing'), {})
    schedules = dept.get('schedule', [])
    specs = [('market-analyst', 'Market analyst', 'Find the market signals worth acting on.', 'live/week.md', None),
             ('creative-director', 'Creative director', 'Turn evidence into a focused idea bank.', 'live/ideas.md', None),
             ('campaign-planner', 'Campaign planner', 'Set the audience, timeline and measure of success.', 'live/plans', None),
             ('media-planner', 'Media planner', 'Outline channels, budgets and delivery.', 'live/media-plans.md', None),
             ('production-director', 'Production director', 'Prepare scripts, shot lists and work orders.', 'live/production.md', 'marketing'),
             ('publisher', 'Publisher', 'Draft LinkedIn posts for your review.', 'live/publish-queue.md', 'publisher'),
             ('reporter', 'Channel reporter', 'Connect channel performance to the next plan.', 'live/report.md', None)]
    roles = []
    for slug, name, description, output, job in specs:
        recipe = 'do/' + slug + '.md'
        if not (base / recipe).is_file():
            continue
        roles.append({'id': slug, 'name': name, 'description': description, 'recipe': recipe, 'output': output,
                      'directory': (base / output).is_dir(), 'job': job if job in job_states else None,
                      'next': next_schedule([s for s in schedules if s['recipe'] == recipe], now)})
    handoffs = []
    for name, folder in [('CRM source quality', 'crm'), ('Sales demand signals', 'brain')]:
        p = root / folder / 'live/handoffs/marketing.md'
        value = text(p)
        handoffs.append({'name': name, 'dept': 'sales' if folder == 'brain' else 'crm', 'path': 'live/handoffs/marketing.md',
                         'available': p.is_file(), 'date': (re.search(r'\d{4}-\d{2}-\d{2}', value).group() if re.search(r'\d{4}-\d{2}-\d{2}', value) else '')})
    sources = {name: (live / name).is_file() for name in ['ideas.md', 'production.md', 'publish-queue.md', 'report.md', 'actions.md']}
    return {'checked': now.isoformat(), 'today': today, 'ideas': ideas, 'production': production, 'actions': actions,
            'plans': plans, 'posts': posts, 'roles': roles, 'handoffs': handoffs, 'sources': sources,
            'report': {'date': stamp.group() if stamp else '', 'findings': findings, 'decisions': decisions, 'status': report_status},
            'department': states.get('marketing', {}), 'next': next_schedule(schedules, now), 'jobs': job_states,
            'counts': {'ideas': sum(i['status'] not in ('DROPPED', 'USED') for i in ideas),
                       'open': sum(r['state'] == 'OPEN' for r in production),
                       'overdue': sum(r['overdue'] for r in production),
                       'unassigned': sum(r['unassigned'] and r['state'] == 'OPEN' for r in production),
                       'ready': sum(p['status'] == 'READY' for p in posts),
                       'approved': sum(p['status'] == 'APPROVED' for p in posts),
                       'posted': sum(p['status'] == 'POSTED' for p in posts)}}
