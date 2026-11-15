"""Plan or execute memory controls for an explicitly supplied task configuration."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.llm_agent import load_dotenv
from scripts.run_swarm import policy_factory
from sepdesign.experiments import CONDITIONS, control_plan, run_controls
from sepdesign.service import make_service
from sepdesign.swarm_context import DEFAULT_INPUT_BYTES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', type=Path, required=True, help='Task JSON including experiment settings')
    parser.add_argument('--provider', choices=['scripted','anthropic','openai','modal'], default='scripted')
    parser.add_argument('--model', default='scripted')
    parser.add_argument('--backend', choices=['mock','chemsep'], default='mock')
    parser.add_argument('--budget', type=int, help='Explicit per-agent override; otherwise read the task experiment settings')
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--rounds', type=int, default=200)
    parser.add_argument('--max-input-bytes', type=int, default=DEFAULT_INPUT_BYTES)
    parser.add_argument('--env-file', default='.env')
    parser.add_argument('--out', type=Path, default=ROOT/'runs/controls')
    parser.add_argument('--condition', action='append', choices=[c[0] for c in CONDITIONS], help='Select conditions; default is all four')
    parser.add_argument('--execute', action='store_true', help='Without this flag, only print the frozen plan')
    args = parser.parse_args(argv)
    task = json.loads(args.task.read_text())
    plan = control_plan(task, args.model, args.budget, args.repetitions, args.rounds, args.condition)
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return plan
    load_dotenv(args.env_file)
    if any(t['memory'] == 'past' for t in plan['trials']) and not os.environ.get('PAST_API_KEY'):
        parser.error('Selected past.dev controls require PAST_API_KEY; no condition has been started')
    root, outcomes = run_controls(task,
        lambda: make_service(args.backend, task=task, **({'retry': False} if args.backend == 'chemsep' else {})),
        policy_factory(args.provider, args.model), args.out, model=args.model,
        budget=args.budget, repetitions=args.repetitions, rounds=args.rounds,
        max_input_bytes=args.max_input_bytes, conditions=args.condition)
    print(root)
    print(json.dumps(outcomes, indent=2))
    return root


if __name__ == '__main__':
    main()
