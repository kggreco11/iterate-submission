"""Read-only live terminal view: python scripts/watch_run.py RUN_DIR [--once]."""
import argparse
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sepdesign.tasks import Economics
from scripts.price_luna_pilot import estimate


def read_json(path):
    try: return json.loads(path.read_text())
    except (OSError,ValueError): return None


def render(path):
    manifest=read_json(path/'manifest.json')
    if manifest: path=Path(manifest['source_directory'])
    config=read_json(path/'config.json') or {}
    rows=[]
    try:
        for line in (path/'trajectory.jsonl').read_text().splitlines():
            try: rows.append(json.loads(line))
            except ValueError: pass  # writer may be halfway through its final line
    except FileNotFoundError: pass
    summary=read_json(path/'summary.json'); failure=read_json(path/'failure.json')
    status='FINISHED' if summary else 'FAILED' if failure else 'IN PROGRESS / awaiting next recorded event'
    lines=[f"{config.get('model', 'MODEL').upper()} PILOT  |  {status}",config.get('run_id',path.name),'']
    usage=[]
    for p in sorted(path.glob('response-*.json')):
        r=read_json(p)
        if r and r.get('usage'): usage.append(r['usage'])
    if rows:
        last=rows[-1]; f=last['feedback']; econ=Economics(json.loads((ROOT/'tasks/hc12_dev_000.json').read_text()))
        value=f['best_reward']*econ.reward_norm
        age=time.time()-(path/'trajectory.jsonl').stat().st_mtime
        lines += [f"Simulator: {f['solves_used']}/{config.get('simulator_budget',50)}  |  Submissions: {len(rows)}  |  Model responses: {len(usage)}",
            f"Best valid net objective: ${value/1e6:,.2f}M/year",
            f"Hypothetical ceiling: ${econ.max_total_revenue/1e6:,.2f}M/year  |  Attained: {100*value/econ.max_total_revenue:.1f}%",
            f"Simulator failures: {f['stats'].get('failed',0)}  |  Median solve: {f['stats'].get('median_s',0):.3f}s",
            f"Last completed evaluation at {last['elapsed_s']/60:.1f} min  |  Feedback age: {age:.0f}s"]
        try: lines += [f"Estimated model cost: ${sum(estimate(u, config.get('model', 'gpt-6-luna')) for u in usage):.5f} (excludes VM)"]
        except (KeyError,AssertionError): lines += ['Estimated model cost: unavailable']
        lines += [f"Tokens: {sum(u['input_tokens'] for u in usage):,} input / {sum(u['output_tokens'] for u in usage):,} output",'',
                  'RECENT SUBMISSIONS','Attempt  Solves   Valid   Candidate $M/yr   Best $M/yr']
        for r in rows[-8:]:
            v=r['feedback'];lines.append(f"{r['turn']+1:>7}  {v['solves_used']:>6}   {str(v['valid']):<5}   {v['reward']*econ.reward_norm/1e6:>15,.2f}   {v['best_reward']*econ.reward_norm/1e6:>10,.2f}")
        lines+=['','LATEST AGENT INTENT',last['proposal'].get('reason','')]
        if f.get('error'):lines+=['Rejected edit: '+f['error']]
    else:lines+=['Waiting for the first simulator result…']
    if summary:lines+=['','Stop reason: '+summary.get('stop_reason','unknown')]
    if failure:lines+=['','Error: '+failure.get('error','unknown')]
    lines+=['','Refresh: 2 seconds. Ctrl-C closes this viewer; the pilot keeps running.',
            'A stale timestamp alone does not prove the runner is alive. Azure delivery adds latency.',str(path)]
    return '\n'.join(lines), bool(summary or failure)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--once',action='store_true');ap.add_argument('--vm',action='store_true',help='Read an Azure run controller JSON');args=ap.parse_args()
    last_error = None
    try:
        while True:
            if args.vm:
                from scripts.watch_vm_run import fetch, render as render_vm
                try:
                    config,data=fetch(args.run.resolve())
                    text,done=render_vm(config,data,Economics(json.loads((ROOT/'tasks'/(config['task']+'.json')).read_text())))
                except RuntimeError as exc:
                    if str(exc) != last_error:
                        print(str(exc),flush=True)
                    last_error = str(exc)
                    if args.once: raise
                    time.sleep(60)
                    continue
            else:
                text,done=render(args.run.resolve())
            last_error = None
            if not args.once and sys.stdout.isatty():print('\033[2J\033[H',end='')
            print(text,flush=True)
            if done and args.vm:
                from scripts.finalize_vm_report import finalize
                print("Generating/downloading completed-run report…", flush=True)
                try:
                    print("Report: " + str(finalize(args.run.resolve())), flush=True)
                except RuntimeError as exc:
                    print("Report export pending: " + str(exc), flush=True)
                    if not args.once:
                        time.sleep(60)
                        continue
            if args.once or done:break
            time.sleep(15 if args.vm else 2)
    except KeyboardInterrupt:pass

if __name__=='__main__':main()
