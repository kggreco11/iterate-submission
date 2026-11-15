"""Task-configured memory controls through one runner, at equal per-agent budgets.

This changes the experimental protocol, not the task's physics or economics.
Factories are injected so the complete campaign is smoke-testable offline.
"""
import hashlib
import json
from pathlib import Path
import uuid

from sepdesign.runtime import atomic_json
from sepdesign.swarm import run_swarm, allocations
from sepdesign.swarm_context import DEFAULT_INPUT_BYTES, encoded
from sepdesign.swarm_memory import NoMemory, ExactMemory, PastMemory
from sepdesign.tasks import simulator_budget

CONDITIONS = (
    ('single_without_past', 1, 'exact'),
    ('single_with_past', 1, 'past'),
    ('swarm_without_past', 5, 'exact'),
    ('swarm_with_past', 5, 'past'),
)


def control_plan(task, model, budget=None, repetitions=1, rounds=200, conditions=None):
    budget = simulator_budget(task, budget, required=True)
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError('repetitions must be a positive integer')
    if budget < 1 or rounds < 1:
        raise ValueError('Controls require a positive per-agent budget and round limit')
    selected = CONDITIONS if conditions is None else tuple(c for c in CONDITIONS if c[0] in conditions)
    if not selected or (conditions is not None and set(conditions) - {c[0] for c in CONDITIONS}):
        raise ValueError("Select at least one known condition")
    trials = []
    for repetition in range(repetitions):
        order = selected[repetition % len(selected):] + selected[:repetition % len(selected)]
        for condition, agents, memory in order:
            trials.append(dict(condition=condition, agents=agents, memory=memory,
                repetition=repetition, budget_per_agent=budget, total_budget=budget*agents,
                allocations=allocations(agents, repetition, mode='equal-per-agent', budget=budget)))
    return dict(protocol='memory-controls-2x2-v2', task=task['task_id'], model=model,
        task_sha256=hashlib.sha256(encoded(task).encode()).hexdigest(),
        budget_unit='charged distinct column queries per agent',
        budget=budget, rounds=rounds, repetitions=repetitions, spend_threshold=None,
        assigned_hypotheses=False, trials=trials)


def memory_for(kind):
    return {'none': NoMemory, 'exact': ExactMemory, 'past': PastMemory}[kind]()


def run_controls(task, service_factory, policy_factory, out, model='scripted',
                 budget=None, repetitions=1, rounds=200, memory_factory=memory_for,
                 max_input_bytes=DEFAULT_INPUT_BYTES, conditions=None):
    plan = control_plan(task, model, budget, repetitions, rounds, conditions)
    budget = plan['budget']
    root = Path(out)/('controls-'+uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    atomic_json(root/'plan.json', plan)
    outcomes = []
    atomic_json(root/'summary.json', dict(state='running', outcomes=outcomes))
    try:
        # Discover a misconfigured project before spending on any control, then
        # recheck the actual new audience at each past trial's startup.
        if any(t['memory'] == 'past' for t in plan['trials']):
            preflight = memory_factory('past')
            try:
                preflight.start('check-'+uuid.uuid4().hex, [f'agent-{i}' for i in range(5)])
            finally:
                atomic_json(root/'memory-preflight.json', getattr(preflight, 'clean_slate', {'verified': None}))
        for trial in plan['trials']:
            run, summary = run_swarm(task, service_factory(), memory_factory(trial['memory']),
                policy_factory, root/'runs', n=trial['agents'], rounds=rounds,
                repetition=trial['repetition'], mode='equal-per-agent', model=model,
                budget=budget, condition=trial['condition'], max_input_bytes=max_input_bytes, archive=False)
            outcome = dict(**trial, run=str(run.relative_to(root)), status=summary['status'],
                best_valid_reward=max(a['best_valid_reward'] or 0 for a in summary['agents'].values()),
                queries=summary['team_distinct_queries'], backend_calls=summary['backend_calls'],
                estimated_model_usd=summary['known_llm_usd'], wall_s=summary['wall_s'],
                input_tokens=summary['team_input_tokens'], output_tokens=summary['team_output_tokens'],
                clean_slate=summary['clean_slate'], pending_ingestions=summary['pending_ingestions'])
            outcomes.append(outcome)
            atomic_json(root/'summary.json', dict(state='running', outcomes=outcomes))
            if summary['status'] in ('aborted', 'infrastructure_error'):
                raise RuntimeError('Control condition failed: '+trial['condition'])
        atomic_json(root/'summary.json', dict(state='complete', outcomes=outcomes))
    except Exception as exc:
        atomic_json(root/'summary.json', dict(state='failed', error_type=type(exc).__name__, outcomes=outcomes))
        raise
    return root, outcomes
