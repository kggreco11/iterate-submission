"""Bounded experimental evidence and reproducible agent inputs.

Raw measurements and rejected attempts belong in trajectory.jsonl. Only this
projection is shared. A model may cite/copy only evidence actually in its input.
"""
import copy
import hashlib
import json
import re

from agents.llm_agent import edit_schema, FINISH_SCHEMA, _state_text, system_prompt

MAX_RECORD_BYTES = 6000
DEFAULT_INPUT_BYTES = 32000
_REFERENCE = re.compile(r'\b(?:[0-9a-f]{8}-[0-9a-f-]{27,}|(?:swarm|control)-[\w-]+-v\d+)\b', re.I)


def encoded(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'), sort_keys=True)


def clean_note(value, limit=400):
    return _REFERENCE.sub('[reference omitted]', str(value or ''))[:limit]


def compact_record(record, names=()):
    """Preserve exact settings and objective; never propagate nested citations."""
    result = record.get('measured')
    if record.get('rejected') or result is None:
        return None
    out = {k: copy.deepcopy(record[k]) for k in ('id', 'agent', 'round', 'design')}
    out['measured'] = {k: result[k] for k in
        ('valid', 'reward', 'revenue', 'tac', 'columns', 'solves_used') if k in result}
    out['failed'] = list(result.get('failed', []))[:16]
    out['unsolved_budget'] = list(result.get('unsolved_budget', []))[:16]
    out['interpretation'] = clean_note(record.get('interpretation'))
    products = []
    for product in sorted(result.get('sold', []), key=lambda p: p.get('value', 0), reverse=True):
        flows = product.get('flows', [])
        total = sum(flows)
        largest = sorted(range(len(flows)), key=lambda i: flows[i], reverse=True)[:3]
        products.append(dict(node=product['node'], kind=product.get('kind'),
            annual_value=product.get('value'), composition={
                names[i] if i < len(names) else str(i): round(flows[i]/total, 4)
                for i in largest if total and flows[i] > 0}))
    out['products'] = products[:8]
    while len(encoded(out).encode()) > MAX_RECORD_BYTES and out['products']:
        out['products'].pop()
    if len(encoded(out).encode()) > MAX_RECORD_BYTES:
        out['interpretation'] = ''
        out['failed'], out['unsolved_budget'] = [], []
    if len(encoded(out).encode()) > MAX_RECORD_BYTES:
        raise ValueError('Exact design exceeds compact evidence budget')
    return out


def evidence_sources(findings):
    mapping = {}
    for finding in findings:
        sources = [s['sourceId'] for s in finding.get('sources', [])]
        if sources and finding.get('id'):
            mapping[finding['id']] = sources
        for source in sources:
            mapping[source] = [source]
    return mapping


def recall_query(env, run_id):
    """Ask about the current measured bottlenecks, rather than the run name alone."""
    result = env.last or {}
    unsold = []
    for product in sorted(result.get('sold', []), key=lambda p: sum(p.get('flows', [])), reverse=True):
        if product.get('value'):
            continue
        flows = product.get('flows', [])
        total = sum(flows)
        largest = sorted(range(len(flows)), key=lambda i: flows[i], reverse=True)[:3]
        unsold.append(dict(path=product['node'], major_components={env.names[i]: round(flows[i]/total, 3)
            for i in largest if total and flows[i] > 0}))
        if len(unsold) == 5:
            break
    failed = {path: env.design.get(path) for path in result.get('failed', [])[:5]}
    return (f'Run {run_id}. Improve the best valid annual net objective {env.score()}. '
            f'Current column paths {sorted(env.design)}. Unpaid product streams {unsold}. '
            f'Failed column settings {failed}. Retrieve measured improvements, '
            'profitable settings, and failed settings relevant to these streams. '
            'Distinguish measured results from interpretations.')


def build_prompt(task, env, turn, history, error, best_turn, findings, records,
                 sharing=True, max_input_bytes=DEFAULT_INPUT_BYTES):
    """Return the exact prompt, its authorization map, and size/freshness evidence.

    The hard cap is UTF-8 bytes including tool schemas and a framing reserve.
    Token estimates are diagnostic only; no provider tokenizer is assumed.
    Mandatory state and incumbent must fit intact; optional history is selected
    as whole records. Failure happens before any model request.
    """
    system = system_prompt(task, env.solve_budget, env) + (
        '\nIndependently maximize the complete plant objective. No assigned search roles. '
        'Cite only IDs in the allowed citation map. To copy an available exact design, '
        'use its version as source_design, then apply edits. Interpretations are hypotheses. '
        'Shared cached results still count against your own distinct-query allocation.')
    state = _state_text(env, env.last, turn, env.solve_budget, history, error, best_turn)
    tools_bytes = len(encoded([edit_schema(env), FINISH_SCHEMA]).encode())
    framing_reserve = 1024
    selected, memories = {}, []
    valid = [r for r in records.values() if r['measured'].get('valid')]
    incumbent = max(valid, key=lambda r: r['measured']['reward'], default=None) if sharing else None

    def render():
        mapping = {key: [key] for key in selected}
        mapping.update(evidence_sources(memories))
        summaries = [{k: v for k, v in r.items() if k != 'design'} for r in selected.values()]
        sections = dict(state=state, shared=encoded(summaries), memory=encoded(memories),
                        citations=encoded(mapping), designs=encoded({
                            key: {'design': r['design']} for key, r in selected.items()}))
        user = (sections['state'] + '\nShared measured findings (interpretations are hypotheses):\n' + sections['shared']
            + '\nRetrieved memory (interpretations are hypotheses):\n' + sections['memory']
            + '\nAllowed citation IDs mapped to source versions:\n' + sections['citations']
            + '\nRetrieved complete design versions:\n' + sections['designs'])
        size = len((system + user).encode()) + tools_bytes + framing_reserve
        return user, mapping, sections, size

    def fits():
        return render()[3] <= max_input_bytes

    if not fits():
        raise ValueError('Mandatory agent state exceeds input byte budget')
    if incumbent:
        selected[incumbent['id']] = incumbent
        if not fits():
            raise ValueError('Team incumbent and current state exceed input byte budget')

    # Exact/past receive the same incumbent and latest four experiments. Further
    # historical sources enter only through recall, isolating retrieval's effect.
    recent = list(records.values())[-4:][::-1] if sharing else []
    for record in recent:
        if record['id'] in selected:
            continue
        selected[record['id']] = record
        if not fits():
            del selected[record['id']]

    dropped = 0
    for finding in findings if sharing else []:
        sources = [s['sourceId'] for s in finding.get('sources', [])]
        if not sources or any(s not in records for s in sources):
            dropped += 1
            continue
        before = set(selected)
        for source in sources:
            selected[source] = records[source]
        # Raw source bodies are replaced with their canonical compact projection;
        # derived content is bounded and cannot carry inherited citation IDs.
        content = finding.get('content', '')
        try:
            parsed = json.loads(content)
            is_record = isinstance(parsed, dict) and 'design' in parsed
        except (ValueError, TypeError):
            is_record = False
        memory = dict(id=finding.get('id'), sources=[{'sourceId': s} for s in sources],
                      content='Measured experiment; see shared findings.' if is_record else clean_note(content, 600))
        memories.append(memory)
        if not fits():
            memories.pop()
            for source in set(selected) - before:
                del selected[source]
            dropped += 1

    user, mapping, sections, size = render()
    diagnostics = dict(input_bytes=size, max_input_bytes=max_input_bytes,
        estimated_input_tokens=(size+3)//4, token_estimate_method='UTF-8 bytes / 4; not provider tokenization',
        tool_schema_bytes=tools_bytes, framing_reserve_bytes=framing_reserve,
        section_bytes={k: len(v.encode()) for k, v in sections.items()},
        source_ids=list(selected), retrieved_memories=len(findings), included_memories=len(memories),
        omitted_memories=dropped, incumbent_id=incumbent['id'] if incumbent else None,
        incumbent_included=bool(incumbent and incumbent['id'] in selected),
        source_rounds={key: r['round'] for key, r in selected.items()},
        prompt_sha256=hashlib.sha256(encoded(dict(system=system, user=user)).encode()).hexdigest())
    return system, user, mapping, set(selected), diagnostics
