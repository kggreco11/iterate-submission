"""Publish portable report bundles under results/; raw run data stays private/local."""
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def segment(value):
    value = str(value)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('Unsafe report path component')
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def destination(metadata, root):
    return Path(root) / 'results' / Path(*(segment(metadata[k]) for k in ('task', 'condition', 'model', 'run_id')))


def index(root=ROOT):
    root = Path(root)
    folder = root / 'results'
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(folder.glob('*/*/*/*/manifest.json')):
        m = json.loads(path.read_text())
        if m.get('schema') not in ('report-bundle-v1', 'v3-analysis-bundle-v1') or not (path.parent / 'index.html').exists():
            continue
        rel = (path.parent / 'index.html').relative_to(folder).as_posix()
        rows.append((m, rel))
    header = '# Experiment reports\n\nCanonical, Git-tracked HTML reports and supporting data. Raw logs and download caches stay in `runs/`.\n\n'
    markdown = header + '| Run | Task | Condition | Model | Status | HTML |\n|---|---|---|---|---|---|\n'
    body = []
    for m, rel in rows:
        values = [str(m[k]) for k in ('run_id', 'task', 'condition', 'model', 'status')]
        markdown += '| ' + ' | '.join(v.replace('|', '\\|').replace('\n',' ') for v in values) + f' | [Open]({rel}) |\n'
        body.append('<tr>' + ''.join('<td>' + html.escape(v) + '</td>' for v in values) + f'<td><a href="{html.escape(rel)}">Open report</a></td></tr>')
    markdown += '\nOther results directories contain historical qualification/baseline evidence; only standardized report bundles appear above. GitHub shows HTML source; download/open it locally or use a separately configured static host.\n'
    (folder / 'README.md').write_text(markdown, encoding='utf-8')
    (folder / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Experiment reports</title><style>body{font:15px system-ui;padding:32px}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}table{border-collapse:collapse}</style><h1>Experiment reports</h1><p>Saved evidence, not live runs. Failed runs are labeled. Raw logs remain local.</p><table><tr><th>Run</th><th>Task</th><th>Condition</th><th>Model</th><th>Status</th><th>HTML</th></tr>' + ''.join(body) + '</table>', encoding='utf-8')
    return folder / 'index.html'


def publish(data, root=ROOT, condition='single-agent'):
    """Render an exported report payload locally and publish only report evidence."""
    from sepdesign.report import build
    # Exclude runtime deployment configuration and arbitrary top-level fields.
    runtime = data.get('runtime', {})
    data = {key: data.get(key, default) for key, default in
            [('summary', {}), ('replay', {}), ('turns', []), ('usage', []), ('status', {})]}
    data['runtime'] = {k:runtime[k] for k in ('phase_seconds','phase_counts','service','wall_s') if k in runtime}
    s, replay = data['summary'], data['replay']
    if not replay or not s.get('run_id'):
        raise ValueError('A saved replay and run summary are required')
    metadata = dict(schema='report-bundle-v1', run_id=s['run_id'], task=s.get('task') or replay['task'],
                    model=s.get('model', 'unknown'), condition=condition,
                    status=data['status'].get('state') or s.get('status', 'unknown'),
                    stop_reason=s.get('status'), report='index.html',
                    evidence='report-data.json; full raw simulator logs may remain on the execution host')
    dest = destination(metadata, root)
    dest.mkdir(parents=True, exist_ok=True)
    write_json(dest / 'report-data.json', data)
    write_json(dest / 'summary.json', s)
    build(dest, data, archive=False).replace(dest / 'index.html')
    metadata['sha256'] = {name: hashlib.sha256((dest / name).read_bytes()).hexdigest()
                          for name in ('index.html', 'report-data.json', 'summary.json')}
    write_json(dest / 'manifest.json', metadata)
    index(root)
    return dest / 'index.html'


def publish_legacy(report, metadata, summary, root=ROOT):
    """Keep older self-contained pilot reports without inventing missing replay data."""
    metadata = {k: metadata[k] for k in ('run_id', 'task', 'condition', 'model', 'status')}
    dest = destination(metadata, root)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'index.html').write_bytes(Path(report).read_bytes())
    write_json(dest / 'summary.json', summary)
    metadata.update(schema='report-bundle-v1', report='index.html',
                    evidence='Legacy self-contained HTML and summary; no standardized report-data payload available',
                    sha256={n: hashlib.sha256((dest/n).read_bytes()).hexdigest() for n in ('index.html','summary.json')})
    write_json(dest / 'manifest.json', metadata)
    index(root)
    return dest / 'index.html'


def publish_swarm(data, root=ROOT):
    """Publish an aggregate and independently reproducible per-agent reports."""
    summary, config = data['summary'], data['config']
    metadata = dict(schema='report-bundle-v1', run_id=summary['run_id'], task=config['task'],
                    condition='shared-memory-' + str(len(summary['agents'])), model=config['model'],
                    status=summary['status'], report='index.html')
    dest = destination(metadata, root)
    dest.mkdir(parents=True, exist_ok=True)
    # Preserve the explicitly chosen comparator when refreshing the same run.
    previous = dest / 'report-data.json'
    if 'comparison' not in data and previous.exists():
        comparison = json.loads(previous.read_text()).get('comparison')
        if comparison:
            data = {**data, 'comparison': comparison}
    from sepdesign.swarm_report import render
    rendered = render(data)  # Validate comparator identity before replacing evidence.
    for agent, payload in data['agents'].items():
        segment(agent)
        folder = dest / 'agents' / agent
        # Render here directly; individual agents are not independent team trials.
        from sepdesign.report import build
        folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / 'report-data.json', payload)
        build(folder, payload, archive=False).replace(folder / 'index.html')
    write_json(dest / 'summary.json', summary)
    write_json(dest / 'report-data.json', data)
    (dest / 'index.html').write_text(rendered, encoding='utf-8')
    metadata['sha256'] = {str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in dest.rglob('*') if p.is_file() and p.name!='manifest.json'}
    write_json(dest / 'manifest.json', metadata)
    index(root)
    return dest / 'index.html'
