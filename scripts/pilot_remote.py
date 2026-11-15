"""One persisted pilot evaluation on the Windows simulator; no API credentials."""
import base64, gzip, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sepdesign import make_env, make_service
from sepdesign.env import EditError

root = Path(__file__).resolve().parents[1]
run = root / 'runs' / sys.argv[1]
run.mkdir(parents=True, exist_ok=True)
state_path = run / 'state.json'
svc = make_service('chemsep', retry=False)
env = make_env(json.loads((root/'tasks/hc12_dev_000.json').read_text()), svc, budget=50)
def key(q):
    return (tuple(q[0]), *q[1:])
if state_path.exists():
    state = json.loads(state_path.read_text())
    env.design = state['design']; env.best = state['best']; env.curve = state['curve']
    env.paid = {key(q) for q in state['paid']}
    svc.cache = {key(q): v for q, v in state['cache']}; svc.log = state['log']
else:
    env.evaluate()
raw_path = run/'simulator.jsonl'
original = svc.backend.solve_column
def logged(case):
    result = original(case)
    with raw_path.open('a') as f: f.write(json.dumps({'case':case,'result':result})+'\n')
    return result
svc.backend.solve_column = logged
edits = json.loads(base64.b64decode(sys.argv[2]))
t0 = time.perf_counter()
error = None
try:
    result = env.step(edits)
except (EditError, ValueError, TypeError, KeyError) as ex:
    error = str(ex)
    result = env.evaluate()
elapsed = time.perf_counter()-t0
state = dict(design=env.design,best=env.best,curve=env.curve,paid=list(env.paid),cache=list(svc.cache.items()),log=svc.log)
state_path.write_text(json.dumps(state))
with (run/'evaluations.jsonl').open('a') as f:
    f.write(json.dumps({'edits':edits,'design':env.design,'result':result,'evaluation_s':elapsed,'error':error})+'\n')
# Keep Azure's bounded output small; full simulator evidence stays on disk.
feedback = dict(error=error,solves_used=env.solves_used,best_reward=env.score(),reward=result['reward'],valid=result['valid'],
                design=env.design,best_design=env.best[1],evaluation_s=elapsed,stats=svc.stats(),feedback=env.render(result,top=5))
print('PILOT='+base64.b64encode(gzip.compress(json.dumps(feedback).encode())).decode())
