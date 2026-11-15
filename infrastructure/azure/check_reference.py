"""Compare selected config-0 worker results with recorded upstream references."""
import argparse
import json
import math
from pathlib import Path
import urllib.request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--url', default='http://127.0.0.1:5701')
    a = p.parse_args()
    report = []
    for item in json.loads(a.cases.read_text()):
        req = urllib.request.Request(a.url + '/solve', data=json.dumps({'config': 0, 'case': item['case'],
                                     'request_id': 'hackathon-smoke-' + item['id']}).encode(),
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=330) as response:
            result = json.load(response)['result']
        expected = item['expected']
        checks = {'success': result['success'] == expected['success']}
        diffs = {}
        if result['success'] and expected['success']:
            for side in ['tops', 'bottoms']:
                observed = result[side]['flows']
                reference = expected[side]['flows']
                checks[side] = len(observed) == len(reference) and all(
                    math.isclose(x, y, rel_tol=1e-7, abs_tol=1e-6) for x, y in zip(observed, reference))
                diffs[side + '_max_abs_mol_s'] = max(abs(x - y) for x, y in zip(observed, reference))
            feed = item['case']['feed_flows_mol_s']
            checks['component_balance'] = all(math.isfinite(t + b) and math.isclose(t + b, f, rel_tol=1e-7, abs_tol=1e-6) for t, b, f in zip(result['tops']['flows'], result['bottoms']['flows'], feed))
            checks['nonnegative_flows'] = all(math.isfinite(x) and x >= -1e-8 for side in ['tops', 'bottoms'] for x in result[side]['flows'])
            checks['tac'] = math.isclose(result['tac_usd_per_year'], expected['tac_usd_per_year'], rel_tol=1e-7, abs_tol=1.0)
            diffs['tac_abs_usd_per_year'] = abs(result['tac_usd_per_year'] - expected['tac_usd_per_year'])
        report.append({'id': item['id'], 'passed': all(checks.values()), 'checks': checks,
                       'differences': diffs, 'observed': result, 'expected': expected})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps([{'id': r['id'], 'passed': r['passed'], 'differences': r['differences']} for r in report], indent=2))
    if not all(r['passed'] for r in report):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
