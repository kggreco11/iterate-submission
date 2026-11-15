"""Package the site-assembly replay, including local Three.js, into one offline HTML."""
import argparse
import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(source, output):
    data = json.loads(Path(source).read_text())
    if not data.get('replay', {}).get('trace'):
        raise ValueError('A saved report with replay.trace is required')
    payload = {key: data.get(key, {}) for key in ('replay', 'turns', 'summary')}
    html = (HERE / 'plant_v2_template.html').read_text()
    imports = {}
    for name, filename in [('three', 'three.module.min.js'), ('three/controls', 'OrbitControls.js'), ('three/geometry', 'BufferGeometryUtils.js')]:
        imports[name] = 'data:text/javascript;base64,' + base64.b64encode((HERE / 'vendor' / 'three' / filename).read_bytes()).decode()
    html = html.replace('__IMPORTS__', json.dumps({'imports': imports}))
    html = html.replace('__RUN_DATA__', json.dumps(payload).replace('<', '\\u003c'))
    html = html.replace('__SCENE_SCRIPT__', (HERE / 'plant_v2.js').read_text())
    license_text = (HERE / 'vendor' / 'three' / 'LICENSE').read_text()
    html = html.replace('<head>', '<!-- Vendored Three.js 0.160.1\n' + license_text + '\n-->\n<head>', 1)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--output', default=str(HERE / 'plant_v2.html'))
    args = parser.parse_args()
    print(build(args.source, args.output))
