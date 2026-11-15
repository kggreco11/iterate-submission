"""Synchronized full-design exploration; no coordinator model."""
import copy
import hashlib
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sepdesign.env import PARAM_KEYS, attach_trace
from sepdesign.runlog import save_run
from sepdesign.service import make_env, InfrastructureError
from sepdesign.tasks import simulator_budget
from sepdesign.swarm_context import (build_prompt, compact_record, clean_note,
    evidence_sources, recall_query, encoded, DEFAULT_INPUT_BYTES)


def allocations(n, repetition=0, mode='equal-total', budget=50):
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
        raise ValueError('budget must be a positive integer')
    if n not in (1, 2, 3, 5):
        raise ValueError('supported team sizes: 1, 2 (plumbing only), 3, 5')
    if mode == 'equal-per-agent':
        return [budget] * n
    if mode != 'equal-total':
        raise ValueError('unknown budget mode')
    shares = [budget // n] * n
    for i in range(budget % n):
        shares[(i + repetition) % n] += 1
    return shares


def run_swarm(task, service, memory, policy_factory, out, n=1, rounds=20,
              repetition=0, mode=None, model='scripted', budget=None,
              condition=None, max_input_bytes=DEFAULT_INPUT_BYTES, archive=True):
    """policy_factory(agent_id, raw_dir, run_id) -> runner-compatible call policy.

    A policy returns (submit_edits, {edits, note, evidence_ids, source_design}).
    source_design is a previous retrieved version ID; its full design is copied
    before edits. Evidence IDs must have been returned to that agent by memory.
    """
    if service.cache or service.events:
        raise ValueError('run requires a fresh simulator service/cache')
    if len(getattr(service.backend, 'variants', (None,))) != 1:
        raise ValueError('disable backend solver retries before running')
    configured = simulator_budget(task)
    if budget is None:
        if configured is not None and mode == 'equal-total':
            raise ValueError('An equal-total override requires an explicit --budget')
        budget = configured if configured is not None else 50  # historical unconfigured runner default
    mode = mode or ('equal-per-agent' if configured is not None else 'equal-total')
    run_id = 'swarm-' + uuid.uuid4().hex
    condition = condition or ('single-agent' if n == 1 else f'shared-memory-{n}')
    if not condition or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in condition):
        raise ValueError('Invalid experiment condition')
    root = Path(out) / task['task_id'] / condition / model / run_id
    raw, metrics = root / 'raw', root / 'metrics'
    raw.mkdir(parents=True)
    metrics.mkdir()
    shares = allocations(n, repetition, mode, budget)
    agents = [f'agent-{i}' for i in range(n)]
    envs = {a: make_env(task, service, budget=b) for a, b in zip(agents, shares)}
    for env in envs.values():
        attach_trace(env)
    policies, findings, versions, records, events = {}, {}, {}, {}, []
    no_tools = {a: 0 for a in agents}
    histories, errors, best_turns = ({a: [] for a in agents}, {a: None for a in agents}, {a: 0 for a in agents})
    allowed, available_versions = {a: {} for a in agents}, {a: set() for a in agents}
    evaluated_designs = {}
    active = set(agents)
    status, error = 'round_limit', None
    started = time.monotonic()
    config = dict(run_id=run_id, agents=agents, allocations=shares, mode=mode, rounds=rounds,
                  repetition=repetition, task=task['task_id'], budget=budget, backend=service.backend_name, model=model,
                  solver_retries=0, simulator_workers=1, memory=type(memory).__name__,
                  memory_timeout_s=getattr(memory, 'timeout', None), condition=condition,
                  sharing=getattr(memory, 'sharing', True), max_input_bytes=max_input_bytes,
                  memory_blocking=getattr(memory, 'blocking', False), context_protocol='compact-v3')
    source_root = Path(__file__).resolve().parents[1]
    source_files = [p for folder in ('sepdesign', 'agents', 'scripts', 'tasks') for p in (source_root / folder).glob('*') if p.is_file() and p.suffix in ('.py', '.json')]
    (root / 'source-manifest.json').write_text(json.dumps({str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}, indent=2))
    (root / 'config.json').write_text(json.dumps(config, indent=2))

    def log(event):
        event.update(run_id=run_id, elapsed_s=time.monotonic()-started)
        events.append(event)
        with (raw / 'trajectory.jsonl').open('a') as f:
            f.write(json.dumps(event) + '\n')

    def propose(a, round_no):
        env = envs[a]
        start = time.monotonic()
        try:
            prompt, context, allowed[a], available_versions[a], diagnostics = build_prompt(
                task, env, round_no, histories[a], errors[a], best_turns[a], findings[a], records,
                sharing=getattr(memory, 'sharing', True), max_input_bytes=max_input_bytes)
            directory = raw / a / 'prompts'
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f'round-{round_no:04d}.json').write_text(json.dumps(dict(
                system=prompt, user=context, diagnostics=diagnostics), indent=2))
            name, args = policies[a].call(prompt, context, env)
            return dict(agent=a, action=name, response=args, model_s=time.monotonic()-start,
                        error=None, context=diagnostics)
        except Exception as exc:
            return dict(agent=a, action=None, response=None, model_s=time.monotonic()-start,
                        error=getattr(exc, 'stop_reason', type(exc).__name__))

    try:
        memory.start(run_id, agents)
        log(dict(kind='clean_slate', **getattr(memory, 'clean_slate', {'verified': None})))
        for a in agents:
            policies[a] = policy_factory(a, raw / a, run_id)
            initial = envs[a].evaluate()
            findings[a] = []
            if a == agents[0] and getattr(memory, 'sharing', True):
                version = f'{run_id}-{a}-v0'
                record = dict(id=version, agent=a, round=0, design={}, measured=initial,
                              rejected=None, interpretation='Initial empty plant; no simulator queries used.')
                records[version] = compact_record(record, envs[a].names)
                versions[version] = {}
                log(dict(kind='initial_design', **record))
        for round_no in range(1, rounds + 1):
            active = {a for a in active if envs[a].solves_left > 0}
            if not active:
                status = 'all_finished_or_exhausted'
                break
            # All proposals precede all publications, independent of completion order.
            with ThreadPoolExecutor(max_workers=n) as pool:
                futures = {pool.submit(propose, a, round_no): (a, time.monotonic()) for a in sorted(active)}
                proposals = []
                for future in as_completed(futures):
                    a, start = futures[future]
                    try:
                        proposal = future.result()
                    except Exception as exc:
                        proposal = dict(agent=a, action=None, response=None,
                                        model_s=time.monotonic()-start, error=type(exc).__name__)
                    proposals.append(proposal)
                    log(dict(kind='policy_outcome', round=round_no, **proposal))
            proposals.sort(key=lambda p: p['agent'])
            if any(p['error'] for p in proposals):
                raise RuntimeError('One or more agent policies failed; see policy_outcome events')
            publications = []
            for proposal in proposals:
                a, name, args, model_s = (proposal[k] for k in ('agent', 'action', 'response', 'model_s'))
                env = envs[a]
                if name == 'noop':
                    no_tools[a] += 1
                    errors[a] = 'Call submit_edits or finish; the previous response contained no tool call.'
                    histories[a].append(f'{round_no}: no tool call')
                    log(dict(kind='no_tool_call', agent=a, round=round_no))
                    if no_tools[a] >= 3:
                        raise ValueError('Three consecutive responses without a tool')
                    continue
                if name not in ('finish', 'submit_edits'):
                    raise ValueError('Unknown policy action')
                no_tools[a] = 0
                if name == 'finish':
                    active.remove(a)
                    log(dict(kind='finish', agent=a, round=round_no, model_s=model_s))
                    continue
                version = f'{run_id}-{a}-v{round_no}'
                evidence = args.get('evidence_ids', [])
                source = args.get('source_design')
                before = copy.deepcopy(env.design)
                failure = None
                try:
                    if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
                        raise ValueError('evidence_ids must be a list of allowed citation strings')
                    if not set(evidence) <= set(allowed[a]) or (source and source not in available_versions[a]):
                        raise ValueError('provenance references evidence not retrieved by this agent')
                    if source:
                        env.design = copy.deepcopy(versions[source])
                    env.apply(args.get('edits', []))
                except (ValueError, KeyError, TypeError) as exc:
                    env.design = before
                    failure = str(exc)
                    if not isinstance(evidence, list):
                        evidence = []
                try:
                    previous_best = env.score()
                    previous_queries = env.solves_used
                    result = None if failure else env.evaluate()
                    if result and result.get('unsolved_budget') and env.solves_left == 0:
                        proposed = copy.deepcopy(env.design)
                        original = result
                        charged_before_cleanup = env.solves_used
                        result = env.cleanup_unsolved()
                        log(dict(kind='budget_cleanup', agent=a, round=round_no,
                            proposed_design=proposed, original_result=original, design=copy.deepcopy(env.design),
                            measured=result, new_queries=env.solves_used-charged_before_cleanup))
                except InfrastructureError as exc:
                    log(dict(kind='evaluation_failure', agent=a, round=round_no,
                             error_category='infrastructure', error=str(exc),
                             design=copy.deepcopy(env.design), response=args,
                             distinct_queries=env.solves_used))
                    raise
                errors[a] = failure
                if failure:
                    histories[a].append(f'{round_no}: rejected edits ({failure[:160]})')
                else:
                    if previous_best is None or env.score() > previous_best:
                        best_turns[a] = round_no
                    histories[a].append(f"{round_no}: reward {result['reward']:.3f}, "
                        f"{'valid' if result['valid'] else 'INVALID'}, {env.solves_used} solves | {clean_note(args.get('note'), 140)}")
                histories[a] = histories[a][-12:]
                versions[version] = copy.deepcopy(env.design)
                record = dict(id=version, agent=a, round=round_no, design=env.design,
                              measured=result, rejected=failure, interpretation=args.get('note', ''),
                              source_design=source, evidence_ids=evidence,
                              evidence_sources={k: allowed[a].get(k, []) for k in evidence if isinstance(k, str)},
                              edits=args.get('edits', []))
                fingerprint = hashlib.sha256(encoded(env.design).encode()).hexdigest()
                log(dict(kind='submission', **record, model_s=model_s,
                         distinct_queries=env.solves_used, new_queries=env.solves_used-previous_queries,
                         design_sha256=fingerprint, duplicate_of=evaluated_designs.get(fingerprint)))
                if not failure:
                    evaluated_designs.setdefault(fingerprint, version)
                    records[version] = compact_record(record, env.names)
                    publications.append((a, version, records[version]))
            start = time.monotonic()
            if hasattr(memory, 'publish_batch'):
                write_ids = memory.publish_batch([record for _, _, record in publications])
            else:
                write_ids = [memory.publish(record) for _, _, record in publications]
            elapsed = time.monotonic()-start
            for (a, version, _), write_id in zip(publications, write_ids):
                if write_id is not None:
                    log(dict(kind='memory_write', agent=a, evidence_id=version, write_id=write_id,
                        memory_s=elapsed/len(publications), batched=hasattr(memory, 'publish_batch')))
            start = time.monotonic()
            memory.barrier()
            log(dict(kind='barrier', round=round_no, memory_s=time.monotonic()-start))
            for a in sorted(active):
                start = time.monotonic()
                query = recall_query(envs[a], run_id)
                findings[a] = memory.recall(a, query=query)
                log(dict(kind='memory_read', agent=a, round=round_no, findings=findings[a],
                         query=query, diagnostics=getattr(memory, 'last_recall', None),
                         read_id=uuid.uuid4().hex, memory_s=time.monotonic()-start))
    except Exception as exc:
        status, error = ('infrastructure_error' if isinstance(exc, InfrastructureError) else 'aborted'), type(exc).__name__ + ': ' + str(exc)
        log(dict(kind='failure', error=error))
    finally:
        usage = {a: p.ledger.summary() for a, p in policies.items() if hasattr(p, 'ledger')}
        for a, u in usage.items():
            rows = [json.loads(line) for line in (raw / a / 'usage.jsonl').read_text().splitlines()] if (raw / a / 'usage.jsonl').exists() else []
            u['reconciled'] = (len(rows) == u['requests'] and sum(r['input_tokens'] or 0 for r in rows) == u['input_tokens'] and sum(r['output_tokens'] or 0 for r in rows) == u['output_tokens'])
        summary = dict(run_id=run_id, status=status, error=error, wall_s=time.monotonic()-started,
            agents={a: dict(distinct_queries=e.solves_used, best_valid_reward=e.score(),
                            best_design=e.best[1] if e.best else None, usage=usage.get(a)) for a, e in envs.items()},
            team_distinct_queries=sum(e.solves_used for e in envs.values()),
            backend_calls=sum(e['backend_call'] for e in service.events),
            cache_hits=sum(e['cache_hit'] for e in service.events),
            submissions=sum(e['kind']=='submission' for e in events),
            team_input_tokens=sum(u['input_tokens'] for u in usage.values()),
            team_output_tokens=sum(u['output_tokens'] for u in usage.values()),
            known_llm_usd=sum(u['usd_estimated_total'] for u in usage.values()),
            unknown_cost_requests=sum(u['requests_with_unknown_cost'] for u in usage.values()),
            memory_usd=None, simulator_usd=None, clean_slate=getattr(memory, 'clean_slate', None),
            pending_ingestions=len(getattr(memory, 'pending', [])),
            duplicate_design_submissions=sum(bool(e.get('duplicate_of')) for e in events),
            max_input_bytes=max((e.get('context', {}).get('input_bytes', 0) for e in events), default=0))
        (metrics / 'summary.json').write_text(json.dumps(summary, indent=2))
        # Generate a replay/report per agent and an aggregate landing page without more solves.
        try:
            from sepdesign.report import build_swarm
            for a, env in envs.items():
                directory = raw / a
                directory.mkdir(exist_ok=True)
                turns = [dict(turn=e['round'], action='edit' if e.get('measured') else 'rejected',
                    note=e.get('interpretation', ''), solves_used=e['distinct_queries'],
                    **({k: e['measured'][k] for k in ('reward', 'valid')} if e.get('measured') else {}))
                    for e in events if e['kind']=='submission' and e['agent']==a]
                (directory / 'turns.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in turns))
                (directory / 'summary.json').write_text(json.dumps({**usage.get(a, {}), 'status': status,
                    'best_valid_reward': env.score(), 'solves_used': env.solves_used, 'task': task['task_id']}))
                save_run(str(directory / 'replay.json'), env, task, a, backend=service.backend_name,
                    wall_s=summary['wall_s'])
            build_swarm(root, summary, config, archive=archive)
        except Exception as report_error:
            (root / 'report_failure.json').write_text(json.dumps({'error_type': type(report_error).__name__}))

        (raw / 'simulator-responses.json').write_text(json.dumps(service.raw_responses, indent=2))
        (raw / 'simulator.json').write_text(json.dumps(service.events, indent=2))
        (raw / 'memory-requests.json').write_text(json.dumps(getattr(memory, 'events', []), indent=2))
        (metrics / 'isolation.json').write_text(json.dumps(getattr(memory, 'clean_slate', {'verified': None}), indent=2))
        (metrics / 'clean-slate.json').write_text(json.dumps(getattr(memory, 'clean_slate', {'verified': None}), indent=2))
        (root / 'manifest.json').write_text(json.dumps(dict(status=status, error=error, evidence_gaps=[
            'Mock/scripted runs are plumbing only; no performance claim.', 'Memory and compute dollar charges unknown.']), indent=2))
    return root, summary
