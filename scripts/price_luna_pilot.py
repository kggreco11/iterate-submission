"""Estimate standard, short-context Luna spend from saved Responses usage."""
import argparse
import json
from pathlib import Path

SOURCE = 'https://developers.openai.com/api/docs/pricing'
RATES = dict(input=0.10, output=0.50, cached_input=0.01, write_30m=0.125, write_12h=0.25)

MODEL_RATES = {"gpt-6-luna": RATES, "gpt-6.1-sol": dict(input=2.0, output=10.0, cached_input=0.1, write_30m=2.5, write_12h=5.0)}

def estimate(usage, model="gpt-6-luna"):
    rates = MODEL_RATES[model]
    tin, tout = usage['input_tokens'], usage['output_tokens']
    detail = usage.get('input_tokens_details', {})
    cached = detail.get('cached_tokens', 0)
    writes = detail.get('cache_write_tokens_details', {})
    w30, w12 = writes.get('ttl_30m_tokens', 0), writes.get('ttl_12h_tokens', 0)
    assert w30 + w12 == detail.get('cache_write_tokens', 0), 'unclassified cache writes'
    fresh = tin - cached - w30 - w12
    assert fresh >= 0, 'cache token subsets exceed total input'
    return (fresh * rates['input'] + cached * rates['cached_input'] + w30 * rates['write_30m'] +
            w12 * rates['write_12h'] + tout * rates['output']) / 1e6

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('run'); a=ap.parse_args()
    path=Path(a.run); events=[]
    for p in sorted(path.glob('response-*.json')):
        r=json.loads(p.read_text())
        if r['model'] not in MODEL_RATES or r.get('service_tier') not in ('default', None):
            raise ValueError('Pricing only verified for standard Luna')
        if r['usage']['input_tokens'] > 272000:
            raise ValueError('Long-context pricing requires separate verification')
        events.append({'response_id':r['id'],'usage':r['usage'],'estimated_usd':estimate(r['usage'], r['model'])})
    report={'label':'estimate, not invoice','source':SOURCE,'verified_date':'2026-11-14',
        'rates_usd_per_million_tokens':MODEL_RATES,'events':events,'estimated_total_usd':sum(e['estimated_usd'] for e in events),
        'excludes':'Azure VM costs; any request without a saved response; non-model costs'}
    (path/'pricing.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'requests':len(events),'estimated_usd':report['estimated_total_usd']}))

if __name__=='__main__': main()
