"""Self-contained reports for persistent agent runs; no simulator calls or network."""
import json
from pathlib import Path


def collect(run):
    run = Path(run)
    def read(name):
        p = run / name
        return json.loads(p.read_text()) if p.exists() else {}
    def rows(name):
        p = run / name
        return [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []
    replay = read('replay.json')
    if not replay:
        raise ValueError('Replay has not been saved yet')
    return dict(summary=read('summary.json'), replay=replay, turns=rows('turns.jsonl'),
                usage=[{k:r.get(k) for k in ('elapsed_s','input_tokens','output_tokens','usd','usd_label')} for r in rows('usage.jsonl')],
                runtime=read('runtime.json'), status=read('status.json'))


def build(run, data=None, archive=True):
    run = Path(run)
    data = data or collect(run)
    output = run / 'report.html'
    output.parent.mkdir(parents=True, exist_ok=True)
    html = TEMPLATE.replace('__DATA__', json.dumps(data).replace('<', '\\u003c'))
    temporary = output.with_suffix('.html.tmp')
    temporary.write_text(html, encoding='utf-8')
    temporary.replace(output)
    if archive:
        project = Path(__file__).resolve().parents[1]
        try:
            relative = run.resolve().relative_to(project / 'runs')
        except ValueError:
            relative = None
        state = data.get('status', {}).get('state')
        if relative is not None and state in ('complete', 'failed') and 'raw' not in relative.parts:
            from sepdesign.report_archive import publish
            publish(data, project)
    return output


TEMPLATE = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Engineering run report</title>
<style>*{box-sizing:border-box}body{font:15px system-ui;color:#192a3d;background:#f5f7fa;max-width:1440px;margin:auto;padding:32px}h1{margin:8px 0}h2{font-size:19px}.muted,small{color:#53677f}.cards,.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}.grid{grid-template-columns:1fr 1fr}.card,section{background:white;border:1px solid #d9e1eb;border-radius:12px;padding:20px}.value{font-size:28px;font-weight:650;margin-top:10px}.wide{grid-column:1/-1}svg.chart{width:100%;height:270px}svg text{font-family:system-ui;font-size:11px;fill:#53677f}button{padding:9px 14px;border:0;border-radius:6px;background:#264963;color:white;cursor:pointer}input{width:100%;margin:18px 0}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid #dce3eb;font-size:13px}pre{white-space:pre-wrap}.scroll{overflow:auto}.note{padding:16px;background:#eaf3f8;line-height:1.6}#flow{overflow:auto;max-height:650px}#flow svg{min-width:700px}button:focus-visible,input:focus-visible{outline:3px solid #16825f}@media(max-width:800px){.cards,.grid{grid-template-columns:1fr}body{padding:16px}}</style>
<header><small>ITERATE / SINGLE AGENT EXPERIMENT</small><h1 id="title"></h1><p id="subtitle" class="muted"></p></header><div class="cards" id="cards"></div><p class="note">The objective is the best valid annual economic value found. The hypothetical ceiling assumes perfect pure-product recovery with zero column cost; it is not a demonstrated feasible plant. Flowsheet replay records improvements to the best design. All evaluated submissions appear in the history below. Values use the benchmark's economic assumptions.</p>
<div class="grid"><section><h2>Quality versus simulator budget</h2><svg class="chart" id="budget"></svg></section><section><h2>Quality versus elapsed time</h2><svg class="chart" id="time"></svg><small>Recorded best-design improvements; elapsed time includes model and local evaluation.</small></section>
<section class="wide"><h2>Flowsheet replay</h2><button id="prev">Previous</button> <button id="play">Play</button> <button id="next">Next</button> <button id="best">Best design</button><span id="position" style="margin-left:16px"></span><input id="slider" type="range" min="0" value="0" aria-label="Best-design improvement"><div id="replaystats"></div><div id="flow"></div><h3>Products</h3><div class="scroll"><table id="products"></table></div></section>
<section><h2>Run metrics</h2><table id="metrics"></table></section><section><h2>Model usage and timing</h2><table id="usage"></table><p id="cost"></p></section><section class="wide"><h2>Submission history</h2><div class="scroll"><table id="history"></table></div></section></div><details><summary>Run configuration and provenance</summary><pre id="config"></pre></details><p class="muted" id="footer"></p>
<script>const D=__DATA__;
const $=id=>document.getElementById(id),fmt=(x,n=2)=>Number(x).toLocaleString(undefined,{maximumFractionDigits:n}),S=D.summary,R=D.replay,T=R.trace||[],U=D.usage,ns='http://www.w3.org/2000/svg';
const last=T.at(-1),norm=R.reward_norm||(last&&last.reward?(last.revenue-last.tac)/last.reward:1),ceiling=R.upper_bound_reward*norm/1e6,best=R.best_reward*norm/1e6;
function el(n,a={},text){const e=document.createElementNS(ns,n);for(const k in a)e.setAttribute(k,a[k]);if(text!==undefined)e.textContent=text;return e}
function table(id,rows,headers){const t=$(id);if(headers){let tr=t.insertRow();headers.forEach(x=>{let th=document.createElement('th');th.textContent=x;tr.append(th)})}rows.forEach(r=>{const tr=t.insertRow();r.forEach(v=>tr.insertCell().textContent=v??'Unavailable')})}
document.title=(S.model||'Agent')+' · '+R.budget+'-call report';$('title').textContent=(S.model||'Agent')+' · engineering run';$('subtitle').textContent=`${R.task} · ${R.budget} simulator calls allowed · ${S.status||D.status.state||'Saved result'}`;
[['Best objective',`$${fmt(best)}M/year`],['Ceiling attained',`${fmt(best/ceiling*100,1)}%`],['Simulator calls',`${R.solves_used}/${R.budget}`],['Elapsed time',`${fmt(R.wall_s/60,1)} minutes`]].forEach(([k,v])=>{let c=document.createElement('div');c.className='card';let a=document.createElement('small');a.textContent=k;let b=document.createElement('div');b.className='value';b.textContent=v;c.append(a,b);$('cards').append(c)});
function chart(id,points,key,label){const s=$(id);s.setAttribute('viewBox','0 0 600 270');let xmax=Math.max(1,...points.map(p=>p[key])),ymax=Math.max(ceiling*1.1,1),x=v=>65+v/xmax*510,y=v=>220-v/ymax*190;for(let i=0;i<=4;i++){let v=ymax*i/4;s.append(el('line',{x1:65,x2:575,y1:y(v),y2:y(v),stroke:'#dce3eb'}),el('text',{x:58,y:y(v)+4,'text-anchor':'end'},fmt(v,0)),el('text',{x:x(xmax*i/4),y:240,'text-anchor':'middle'},fmt(xmax*i/4,1)))}s.append(el('line',{x1:65,x2:575,y1:y(ceiling),y2:y(ceiling),stroke:'#b17922','stroke-dasharray':'7 5'}),el('text',{x:570,y:y(ceiling)-7,'text-anchor':'end'},'Hypothetical ceiling'),el('text',{x:300,y:264},label));let path='M65,220';for(const p of points)path+=` H${x(p[key])} V${y(p.best)}`;s.append(el('path',{d:path,fill:'none',stroke:'#16825f','stroke-width':3}));for(const p of points){let c=el('circle',{cx:x(p[key]),cy:y(p.best),r:3,fill:'#16825f'});c.append(el('title',{},`${fmt(p[key])} ${label}: $${fmt(p.best)}M/year`));s.append(c)}}
let running=0;const submissions=D.turns.filter(t=>t.reward!==undefined),points=submissions.map(t=>{if(t.valid)running=Math.max(running,t.reward);return {solves:t.solves_used,best:running*norm/1e6}});chart('budget',points,'solves','Simulator calls');chart('time',T.map(t=>({minutes:t.wall_s/60,best:t.reward*norm/1e6})),'minutes','Minutes');
table('metrics',[['Stop reason',S.status],['Evaluated submissions',submissions.length],['Valid submissions',submissions.filter(t=>t.valid).length],['Simulator failures',D.runtime.service?.failed],['Median solve (seconds)',D.runtime.service?.median_s],['Best plant columns',last?Object.keys(last.columns).length:0],['Hypothetical ceiling ($M/year)',fmt(ceiling)],['Annual revenue ($M/year)',last?fmt(last.revenue/1e6):null],['Annual column cost ($M/year)',last?fmt(last.tac/1e6):null]]);
table('usage',[['Model requests',S.requests],['Failed requests',S.failed_requests],['Input tokens',fmt(S.input_tokens,0)],['Output tokens',fmt(S.output_tokens,0)],...Object.entries(D.runtime.phase_seconds||{}).map(([k,v])=>[k+' (seconds)',fmt(v)])]);$('cost').textContent=S.requests_with_unknown_cost?'Model cost unavailable: pricing is not configured for all requests.':`Estimated model cost: $${fmt(S.usd_estimated_total,5)}; excludes VM.`;
running=0;table('history',D.turns.map(t=>{if(t.valid)running=Math.max(running,t.reward);return [t.turn,t.solves_used,t.valid===undefined?t.action:t.valid?'Yes':'No',t.reward===undefined?'—':fmt(t.reward*norm/1e6),fmt(running*norm/1e6),t.note||t.error||'']}),['Turn','Solves','Valid / action','Candidate $M/year','Best $M/year','Agent intent / feedback']);
let index=0,timer=null;function stop(){clearInterval(timer);timer=null;$('play').textContent='Play'}
function draw(i){if(!T.length){$('flow').textContent='No valid improvement snapshots recorded.';return}index=Math.max(0,Math.min(T.length-1,i));const t=T[index];$('slider').value=index;$('position').textContent=`Improvement ${index+1} / ${T.length}`;$('replaystats').textContent=`${t.solves}/${R.budget} solves · $${fmt(t.reward*norm/1e6)}M/year · ${fmt(t.wall_s/60,1)} minutes`;
let nodes=[],leaf=0;function visit(p){let n={p,c:t.columns[p],product:t.products.find(x=>x.node===p),x:40+p.length*210};nodes.push(n);if(n.c){n.top=visit(p+'T');if(n.c.side)n.side=visit(p+'S');n.bottom=visit(p+'B');n.y=(n.top.y+n.bottom.y)/2}else n.y=55+leaf++*95;return n}visit('');let width=Math.max(...nodes.map(n=>n.x))+200,height=Math.max(200,leaf*95+20),svg=el('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Best plant flowsheet'});svg.style.width=width+'px';svg.style.height=height+'px';for(const n of nodes){if(n.c)for(const [child,label] of [[n.top,'T'],...(n.side?[[n.side,'S']]:[]),[n.bottom,'B']])svg.append(el('path',{d:`M${n.x+170},${n.y} H${n.x+190} V${child.y} H${child.x}`,fill:'none',stroke:'#8294a8'}),el('text',{x:n.x+185,y:child.y-5},label));let g=el('g');g.append(el('rect',{x:n.x,y:n.y-32,width:170,height:64,rx:n.c?16:5,fill:n.c?'#edf3fb':n.product?.value>0?'#e1f3e9':'#f1f3f6',stroke:'#9aabba'}),el('text',{x:n.x+10,y:n.y-12},(n.c?(n.c.double_effect?'Double effect ':'Column '):'Outlet ')+(n.p||'feed')),el('text',{x:n.x+10,y:n.y+5},n.c?`${n.c.n_stages} stages · R ${n.c.reflux}`:(n.product?.kind?.startsWith('blend:')?n.product.kind:n.product?.component)||'No product'),el('text',{x:n.x+10,y:n.y+22},n.c?`Reboil ${n.c.reboil} · ΔP ${n.c.dp}`:n.product?`${fmt(n.product.purity*100)}% · $${fmt(n.product.value/1e6)}M`:'No recorded value'));g.append(el('title',{},JSON.stringify(n.c||n.product||{})));svg.append(g)}$('flow').replaceChildren(svg);$('products').replaceChildren();table('products',t.products.map(p=>[p.node||'feed',p.kind||'Unrecorded',p.component,fmt(p.purity*100)+'%',fmt(p.flow_mol_s),fmt(p.value/1e6)]),['Outlet','Sale grade','Main component','Main component fraction','Flow mol/s','Value $M/year'])}
$('slider').max=Math.max(0,T.length-1);$('slider').oninput=e=>{stop();draw(+e.target.value)};$('prev').onclick=()=>{stop();draw(index-1)};$('next').onclick=()=>{stop();draw(index+1)};$('best').onclick=()=>{stop();draw(T.length-1)};$('play').onclick=()=>{if(timer){stop();return}if(index===T.length-1)draw(0);$('play').textContent='Pause';timer=setInterval(()=>{if(index>=T.length-1)stop();else draw(index+1)},1200)};draw(T.length-1);$('config').textContent=JSON.stringify({summary:S,backend:R.backend,budget:R.budget,task:R.task,status:D.status},null,2);$('footer').textContent=S.run_id||R.label;
</script></html>'''

if __name__ == '__main__':
    import sys
    print(build(Path(sys.argv[1])))


def build_swarm(root, summary, config, archive=True):
    """Aggregate landing page linking independent per-agent replay reports."""
    import html
    root = Path(root)
    rows = []
    for agent, result in summary['agents'].items():
        replay = json.loads((root / 'raw' / agent / 'replay.json').read_text())
        objective = (result['best_valid_reward'] or 0) * replay['reward_norm'] / 1e6
        budget = replay['budget']
        rows.append(f'<tr><td><a href="raw/{agent}/report.html">{agent}</a></td>'
                    f'<td>{result["distinct_queries"]}/{budget}</td><td>${objective:,.2f}M/year</td></tr>')
    content = ('<!doctype html><meta charset="utf-8"><title>Swarm report</title>'
        '<style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:20px}'
        'td,th{padding:14px;text-align:left}pre{white-space:pre-wrap}</style>'
        f'<h1>{html.escape(config["model"])} · {len(rows)}-agent swarm</h1>'
        f'<p>{html.escape(config["task"])} · {html.escape(summary["status"])}</p>'
        f'<p>{summary["team_distinct_queries"]}/{sum(config["allocations"])} charged simulator calls; '
        f'{summary["backend_calls"]} backend calls. Click an agent for its replay.</p>'
        f'<p>Estimated model cost: ${summary["known_llm_usd"]:.4f}; '
        f'{summary["unknown_cost_requests"]} requests with unknown cost. Memory and VM costs excluded.</p>'
        '<table><tr><th>Agent</th><th>Simulator calls</th><th>Best objective</th></tr>'
        + ''.join(rows) + '</table><details><summary>Configuration</summary><pre>'
        + html.escape(json.dumps(config, indent=2)) + '</pre></details>')
    (root / 'report.html').write_text(content, encoding='utf-8')
    if archive:
        project = Path(__file__).resolve().parents[1]
        try:
            root.resolve().relative_to(project / 'runs')
        except ValueError:
            pass
        else:
            from sepdesign.report_archive import publish_swarm
            publish_swarm(dict(summary=summary, config=config,
                agents={agent:collect(root/'raw'/agent) for agent in summary['agents']}), project)
    return root / 'report.html'
