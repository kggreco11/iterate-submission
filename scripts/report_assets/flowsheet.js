let replayIndex=0,replayTimer=null;
function stopReplay(){if(replayTimer)clearInterval(replayTimer);replayTimer=null;$('replay-play').textContent='▶ Play'}
function drawReplay(index){
 replayIndex=Math.max(0,Math.min(D.rows.length-1,index));const row=D.rows[replayIndex],f=row.feedback,p=D.points[replayIndex+1],design=f.design;
 $('replay-position').textContent=`${replayIndex+1} / ${D.rows.length}`;$('replay-slider').value=replayIndex;
 const m=f.feedback.match(/revenue \$([\d.]+)M\/yr \| column cost \$([\d.]+)M\/yr/);
 $('replay-metrics').innerHTML=[['Candidate objective',`$${fmt(p.current)}M/yr`],['Best so far',`$${fmt(p.best)}M/yr`],['Validity / calls',`${f.valid?'Valid':'INVALID'} · ${p.solves}/50`],['Revenue / column cost',m?`$${m[1]}M / $${m[2]}M`:'Unavailable']].map(a=>`<div class="card" style="padding:12px"><small>${a[0]}</small><div style="font-size:19px;font-weight:650;margin-top:8px">${a[1]}</div></div>`).join('');
 $('replay-reason').textContent=row.proposal.reason+(f.error?' Rejected edit: '+f.error:'');
 const observed={};for(const line of f.feedback.split('\n')){const a=line.match(/^\[([^\]]+)\] (.*?) -> (.*)$/);if(a)observed[a[1]==='feed'?'':a[1]]={feed:a[2],result:a[3],line};}
 const nodes=[];let leaf=0;
 function visit(path){let n={path,depth:path.length,settings:design[path],obs:observed[path]};nodes.push(n);if(n.settings){n.top=visit(path+'T');n.bottom=visit(path+'B');n.y=(n.top.y+n.bottom.y)/2;}else n.y=65+leaf++*100;n.x=80+n.depth*235;return n;}
 const root=visit(''),width=310+Math.max(...nodes.map(n=>n.depth))*235,height=Math.max(260,leaf*100+35);
 const svg=el('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':`Flowsheet for submission ${replayIndex+1}`});svg.style.width=width+'px';svg.style.height=height+'px';svg.style.display='block';
 const defs=el('defs',{}),marker=el('marker',{id:'flow-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});marker.append(el('path',{d:'M0 0L10 5L0 10z',fill:'#8294a8'}));defs.append(marker);svg.append(defs);
 for(const n of nodes){if(!n.settings)continue;for(const [child,label] of [[n.top,'T'],[n.bottom,'B']]){svg.append(el('path',{d:`M${n.x+170} ${n.y} H${n.x+195} V${child.y} H${child.x}`,fill:'none',stroke:'#8294a8','stroke-width':1.5,'marker-end':'url(#flow-arrow)'}));svg.append(el('text',{x:n.x+199,y:child.y-5},label));}}
 const prev=replayIndex?D.rows[replayIndex-1].feedback.design:{};
 function select(n){const s=n.settings;let lines=[`Stream path: ${n.path||'feed'}`,s?'Distillation column':'Terminal stream',''];if(s)lines.push(`Stages: ${s[0]}`,`Reflux ratio: ${s[1]}`,`Reboil ratio: ${s[2]}`,`Pressure drop fraction: ${s[3]}`,'');lines.push(n.obs?n.obs.feed:'No stream observation recorded',n.obs?n.obs.result:'Not evaluated or unreachable in this submission');$('replay-detail').textContent=lines.join('\n');}
 for(const n of nodes){const sale=n.obs?.result.match(/sold for \$([\d.]+)M/),valuable=sale&&Number(sale[1])>0,failed=!n.obs||/failed|not_solved|negligible/.test(n.obs.result),changed=n.settings&&JSON.stringify(n.settings)!==JSON.stringify(prev[n.path]);const g=el('g',{tabindex:0,role:'button','aria-label':`${n.settings?'Column':'Outlet'} ${n.path||'feed'}`});g.style.cursor='pointer';g.append(el('rect',{x:n.x,y:n.y-35,width:170,height:70,rx:n.settings?18:6,fill:failed?'#fff1ef':valuable?'#e1f3e9':n.settings?'#edf3fb':'#f1f3f6',stroke:failed?'#c66d59':changed?'#287ac1':valuable?'#218460':'#9aabba','stroke-width':changed?3:1.5}));
 if(n.settings)for(let dy of [-15,0,15])g.append(el('line',{x1:n.x+8,x2:n.x+22,y1:n.y+dy,y2:n.y+dy,stroke:'#9aabba'}));
 g.append(el('text',{x:n.x+30,y:n.y-15,style:'font-weight:650;fill:#243d55'},(n.settings?'Column ':'Outlet ')+(n.path||'feed')));
 g.append(el('text',{x:n.x+30,y:n.y+2},n.settings?`${n.settings[0]} stages · R ${n.settings[1]}`:valuable?`Product: $${sale[1]}M/yr`:failed?'Not evaluated':'Off-spec / $0'));
 g.append(el('text',{x:n.x+30,y:n.y+19},n.obs?(n.obs.feed.match(/^([\d.]+ mol\/s)/)?.[1]||'Flow unavailable'):'Flow unavailable'));
 const title=el('title',{},n.obs?n.obs.line:'No simulator observation');g.append(title);g.onclick=()=>select(n);g.onkeydown=e=>{if(e.key==='Enter'){select(n);e.preventDefault();}};svg.append(g);}
 $('replay-diagram').replaceChildren(svg);select(root);
}
$('replay-slider').max=D.rows.length-1;$('replay-slider').oninput=e=>{stopReplay();drawReplay(+e.target.value)};
$('replay-prev').onclick=()=>{stopReplay();drawReplay(replayIndex-1)};$('replay-next').onclick=()=>{stopReplay();drawReplay(replayIndex+1)};
$('replay-best').onclick=()=>{stopReplay();const best=Math.max(...D.rows.filter(r=>r.feedback.valid).map(r=>r.feedback.reward));drawReplay(D.rows.findIndex(r=>r.feedback.valid&&r.feedback.reward===best));};
$('replay-play').onclick=()=>{if(replayTimer){stopReplay();return}if(replayIndex===D.rows.length-1)drawReplay(0);$('replay-play').textContent='Ⅱ Pause';replayTimer=setInterval(()=>{if(replayIndex>=D.rows.length-1){stopReplay();return}drawReplay(replayIndex+1)},1500)};
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA')return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();stopReplay();drawReplay(replayIndex+(e.key==='ArrowRight'?1:-1));}else if(e.code==='Space'&&$('replay-play').closest('section').contains(e.target)&&!['BUTTON','SUMMARY'].includes(e.target.tagName)){e.preventDefault();$('replay-play').click();}});
$('replay-best').click();