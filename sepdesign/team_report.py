"""Publish team-run evidence without requiring a simulator or inventing missing plants."""
import hashlib
import html
import json
from pathlib import Path

from sepdesign.report_archive import ROOT, destination, index, write_json


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def payload(folder):
    folder = Path(folder)
    config = json.loads((folder / 'config.json').read_text())
    summary_path = folder / 'summary.json'
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    events = read_rows(folder / 'events.jsonl')
    rounds = [e for e in events if e.get('kind') == 'round']
    last = rounds[-1] if rounds else {}
    if not summary:
        summary = dict(status='incomplete snapshot', team_best=last.get('team_best'),
                       team_solves=last.get('team_solves'), usd_cached_price_estimate=last.get('usd_real'))
    return dict(schema='team-report-v1', config=config, summary=summary,
                board=read_rows(folder / 'board.jsonl'), events=events,
                team_curve=json.loads((folder/'team_curve.json').read_text()) if (folder/'team_curve.json').exists() else None,
                turns={p.parent.name: read_rows(p) for p in folder.glob('agents/*/turns.jsonl')},
                usage={p.parent.name: read_rows(p) for p in folder.glob('agents/*/usage.jsonl')})


def publish_team(data, root=ROOT):
    cfg, summary = data['config'], data['summary']
    run_id = cfg.get('run_id') or summary.get('run_id')
    if not run_id:
        raise ValueError('Team evidence must have a unique run_id')
    meta = dict(schema='report-bundle-v1', task=cfg['task'], model=cfg['model'], run_id=run_id,
                condition='team-' + cfg['config']['preset'], status=summary.get('status', 'incomplete snapshot'), report='index.html')
    dest = destination(meta, root)
    dest.mkdir(parents=True, exist_ok=True)
    write_json(dest / 'report-data.json', data)
    write_json(dest / 'summary.json', summary)
    esc = lambda v: html.escape(str(v))
    missing = 'Plant records were not saved in this historical snapshot; no replay can be reconstructed.' if not data['board'] else 'Saved plant records are available below.'
    warning = data.get('limitations', '')
    rows = ''.join('<tr>' + ''.join('<td>' + esc(r.get(k, '')) + '</td>' for k in ('id', 'agent', 'round', 'reward', 'valid', 'solves')) + '</tr>' for r in data['board'])
    plants = ''.join('<details><summary>' + esc(r.get('id')) + ' — ' + esc(r.get('agent')) + '</summary><pre>' + esc(r.get('view') or json.dumps(r.get('design'), indent=2)) + '</pre></details>' for r in data['board'])
    page = '<!doctype html><meta charset="utf-8"><title>Team run evidence</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto}td,th{padding:8px;text-align:left}pre{white-space:pre-wrap}details{margin:12px 0}</style>'
    page += '<h1>' + esc(cfg['model']) + ' · ' + esc(cfg['config']['preset']) + '</h1><p>Run: ' + esc(run_id) + '</p><p>Status: ' + esc(meta['status']) + '</p>'
    page += '<p>' + esc(missing) + '</p><p>' + esc(warning) + '</p><p><a href="report-data.json">Queryable source JSON</a> · <a href="summary.json">Summary JSON</a></p>'
    page += '<h2>Recorded summary</h2><pre>' + esc(json.dumps(summary, indent=2)) + '</pre><h2>Evaluated plants</h2><table><tr><th>ID</th><th>Agent</th><th>Round</th><th>Reward</th><th>Valid</th><th>Solves</th></tr>' + rows + '</table>' + plants
    (dest / 'index.html').write_text(page, encoding='utf-8')
    meta['sha256'] = {n: hashlib.sha256((dest/n).read_bytes()).hexdigest() for n in ('index.html', 'report-data.json', 'summary.json')}
    write_json(dest / 'manifest.json', meta)
    index(root)
    return dest / 'index.html'
