"""Run one bounded V2 single-agent/swarm comparison, sequentially on the VM."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sepdesign.runtime import atomic_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--task', type=Path, default=ROOT/'tasks/hc16v2_dev_000.json')
    a = ap.parse_args()
    control = ROOT/'runs'/a.run_id
    control.mkdir(parents=True, exist_ok=False)
    task = str(a.task.resolve())
    common = ['--task',task,'--provider','modal','--model','kimi-k3.1-pro','--backend','chemsep']
    os.environ['CHEMSEP_DIR'] = r'C:\Users\chemsepadmin\Desktop'
    atomic_json(control/'status.json', {'state':'single_running'})
    commands = [
        ('single', [sys.executable, str(ROOT/'scripts/run_vm_agent.py'), *common,
            '--run-id',a.run_id+'-single','--budget','200','--max-turns','400']),
        ('swarm', [sys.executable, str(ROOT/'scripts/run_swarm.py'), *common,
            '--agents','5','--mode','equal-per-agent','--budget','100','--rounds','200',
            '--memory','past','--out',str(ROOT/'runs')])]
    try:
        for name, command in commands:
            atomic_json(control/'status.json', {'state':name+'_running'})
            with (control/(name+'.log')).open('w') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(name+' process failed')
            if name == 'single':
                state=json.loads((ROOT/'runs/runtime'/(a.run_id+'-single')/'status.json').read_text())
                if state['state'] != 'complete':
                    raise RuntimeError('Single-agent run failed; swarm not started')
        atomic_json(control/'status.json', {'state':'complete'})
    except BaseException as exc:
        atomic_json(control/'status.json', {'state':'failed','phase':name,'error_type':type(exc).__name__})
        raise


if __name__ == '__main__':
    main()
