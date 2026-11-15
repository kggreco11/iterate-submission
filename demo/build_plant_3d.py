"""Build an offline 3D replay from a saved report-data.json; no simulator calls."""
import argparse
import json
from pathlib import Path


def build(source, output):
    data = json.loads(Path(source).read_text())
    replay = data['replay']
    if not replay.get('trace'):
        raise ValueError('The saved run has no improvement snapshots')
    payload = {'replay': replay, 'turns': data.get('turns', []), 'model': data.get('summary', {}).get('model', 'Agent')}
    template = Path(__file__).with_name('plant_3d_template.html').read_text()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace('__RUN_DATA__', json.dumps(payload).replace('<', '\\u003c')))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--output', default='demo/plant_3d.html')
    args = parser.parse_args()
    print(build(args.source, args.output))
