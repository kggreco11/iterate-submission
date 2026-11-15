"""Correct backend-call curves using measured column executions, including cached calls and cleanup."""
import json,lzma,base64,hashlib
from pathlib import Path
BASE=Path(r'C:\iterate-hackathon')
patches={}
for dep in BASE.glob('*v3*400*'):
 for camp in (dep/'runs/controls').glob('controls-*'):
  for cp in (camp/'runs').rglob('config.json'):
   run=cp.parent;c=json.loads(cp.read_text())
   if not c.get('allocations') or not all(n==400 for n in c['allocations']) or not (run/'metrics/summary.json').exists():continue
   ev=[json.loads(l) for l in (run/'raw/trajectory.jsonl').read_text().splitlines()];sim=json.loads((run/'raw/simulator.json').read_text());s=json.loads((run/'metrics/summary.json').read_text())
   pos=back=0;best={};cleanup={};points=[]
   def calls(m):return sum(2 if n['column_result'].get('effects') else 1 for n in (m or {}).get('nodes',{}).values() if 'column_result' in n)
   for e in ev:
    key=(e.get('agent'),e.get('round'));m=e.get('measured') or {}
    if e['kind']=='budget_cleanup':cleanup[key]=calls(e['original_result'])
    if e['kind'] not in ('submission','initial_design'):continue
    n=calls(m)+cleanup.pop(key,0);batch=sim[pos:pos+n];pos+=n;back+=sum(x['backend_call'] for x in batch)
    if m.get('valid') and (key[0] not in best or m['reward']>best[key[0]]):
     best[key[0]]=m['reward'];points.append([key[0],key[1],back])
   patches[c['run_id']]={'points':points,'verified':pos==len(sim) and back==s['backend_calls'],'service_events_mapped':pos,'service_events_total':len(sim),'backend_calls_mapped':back,'backend_calls_summary':s['backend_calls']}
p=BASE/'v3-backend-patch.json.xz';packed=lzma.compress(json.dumps(patches,separators=(',',':')).encode());p.write_bytes(packed)
print(json.dumps({'bytes':len(packed),'sha256':hashlib.sha256(packed).hexdigest(),'data':base64.b64encode(packed).decode() if len(packed)<=2700 else None}))
