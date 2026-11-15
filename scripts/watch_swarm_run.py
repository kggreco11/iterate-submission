"""Readable live swarm progress using the shared Azure snapshot cache."""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.check_v2_pair import snapshot
from sepdesign.tasks import Economics


def render(config,data,econ):
    agents=data.get('live_agents',{})
    state=data.get('pair',{}).get('state','waiting for status')
    if not agents:
        viewer=data.get('viewer',{})
        return '\n'.join(['KIMI K3.1 PRO · FIVE-AGENT SHARED-MEMORY SWARM  |  '+state.upper(),
            config['run_id'], 'Waiting for a detailed swarm snapshot; existing cached data has no per-agent counters.',
            f"Snapshot age: {viewer.get('snapshot_age_s','unknown')}s · {viewer.get('note','')}",
            'Refresh: 60 seconds plus Azure delivery. Ctrl-C closes only this viewer.'])
    norm=econ.reward_norm/1e6
    best=max((v.get('best',0) for v in agents.values()),default=0)
    total=lambda key:sum(v.get(key,0) for v in agents.values())
    lines=['KIMI K3.1 PRO · FIVE-AGENT SHARED-MEMORY SWARM  |  '+state.upper(),
        config['run_id'],config['task'],'',
        f"Simulator: {total('solves')}/{config['team_budget']} team calls · {config['per_agent_budget']} per agent  |  Submissions: {data.get('live_submissions',0)}  |  Model responses: {total('requests')}",
        f'Best valid team objective: ${best*norm:,.2f}M/year',
        f'Hypothetical ceiling: ${econ.max_total_revenue/1e6:,.2f}M/year  |  Attained: {100*best/econ.upper_bound_reward:.1f}%',
        f"Estimated model cost: ${total('usd'):.4f}  |  Unknown-cost requests: {total('unknown')}",
        f"Tokens: {total('input'):,} input / {total('output'):,} output",'',
        'AGENTS','Agent       Calls      Best $M/year   Responses   Estimated $']
    if not agents:lines.append('Waiting for the first detailed swarm snapshot…')
    for a,v in sorted(agents.items()):
        lines.append(f"{a:<10} {v['solves']:>3}/{v.get('budget',100):<3} {v['best']*norm:>16,.2f} {v['requests']:>11} {v['usd']:>13.4f}")
    lines+=['','RECENT SUBMISSIONS','Round  Agent      Calls  Valid    Candidate $M/year   Best $M/year']
    for v in data.get('live_recent',[]):
        candidate='—' if v['reward'] is None else f"{v['reward']*norm:,.2f}"
        lines.append(f"{v['round']:>5}  {v['agent']:<9} {v['solves']:>5}  {str(v['valid']):<7} {candidate:>18} {v['best']*norm:>14,.2f}")
    event=data.get('live_event',{})
    lines+=['','LATEST AGENT INTENT',data.get('live_note',''),'',
        f"Latest event: {event.get('kind','waiting')} · round {event.get('round') or '—'} · elapsed {(event.get('elapsed_s') or 0)/60:.1f} min",
        str(data.get('swarm_summary',{}).get('error') or ''),
        f"Snapshot age: {data.get('viewer',{}).get('snapshot_age_s','unknown')}s · {data.get('viewer',{}).get('note','')}",
        'Refresh: 60 seconds plus Azure delivery. Ctrl-C closes only this viewer.']
    return '\n'.join(lines)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('controller',type=Path);ap.add_argument('--once',action='store_true');a=ap.parse_args()
    config=json.loads(a.controller.read_text())
    econ=Economics(json.loads((ROOT/'tasks'/(config['task']+'.json')).read_text()))
    try:
        while True:
            data=snapshot(a.controller.resolve())
            if not a.once and sys.stdout.isatty():print('\033[2J\033[H',end='')
            print(render(config,data,econ),flush=True)
            if a.once or (data.get('pair',{}).get('state') in ('complete','failed') and data.get('viewer',{}).get('snapshot_age_s',999)<60):break
            time.sleep(60)
    except KeyboardInterrupt:pass


if __name__=='__main__':main()
