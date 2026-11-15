"""Run scripted plumbing or explicitly selected paid policies; see docs/SWARM.md."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.llm_agent import _Scripted, _Anthropic, _OpenAI, load_dotenv
from agents.kimi import Kimi
from sepdesign.ledger import Ledger, PRICES
from sepdesign.service import make_service
from sepdesign.swarm import run_swarm
from sepdesign.swarm_memory import LocalMemory, PastMemory, NoMemory, ExactMemory
from sepdesign.swarm_context import DEFAULT_INPUT_BYTES


class PlumbingPolicy(_Scripted):
    """Deterministic causal-use probe: B copies retrieved A v1 then changes reflux."""
    def __init__(self, ledger, agent):
        super().__init__(ledger)
        self.agent, self.turn = agent, 0

    def call(self, system, user, env=None):
        self.turn += 1
        if self.agent == 'agent-1' and self.turn == 2:
            records = json.loads(user.split('Retrieved complete design versions:\n')[1])
            source = next(k for k in records if '-agent-0-v1' in k)
            self.ledger.record('plumbing-copy', 0, 0, usd_billed=0, note='scripted; no model')
            return 'submit_edits', dict(source_design=source, evidence_ids=[source],
                note='Using A simulator evidence: copy its evaluated complete design and test reflux 4.0.',
                edits=[dict(op='set', node='', n_stages=53, reflux_ratio=4, reboil_ratio=3.56, pressure_drop_fraction=.04)])
        return super().call(system, user, env)


def policy_factory(provider, model, max_usd=None, plumbing=False):
    """Use identical provider settings for all controlled conditions."""
    if max_usd is not None and (max_usd <= 0 or (provider != 'scripted' and model not in PRICES)):
        raise ValueError('Spend thresholds require a positive amount and known model pricing')
    def factory(agent, directory, run_id):
        ledger = Ledger(str(directory), run_id, agent, provider, model)
        if provider == 'scripted':
            return PlumbingPolicy(ledger, agent) if plumbing else _Scripted(ledger)
        policy = {'anthropic': _Anthropic, 'openai': _OpenAI, 'modal': Kimi}[provider](model, ledger)
        if hasattr(policy, 'c'):
            policy.c = policy.c.with_options(max_retries=0)
        original = policy.call
        def capped(*args, **kw):
            if max_usd is not None and ledger.unknown:
                raise RuntimeError('Unknown usage; stopping paid run')
            if max_usd is not None and ledger.usd >= max_usd:
                return 'finish', {'note': 'spend threshold'}
            return original(*args, **kw)
        policy.call = capped
        return policy
    return factory


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--agents', type=int, choices=[1,2,3,5], default=2)
    ap.add_argument('--task', type=Path, default=Path(__file__).resolve().parents[1] / 'tasks/hc12_dev_000.json')
    ap.add_argument('--budget', type=int, help='Explicit override; otherwise use task experiment.simulator_budget_per_agent or the historical default')
    ap.add_argument('--rounds', type=int, default=2)
    ap.add_argument('--repetition', type=int, default=0)
    ap.add_argument('--mode', choices=['equal-total','equal-per-agent'], help='Task budgets are per-agent; unconfigured tasks retain equal-total mode')
    ap.add_argument('--memory', choices=['none','exact','local','past'], default='local')
    ap.add_argument('--memory-timeout', type=float, default=300, help='Maximum age of a pending ingestion in seconds')
    ap.add_argument('--memory-blocking', action='store_true', help='Wait for ingestion; default polls without sleeping')
    ap.add_argument('--max-input-bytes', type=int, default=DEFAULT_INPUT_BYTES)
    ap.add_argument('--backend', choices=['mock','chemsep'], default='mock')
    ap.add_argument('--provider', choices=['scripted','anthropic','openai','modal'], default='scripted')
    ap.add_argument('--model', default='scripted')
    ap.add_argument('--max-usd', type=float, default=None, help='Optional per-agent API spend threshold; disabled by default')
    ap.add_argument('--env-file', default='.env')
    ap.add_argument('--out', default='runs')
    a = ap.parse_args(argv)
    load_dotenv(a.env_file)
    if a.max_usd is not None and a.provider != 'scripted' and a.model not in PRICES:
        ap.error('Paid policy requires a known Ledger price; add verified rates before running.')
    task = json.loads(a.task.read_text())
    factory = policy_factory(a.provider, a.model, a.max_usd,
        plumbing=a.agents == 2 and a.rounds == 2 and a.memory != 'none')
    memory = (PastMemory(timeout=a.memory_timeout, blocking=a.memory_blocking) if a.memory == 'past'
              else {'local': LocalMemory, 'exact': ExactMemory, 'none': NoMemory}[a.memory]())
    root, summary = run_swarm(task, make_service(a.backend, task=task, **({'retry':False} if a.backend=='chemsep' else {})),
        memory, factory, a.out, a.agents, a.rounds, a.repetition, a.mode, a.model,
        budget=a.budget, max_input_bytes=a.max_input_bytes)
    if a.agents == 2 and a.rounds == 2 and summary['status'] not in ('aborted', 'infrastructure_error'):
        other = PastMemory() if a.memory == 'past' else LocalMemory()
        import uuid
        other.start('iso-' + uuid.uuid4().hex, ['outsider'])
        isolated = other.recall('outsider', query=f'Simulator findings for run {summary["run_id"]}') == []
        isolated = isolated and not any(s.startswith(summary['run_id']) for s in getattr(other, 'last_source_ids', []))
        (root / 'metrics' / 'isolation.json').write_text(json.dumps({'isolated': isolated}))
        if not isolated:
            raise RuntimeError('cross-run memory leakage')
    print(root)
    print(json.dumps(summary, indent=2))
    if summary['status'] in ('aborted', 'infrastructure_error'):
        sys.exit(1)


if __name__ == '__main__':
    main()
