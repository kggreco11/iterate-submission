"""Live backend smoke/first-cut check; never substitutes mock results."""
import base64,gzip,hashlib,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sepdesign import make_env,make_service,baselines
from sepdesign.chemsep_lib import find_chemsep

root=Path(__file__).resolve().parents[1]
out=root/'results/hc12-qualification'
out.mkdir(parents=True,exist_ok=True)
task=json.loads((root/'tasks/hc12_dev_000.json').read_text())
svc=make_service('chemsep',names=task['components'])
raw=[]
original=svc.backend.solve_column

def logged(case):
    r=original(case); raw.append({'case':case,'result':r})
    (out/'calls.json').write_text(json.dumps(raw))
    return r
svc.backend.solve_column=logged
t0=time.perf_counter()
env=make_env(task,svc,budget=24,max_columns=12)
empty=env.evaluate()
first=baselines.first_cut(env)
report={'task':task['task_id'],'backend':svc.backend_name,'chemsep_dir':find_chemsep(),
    'task_sha256':hashlib.sha256((root/'tasks/hc12_dev_000.json').read_bytes()).hexdigest(),
    'source_hashes':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'sepdesign').glob('*.py'))},
    'empty_valid':empty['validation']['eligible'],'best_reward':env.score(),'best_design':env.best[1] if env.best else None,
    'best_result':env.best[2] if env.best else None,'final_validation':first['validation'],'final_reward':first['reward'],
    'final_design':env.design,'service':svc.stats(),'wall_s':time.perf_counter()-t0,
    'note':'First-cut qualification, not agent experiment; tolerances provisional and energy closure unverified.'}
(out/'report.json').write_text(json.dumps(report,indent=2))
summary={k:v for k,v in report.items() if k not in ['source_hashes','best_result','best_design','final_design']}
print(json.dumps(summary,indent=2))
