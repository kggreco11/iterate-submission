"""Exercise task-configured controls offline; optionally probe live past.dev isolation.

No model API or ChemSep is used. The live probe writes one clearly labeled
compact canary in its own audience and verifies a new audience cannot recall it.
"""
import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.llm_agent import load_dotenv
from sepdesign.experiments import run_controls
from sepdesign.ledger import Ledger
from sepdesign.service import make_service
from sepdesign.swarm_context import compact_record
from sepdesign.swarm_memory import NoMemory, ExactMemory, PastMemory
from sepdesign.tasks import simulator_budget


class SmokePolicy:
    def __init__(self, agent, directory, run_id):
        self.turn, self.agent = 0, int(agent.split('-')[-1])
        self.ledger = Ledger(str(directory), run_id, agent, 'scripted', 'smoke')

    def call(self, system, user, env):
        self.turn += 1
        self.ledger.record('offline-smoke', 0, 0, usd_billed=0)
        return 'submit_edits', dict(note='Offline unique-query budget smoke test', edits=[
            dict(op='set', node='', n_stages=20+(self.turn-1)%100,
                 reflux_ratio=3+(self.turn-1)//100*.01, reboil_ratio=3+self.agent*.01, pressure_drop_fraction=.04)])


class StalledPast(ExactMemory):
    """Explicit offline stand-in: ingestion never yields any retrieved finding."""
    pass


def live_isolation(env_file, output):
    load_dotenv(env_file)
    first = PastMemory(blocking=True)
    scope = 'smoke-'+uuid.uuid4().hex
    first.start(scope, ['a','b'])
    record = compact_record(dict(id=scope+'-agent-a-v1', agent='a', round=1, design={},
        rejected=None, interpretation='ISOLATION_SMOKE_CANARY current scoped measured objective',
        measured=dict(valid=True, reward=3.5, revenue=3500, tac=0)))
    first.publish_batch([record])
    first.barrier()
    found = first.recall('b', query=f'ISOLATION_SMOKE_CANARY measured objective from run {scope}')
    visible = any(s['sourceId'] == record['id'] for f in found for s in f.get('sources', []))
    second = PastMemory()
    second.start('smoke-'+uuid.uuid4().hex, ['outsider'])
    other = second.recall('outsider', query=f'ISOLATION_SMOKE_CANARY measured objective from run {scope}')
    result = dict(first_scope=scope, first_clean_slate=first.clean_slate,
        current_source_visible=visible, second_scope=second.run_id,
        second_clean_slate=second.clean_slate, outsider_raw_findings=second.last_recall['raw_findings'],
        outsider_accepted_findings=len(other), outsider_raw_sources=second.last_source_ids,
        passed=visible and not other and second.last_recall['raw_findings'] == 0)
    output.write_text(json.dumps(result, indent=2))
    if not result['passed']:
        raise RuntimeError('Live memory isolation smoke failed; inspect '+str(output))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'runs/smoke-controls')
    parser.add_argument('--live-past', action='store_true')
    parser.add_argument('--env-file', default='.env')
    parser.add_argument('--task', type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    task = json.loads(args.task.read_text())
    budget = simulator_budget(task, required=True)
    memory_factory = lambda mode: {'none': NoMemory, 'exact': ExactMemory, 'past': StalledPast}[mode]()
    root, outcomes = run_controls(task, lambda: make_service('mock', task=task),
        SmokePolicy, args.out, memory_factory=memory_factory, rounds=budget+1, model='smoke')
    prompts = [json.loads(p.read_text()) for p in root.rglob('prompts/*.json')]
    result = dict(campaign=str(root), task=task['task_id'], past_backend='offline stalled-retrieval stand-in',
        condition_queries={e['condition']: e['queries'] for e in outcomes},
        condition_allocations={e['condition']: e['allocations'] for e in outcomes},
        prompt_count=len(prompts), max_input_bytes=max(p['diagnostics']['input_bytes'] for p in prompts),
        input_byte_limit=32000, prompt_incumbent_checks=sum(p['diagnostics']['incumbent_included'] for p in prompts),
        all_clean_slate=all(e['clean_slate']['verified'] for e in outcomes),
        model_api_calls=0, chemsep_calls=0,
        passed=all(e['queries'] == e['total_budget'] for e in outcomes) and all(
            p['diagnostics']['input_bytes'] <= p['diagnostics']['max_input_bytes'] for p in prompts))
    if args.live_past:
        result['live_past'] = live_isolation(args.env_file, args.out/'live-isolation.json')
    (args.out/'smoke-summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise RuntimeError('Task-configured controls smoke failed')
    return result


if __name__ == '__main__':
    main()
