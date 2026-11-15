"""Build a discoverable run directory without moving an active writer's files."""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def organize(source):
    source = source.resolve()
    config = json.loads((source/'config.json').read_text())
    task = config.get('task_id', 'hc12_dev_000')
    dest = ROOT/'runs'/task/'single-agent'/config['model']/config['run_id']
    for name in ('raw', 'metrics', 'reports'):
        (dest/name).mkdir(parents=True, exist_ok=True)
    # Snapshot only known non-secret outputs. Never include command payloads or env files.
    names = ['trajectory.jsonl', 'usage.jsonl', 'request-timing.jsonl', 'failure.json']
    files = [source/n for n in names if (source/n).exists()]
    files += list(source.glob('request-*.json')) + list(source.glob('response-*.json')) + list(source.glob('error-*.json'))
    for p in files:
        target = dest/'raw'/p.name
        if p.resolve() != target.resolve(): shutil.copy2(p, target)
    for name in ('config.json', 'source-manifest.json'):
        if (source/name).exists(): shutil.copy2(source/name, dest/name)
    for script in ('price_luna_pilot.py', 'build_pilot_report.py'):
        subprocess.run([sys.executable, str(ROOT/'scripts'/script), str(source)], check=True, capture_output=True)
    for name in ('pricing.json', 'summary.json'):
        if (source/name).exists(): shutil.copy2(source/name, dest/'metrics'/name)
    shutil.copy2(source/'report.html', dest/'reports'/'index.html')
    complete = (source/'summary.json').exists()
    manifest = dict(run_id=config['run_id'], task=task, condition='single-agent', model=config['model'],
        status='finished' if complete else ('failed' if (source/'failure.json').exists() else 'in-progress snapshot'),
        source_directory=str(source), updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        simulator_evidence='Still on Azure VM; not yet exported',
        notes='Raw files are a snapshot while running. Source directory remains authoritative until finalized.')
    (dest/'manifest.json').write_text(json.dumps(manifest, indent=2))
    entries=[]
    for p in sorted((ROOT/'runs').glob('*/*/*/*/manifest.json')):
        m=json.loads(p.read_text()); rel=p.parent.relative_to(ROOT/'runs')
        entries.append(f"| {m['run_id']} | {m['task']} | {m['condition']} | {m['model']} | {m['status']} | [Report]({rel}/reports/index.html) |")
    (ROOT/'runs'/'README.md').write_text('# Local experiment runs\n\nGenerated index; raw artifacts stay Git-ignored.\n\n| Run | Task | Condition | Model | Status | Report |\n|---|---|---|---|---|---|\n'+'\n'.join(entries)+'\n\nLegacy integration-smoke contains a scripted mock test, not an experimental result.\n')
    if complete:
        sys.path.insert(0, str(ROOT))
        from sepdesign.report_archive import publish_legacy
        publish_legacy(dest/'reports/index.html', manifest, json.loads((dest/'metrics/summary.json').read_text()), ROOT)
    print(dest)
    return dest

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('source', type=Path)
    organize(ap.parse_args().source)
