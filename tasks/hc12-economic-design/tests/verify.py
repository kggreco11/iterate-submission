"""Replay a harness-owned run state through the validity checker, without new solves.

Input must be the simulator-side state.json, never an agent-authored score file.
"""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from sepdesign import make_env
from sepdesign.service import SolveService


def verify(state_path, output_dir):
    state = json.loads(Path(state_path).read_text())
    class NoNewSolves:
        name = 'recorded-chemsep'
        def solve_column(self, case):
            raise ValueError('Missing recorded simulator evidence for submitted design')
    service = SolveService(NoNewSolves())
    service.cache = {(tuple(q[0]), *q[1:]): result for q, result in state['cache']}
    task = json.loads((ROOT/'tasks/hc12_dev_000.json').read_text())
    env = make_env(task, service, budget=50)
    env.design = state['best'][1]
    result = env.evaluate()
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    (out/'validation.json').write_text(json.dumps(result['validation'], indent=2))
    reward = result['reward'] if result['valid'] else 0.0
    (out/'reward.json').write_text(json.dumps({'reward':reward}))
    return result

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('state'); ap.add_argument('--output', default='/logs/verifier')
    args = ap.parse_args()
    verify(args.state, args.output)
