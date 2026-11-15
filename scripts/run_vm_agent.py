"""Persistent VM-local agent loop. Run from a detached Scheduled Task on Windows."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.llm_agent import run_agent
from sepdesign import attach_trace, make_env, make_service, save_run
from sepdesign.ledger import PRICES
from sepdesign.runtime import SerialBackend, Timings, atomic_json


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--backend', choices=['mock', 'chemsep'], default='chemsep')
    ap.add_argument('--provider', choices=['scripted', 'openai', 'anthropic', 'modal'], default='scripted')
    ap.add_argument('--model', default='gpt-6-luna')
    ap.add_argument('--task', type=Path, default=ROOT / 'tasks/hc12_dev_000.json')
    ap.add_argument('--budget', type=int, default=50)
    ap.add_argument('--max-turns', type=int, default=80)
    ap.add_argument('--max-usd', type=float, default=None, help='Optional estimated API spend threshold; disabled by default')
    ap.add_argument('--out', type=Path, default=ROOT / 'runs' / 'runtime')
    ap.add_argument('--chemsep-dir', default=r'C:\Users\chemsepadmin\Desktop')
    a = ap.parse_args(argv)
    if not a.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in a.run_id):
        ap.error('run-id must contain only letters, digits, - or _')
    run = a.out / a.run_id
    run.mkdir(parents=True, exist_ok=False)  # Never overwrite or silently resume a run.
    os.environ['CHEMSEP_DIR'] = a.chemsep_dir
    timings = Timings(run / 'timings.jsonl')
    started = time.perf_counter()
    atomic_json(run / 'status.json', dict(state='running', pid=os.getpid()))
    env = svc = task = None
    try:
        if a.max_usd is not None and a.provider != 'scripted' and a.model not in PRICES:
            raise ValueError('Paid provider requires known model pricing before execution')
        if a.max_usd is not None and a.max_usd <= 0:
            raise ValueError('max-usd must be positive')
        task = json.loads(a.task.read_text())
        svc = make_service(a.backend, retry=False, task=task)
        svc.backend = SerialBackend(svc.backend, timings, run / 'simulator.jsonl')
        env = make_env(task, svc, budget=a.budget)
        attach_trace(env)
        summary = run_agent(env, task, provider=a.provider, model=a.model, max_turns=a.max_turns,
                            max_usd=a.max_usd, out_dir=str(a.out), run_id=a.run_id, timings=timings)
        elapsed = time.perf_counter() - started
        save_run(str(run / 'replay.json'), env, task, a.run_id, backend=svc.backend_name, wall_s=elapsed)
        atomic_json(run / 'runtime.json', dict(wall_s=elapsed, phase_seconds=timings.totals,
                    phase_counts=timings.counts, simulator_capacity=1, solver_retry=False,
                    submission_transport_s=0.0, service=svc.stats(), agent=summary))
        stop_reason = summary.get('status', 'unknown')
        successful = stop_reason in {'budget_exhausted', 'finished', 'max_turns', 'spend_cap'}
        if not successful:
            atomic_json(run / 'failure.json', dict(error_type='AgentRunFailure', stop_reason=stop_reason))
        atomic_json(run / 'status.json', dict(state='complete' if successful else 'failed',
                    stop_reason=stop_reason, wall_s=elapsed))
    except BaseException as ex:
        # Preserve available evidence while allowing the original exception to propagate.
        try:
            elapsed = time.perf_counter() - started
            summary_path = run / 'summary.json'
            summary = json.loads(summary_path.read_text()) if summary_path.exists() else {
                'status': 'failed', 'error_type': type(ex).__name__, 'requests': 0,
                'input_tokens': None, 'output_tokens': None}
            if not summary_path.exists(): atomic_json(summary_path, summary)
            if env is not None:
                save_run(str(run / 'replay.json'), env, task, a.run_id, backend=svc.backend_name, wall_s=elapsed,
                    extra={'partial': True, 'current_design': env.design, 'last_result': env.last})
            atomic_json(run / 'runtime.json', dict(partial=True, wall_s=elapsed,
                phase_seconds=timings.totals, phase_counts=timings.counts,
                service=svc.stats() if svc is not None else None, agent=summary))
        except Exception as cleanup_error:
            atomic_json(run / 'cleanup_failure.json', {'error_type': type(cleanup_error).__name__})
        # Avoid copying provider exception strings (which may contain secrets) to control output.
        atomic_json(run / 'failure.json', dict(error_type=type(ex).__name__))
        atomic_json(run / 'status.json', dict(state='failed', error_type=type(ex).__name__))
        raise
    finally:
        if (run / 'replay.json').exists():
            try:
                from sepdesign.report import build
                build(run)
            except Exception as ex:
                atomic_json(run / 'report_failure.json', dict(error_type=type(ex).__name__))


if __name__ == '__main__':
    main()
