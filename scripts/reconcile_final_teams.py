"""Verify final team evidence and refresh current canonical reports, offline."""
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sepdesign.team_report import payload, publish_team

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'e7ca677af0f04fdd44392d46010d59a731ece03d'


def reconcile():
    base = ROOT / 'results/final-dev002'
    # Model/run-ID directories are authoritative; older label-only snapshots stay historical.
    configs = list(base.glob('*/*/config.json')) + list((base/'opus-forced-dev000').glob('*/*/config.json'))
    rows = []
    navigation = (ROOT/'results/README.md').read_bytes()
    for path in sorted(configs):
        data = payload(path.parent)
        cfg, summary, board = data['config'], data['summary'], data['board']
        usage = [u for stream in data['usage'].values() for u in stream]
        agent_summaries = [json.loads(p.read_text()) for p in path.parent.glob('agents/*/summary.json')]
        reward = max([0.0] + [r['reward'] for r in board if r['valid']])
        curve = data['team_curve']
        checks = {
            'board_best': math.isclose(reward, summary['team_best'], abs_tol=1e-8),
            'agent_solves': sum(a['solves_used'] for a in agent_summaries) == summary['team_solves'],
            'usage_requests': len(usage) == summary['requests'],
            'logged_cost': math.isclose(sum(u['usd'] or 0 for u in usage), summary['usd_logged'], abs_tol=1e-7),
            'curve_endpoint': math.isclose(curve[-1][1], reward, abs_tol=1e-8),
            'observed_checkpoints': all(v is None or int(k) > summary['team_solves'] or math.isclose(v, max([0.0]+[point[1] for point in curve if point[0]<=int(k)]), abs_tol=1e-8) for k,v in summary['best_at'].items()),
        }
        if not all(checks.values()):
            raise ValueError((cfg['run_id'], checks))
        data['source'] = dict(commit=SOURCE, path=str(path.parent.relative_to(ROOT)))
        data['limitations'] = 'Single run; unequal team budgets and model thinking settings. The dev002 experiments predate migration-selection and managed-budget fixes; organization names describe intended configurations.' if cfg['task'].endswith('002') else 'Separate dev000 reference; do not pool with dev002. Forced continuation and free stopping are different runs, not a controlled replay.'
        report = publish_team(data, ROOT)
        row = dict(run_id=cfg['run_id'], task=cfg['task'], model=cfg['model'], preset=cfg['config']['preset'], agents=len(cfg['budgets']), allocation=sum(cfg['budgets'].values()), queries=summary['team_solves'], reward=reward, status=summary['status'], cost=summary['usd_cached_price_estimate'], board_records=len(board), usage_records=len(usage), source=str(path.parent.relative_to(ROOT)), report=str(report.relative_to(ROOT)), checks=checks)
        row['source_hashes'] = {str(p.relative_to(path.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.parent.rglob('*')) if p.is_file()}
        rows.append(row)
    (ROOT/'results/README.md').write_bytes(navigation)
    assert len(rows)==21 and len({r['run_id'] for r in rows})==21
    out = ROOT/'results/results-so-far/final-team-review.json'
    out.write_text(json.dumps(dict(source_commit=SOURCE, rows=rows), indent=2)+'\n')
    print(json.dumps(dict(runs=len(rows), board_records=sum(r['board_records'] for r in rows), usage_records=sum(r['usage_records'] for r in rows), checks=sum(len(r['checks']) for r in rows))))


if __name__ == '__main__':
    reconcile()
