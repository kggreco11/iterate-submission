"""Probe a fresh past.dev reader against a prior run; no model or simulator calls."""
import argparse
import json
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.llm_agent import load_dotenv
from sepdesign.swarm_memory import PastMemory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--env-file', required=True)
    args = parser.parse_args()
    load_dotenv(args.env_file)
    config = json.loads((args.run/'config.json').read_text())
    rows = [json.loads(line) for line in (args.run/'raw/trajectory.jsonl').read_text().splitlines()]
    sources = {r['id'] for r in rows if r['kind']=='submission'}
    for r in rows:
        if r['kind']=='memory_read':
            sources.update(s['sourceId'] for f in r['findings'] for s in f.get('sources', []))
    reader = PastMemory()
    scope = 'iso-' + uuid.uuid4().hex
    result = dict(reference_run=config['run_id'], probe_scope=scope, isolated=False)
    try:
        reader.start(scope, ['outsider'])
        accepted = reader.recall('outsider', query=f"Simulator findings, designs and results from run {config['run_id']}")
        overlap = sorted(set(reader.last_source_ids) & sources)
        result.update(accepted_memories=len(accepted), raw_reference_source_overlap=overlap,
            clean_slate=reader.clean_slate, recall=reader.last_recall,
            isolated=not accepted and not reader.last_source_ids and reader.last_recall['raw_findings'] == 0)
    except RuntimeError as exc:
        result.update(error_type=type(exc).__name__, clean_slate=reader.clean_slate)
    (args.run/'metrics'/f'{scope}.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    if not result['isolated']:
        raise RuntimeError('cross-run memory leakage')


if __name__ == '__main__':
    main()
