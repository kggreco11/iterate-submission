"""Generate Git-tracked HTML reports locally from saved evidence (no inference)."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sepdesign.report_archive import publish, publish_legacy, publish_swarm, index


def migrate(root=ROOT):
    root = Path(root)
    paths = []
    # Regenerate published bundles in fresh clones, before applying newer local evidence.
    for p in sorted((root/'results').glob('*/*/*/*/report-data.json')):
        manifest = p.parent / 'manifest.json'
        if manifest.exists() and json.loads(manifest.read_text()).get('schema') == 'v3-analysis-bundle-v1':
            continue  # Comparison bundles use their own reproducible analysis scripts.
        data = json.loads(p.read_text())
        if data.get('schema') == 'team-report-v1':
            from sepdesign.team_report import publish_team
            paths.append(publish_team(data, root))
        else:
            paths.append((publish_swarm if 'agents' in data and 'config' in data else publish)(data, root))
    # Team snapshots can be published while running; missing evidence remains explicit.
    from sepdesign.team_report import payload, publish_team
    for p in sorted((root/'runs'/'teams').glob('*/*/*/config.json')):
        paths.append(publish_team(payload(p.parent), root))
    # Finalized modern exports, including earlier failed runs.
    for p in sorted((root/'runs').glob('*/*/*/*/report-data.json')):
        data = json.loads(p.read_text())
        if data.get('status',{}).get('state') in ('complete','failed') or data.get('summary',{}).get('status') in ('budget_exhausted','finish','turn_limit'):
            paths.append(publish(data, root))
    # Legacy self-contained reports retain their original schema.
    for p in sorted((root/'runs').glob('*/*/*/*/manifest.json')):
        m=json.loads(p.read_text()); report=p.parent/'reports/index.html'
        if not report.exists() or (p.parent/'report-data.json').exists() or m.get('status') not in ('finished','complete','failed'):
            continue
        summary=p.parent/'metrics/summary.json'
        paths.append(publish_legacy(report,m,json.loads(summary.read_text()) if summary.exists() else {},root))
    # Historical checked-in Opus runs use a separate replay JSON and log folder.
    for family in ('hc16v2-first-look', 'opus-5-5-dev-first-look', 'hc16v3-first-look'):
        for p in sorted((root/'results'/family).rglob('*.json')):
            replay=json.loads(p.read_text())
            if not isinstance(replay,dict) or 'trace' not in replay or 'solves_used' not in replay:
                continue
            logs=p.with_suffix('') if p.with_suffix('').is_dir() else p.parent
            summary=logs/'summary.json'
            if not summary.exists():continue
            def rows(name):
                f=logs/name
                return [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []
            paths.append(publish(dict(summary=json.loads(summary.read_text()), replay=replay,
                turns=rows('turns.jsonl'), usage=[{k:v.get(k) for k in ('elapsed_s','input_tokens','output_tokens','usd','usd_label')} for v in rows('usage.jsonl')],
                runtime={}, status={'state':'complete'}),root))
    for p in sorted((root/'runs').glob('*/shared-memory-*/*/*/metrics/summary.json')):
        from sepdesign.report import collect
        run=p.parent.parent;summary=json.loads(p.read_text())
        config=json.loads((run/'config.json').read_text())
        paths.append(publish_swarm(dict(summary=summary,config=config,
            agents={a:collect(run/'raw'/a) for a in summary['agents']}),root))
    index(root)
    return paths


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--controller', type=Path, help='Download completed VM single-agent evidence first')
    ap.add_argument('--swarm-controller', type=Path, help='Download completed VM swarm evidence and all agent reports')
    ap.add_argument('--data',type=Path,help='Publish a saved report-data JSON payload')
    a=ap.parse_args()
    if a.controller:
        from scripts.finalize_vm_report import finalize
        print(finalize(a.controller.resolve()),flush=True)
    if a.swarm_controller:
        from scripts.finalize_vm_report import finalize_swarm
        print(finalize_swarm(a.swarm_controller.resolve()),flush=True)
    if a.data:
        data=json.loads(a.data.read_text())
        print((publish_swarm if 'agents' in data and 'config' in data else publish)(data,ROOT),flush=True)
    for path in migrate():print(path)
    print('Index:', ROOT/'results/index.html')


if __name__=='__main__':main()
