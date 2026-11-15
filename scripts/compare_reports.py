"""Add an explicit single-agent comparator to a portable swarm report."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sepdesign.report_archive import publish_swarm
from sepdesign.swarm_report import single_metrics


def compare(single_path, swarm_path, root=ROOT):
    single_path,swarm_path=Path(single_path),Path(swarm_path)
    single=json.loads(single_path.read_text())
    swarm=json.loads(swarm_path.read_text())
    state = single.get('status', {}).get('state')
    single_complete = state == 'complete' if state else single['summary'].get('status') in {
        'budget_exhausted', 'finish', 'turn_limit'}
    if not single_complete or swarm['summary'].get('status') not in {
            'complete', 'all_finished_or_exhausted', 'round_limit'}:
        raise ValueError('Comparison requires completed single-agent and swarm runs')
    swarm['comparison']=dict(single=single_metrics(single),
        single_payload_sha256=hashlib.sha256(single_path.read_bytes()).hexdigest())
    return publish_swarm(swarm,root)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--single',type=Path,required=True)
    ap.add_argument('--swarm',type=Path,required=True)
    args=ap.parse_args()
    print(compare(args.single,args.swarm))
