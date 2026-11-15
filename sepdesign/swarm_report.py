"""Portable swarm dashboard, with an explicitly selected single-run comparator."""
import html
import json


def single_metrics(data):
    s, r = data['summary'], data['replay']
    return dict(run_id=s['run_id'], task=r['task'], model=s['model'],
        reward=r['best_reward'], norm=r['reward_norm'], ceiling=r['upper_bound_reward'],
        queries=r['solves_used'], budget=r['budget'], wall_s=r['wall_s'],
        usd=s.get('usd_estimated_total'), requests=s.get('requests'),
        unknown_cost_requests=s.get('requests_with_unknown_cost'), backend=r.get('backend'))


def progress_chart(data, norm, ceiling):
    """Show observed valid best-so-far scores by synchronized round."""
    trajectories = {}
    for agent, payload in data['agents'].items():
        best = None
        points = []
        for turn in sorted(payload.get('turns', []), key=lambda t: t['turn']):
            if turn.get('valid') and turn.get('reward') is not None:
                best = max(best, turn['reward']) if best is not None else turn['reward']
            if best is not None:
                points.append((turn['turn'], best))
        trajectories[agent] = points
    xmax = max((r for points in trajectories.values() for r, _ in points), default=1)
    ymax = max(ceiling, max((v for points in trajectories.values() for _, v in points), default=1), 1)
    x = lambda r: 70 + 900*r/xmax
    y = lambda v: 300 - 250*v/ymax
    elements = []
    for i in range(5):
        value=ymax*i/4
        elements.append(f'<line x1="70" x2="970" y1="{y(value)}" y2="{y(value)}" stroke="#dde4e9"/><text x="60" y="{y(value)+4}" text-anchor="end">{value*norm/1e9:.1f}</text>')
        r=xmax*i/4
        elements.append(f'<text x="{x(r)}" y="325" text-anchor="middle">{r:.0f}</text>')
    palette=['#16825f','#3579b5','#ba7423','#8a57ae','#bb4969']
    legend=[]
    for (agent, points), color in zip(trajectories.items(), palette):
        if not points:
            continue
        path=f'M{x(points[0][0])},{y(points[0][1])}'
        for r,v in points[1:]:
            path+=f' H{x(r)} V{y(v)}'
        elements.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"/>')
        for r,v in points:
            elements.append(f'<circle cx="{x(r)}" cy="{y(v)}" r="3" fill="{color}"><title>{html.escape(agent)} / round {r}: ${v*norm/1e9:.3f}B/year</title></circle>')
        legend.append(f'<span style="color:{color};margin-right:24px">● {html.escape(agent)}</span>')
    return '<section><h2>Search progress across rounds</h2><p>Best valid annual objective ($B/year). Rounds are synchronization steps, not equal-query or equal-time checkpoints. Hover over a point for its value.</p><svg role="img" aria-label="Per-agent best objective by round" viewBox="0 0 1000 355" style="width:100%">'+''.join(elements)+'<text x="500" y="350" text-anchor="middle">Synchronized round</text></svg><p>'+''.join(legend)+'</p></section>'


def render(data):
    s, c = data['summary'], data['config']
    agents = s['agents']
    best_id = max(agents, key=lambda a: agents[a].get('best_valid_reward') or 0)
    replay = data['agents'][best_id]['replay']
    norm = replay.get('reward_norm', 1)
    ceiling = replay.get('upper_bound_reward', 0)
    best = agents[best_id].get('best_valid_reward') or 0
    def f(v, digits=2):
        return 'Unavailable' if v is None else f'{v:,.{digits}f}'
    def esc(v):
        return html.escape(str(v))
    def money(v):
        return 'Unavailable' if v is None else '$'+f(v,4)
    def objective(v):
        return '$'+f(v*norm/1e9,3)+'B/year'
    rows=[]
    for a, r in agents.items():
        u=r.get('usage') or {}
        value=r.get('best_valid_reward') or 0
        rows.append(f'<tr><td><a href="agents/{esc(a)}/index.html">{esc(a)}</a>{" · best" if a==best_id else ""}</td><td>{r["distinct_queries"]}</td><td>{objective(value)}</td><td>{f(value,4)}</td><td>{money(u.get("usd_estimated_total"))}</td><td>{u.get("requests", "—")}</td></tr>')
    comparison=''
    single=data.get('comparison',{}).get('single')
    if single:
        if single['task']!=c['task'] or single['model']!=c['model'] or single['norm']!=norm or single['ceiling']!=ceiling or single.get('backend') != c.get('backend'):
            raise ValueError('Comparator task, model, backend and reward normalization must match')
        delta=(best/single['reward']-1)*100 if single['reward'] else None
        delta_text = ('Percentage change unavailable because the single-agent baseline reward is zero.' if delta is None else
            f"Swarm best objective is {f(abs(delta),2)}% {'lower than' if delta < 0 else 'higher than' if delta > 0 else 'different from'} the single agent.")
        metrics=[('Best annual objective',objective(single['reward']),objective(best)),
            ('Normalized reward',f(single['reward'],4),f(best,4)),
            ('Hypothetical ceiling attained',f(single['reward']/ceiling*100,1)+'%' if ceiling else 'Unavailable',f(best/ceiling*100,1)+'%' if ceiling else 'Unavailable'),
            ('Charged queries / allocation',f'{single["queries"]} / {single["budget"]}',f'{s["team_distinct_queries"]} / {sum(c.get("allocations",[]))}'),
            ('Elapsed minutes',f(single['wall_s']/60,1),f(s['wall_s']/60,1)),
            ('Estimated model cost',money(single['usd']),money(s.get('known_llm_usd'))),
            ('Model requests',single['requests'],sum((v.get('usage') or {}).get('requests',0) for v in agents.values())),
            ('Unknown-cost model requests',single['unknown_cost_requests'],s.get('unknown_cost_requests'))]
        comparison='<section><h2>Completed run comparison</h2><p class="lead">'+delta_text+'</p><table><tr><th>Metric</th><th>Single agent</th><th>Multi-agent swarm</th></tr>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in metrics)+'</table><p class="note">These are completed outcomes at unequal budgets, from one run per condition on one development task. They do not establish a general single-agent advantage or isolate the effect of memory. No equal-200-query team checkpoint is claimed. Model cost excludes memory and VM charges.</p><p>Comparator: '+esc(single['run_id'])+'; its payload SHA-256 is recorded in report-data.json.</p><p><a href="../../../single-agent/'+esc(single['model'])+'/'+esc(single['run_id'])+'/index.html">Open the single-agent report</a></p></section>'
    bars=''.join(f'<div class="barrow"><span>{esc(a)}</span><div class="track"><div class="bar" style="width:{max(0,min(100,(r.get("best_valid_reward") or 0)/ceiling*100)) if ceiling else 0}%"></div></div><b>{objective(r.get("best_valid_reward") or 0)}</b></div>' for a,r in agents.items())
    cards=[('Best team objective',objective(best)),('Ceiling attained',f(best/ceiling*100,1)+'%' if ceiling else 'Unavailable'),('Charged queries',str(s['team_distinct_queries'])),('Elapsed time',f(s.get('wall_s',0)/60,1)+' min')]
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kimi multi-agent results</title><style>
body{margin:0;background:#f4f6f8;color:#182b3b;font:16px system-ui}main{max-width:1180px;margin:40px auto;padding:0 24px}h1{font-size:36px}h2{margin-top:0}.eyebrow{letter-spacing:.12em;font-size:12px;color:#52706a}.muted{color:#536779}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.card,section{background:white;border:1px solid #dce3eb;border-radius:12px;padding:24px;margin:22px 0}.card strong{display:block;font-size:26px;margin-top:12px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:13px 10px;border-bottom:1px solid #e3e8ed}th{color:#536779;font-size:13px}a{color:#087b60}.note{background:#edf5f2;padding:18px;line-height:1.6}.lead{font-size:22px}.barrow{display:flex;align-items:center;gap:18px;margin:20px 0}.track{height:24px;background:#edf0f3;flex:1}.bar{height:100%;background:#16825f}.barrow b{min-width:150px;font-size:14px}pre{white-space:pre-wrap}@media(max-width:750px){.cards{grid-template-columns:1fr 1fr}table{font-size:12px}section{overflow:auto}}
</style><main><div class="eyebrow">ITERATE / COMPLETED MULTI-AGENT EXPERIMENT</div>'''+f'<h1>{esc(c["model"])} · {len(agents)} agents</h1><p class="muted">{esc(c["task"])} · {esc(s["status"])} · {esc(c.get("backend","backend unavailable"))}</p><div class="cards">'+''.join(f'<div class="card">{esc(k)}<strong>{esc(v)}</strong></div>' for k,v in cards)+'</div>'+comparison+progress_chart(data,norm,ceiling)+'<section><h2>Every agent, one team outcome</h2><p>The team score is its best valid design, never the sum of agent objectives. Bars show the fraction of the hypothetical perfect-recovery, zero-column-cost ceiling.</p>'+bars+'<table><tr><th>Open design replay</th><th>Queries</th><th>Best objective</th><th>Reward</th><th>Model cost</th><th>Requests</th></tr>'+''.join(rows)+'</table></section>'+f'<section><h2>Evidence and accounting</h2><p>{s.get("backend_calls","Unavailable")} backend calls; {s.get("cache_hits","Unavailable")} cache hits; {s.get("submissions","Unavailable")} submitted proposals. Charged queries are summed across agents and can differ from backend calls through shared caching.</p><p>Estimated model cost: {money(s.get("known_llm_usd"))}. Unknown-cost requests: {s.get("unknown_cost_requests","Unavailable")}. Memory and simulator/VM dollar charges are unavailable.</p><p>Usage ledgers marked reconciled: {sum((r.get('usage') or {}).get('reconciled') is True for r in agents.values())}/{len(agents)}. Shared-memory configuration: {esc(c.get("memory","Unavailable"))}. This bundle contains saved outcomes and agent replays; it does not by itself establish causal benefit from memory or verify which retrieved evidence changed a decision.</p><p><a href="report-data.json">Reproducible report data</a> · <a href="summary.json">Team summary</a> · <a href="manifest.json">SHA-256 manifest</a></p><details><summary>Run configuration</summary><pre>{esc(json.dumps(c,indent=2))}</pre></details></section></main></html>'
