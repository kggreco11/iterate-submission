"""Install automatic report completion hooks in existing VM runtime deployments."""
import base64,json,sys
from pathlib import Path
from finalize_vm_report import remote, ROOT
source=base64.b64encode((ROOT/'sepdesign/report.py').read_bytes()).decode()
for arg in sys.argv[1:]:
 config=json.loads(Path(arg).read_text());root=config['remote'];run=root+'\\runs\\runtime\\'+config['run_id'];name='iterate-report-'+config['run_id']
 waiter=f'''import sys,time,json
from pathlib import Path
sys.path.insert(0,{root!r})
from sepdesign.report import build
run=Path({run!r})
for _ in range(1440):
 try:state=json.loads((run/'status.json').read_text()).get('state')
 except (OSError,ValueError):state=None
 if state in ('complete','failed'):
  build(run)
  break
 time.sleep(10)
'''
 hook='''    folder = os.path.dirname(os.path.abspath(path))
    if os.path.exists(os.path.join(folder, 'summary.json')) and os.path.exists(os.path.join(folder, 'turns.jsonl')):
        try:
            from sepdesign.report import build
            build(folder)
        except Exception as exc:
            with open(os.path.join(folder, 'report_failure.json'), 'w') as failure:
                json.dump({'error_type': type(exc).__name__}, failure)
    return out'''
 final_hook='''\n    finally:
        # Final report after terminal status.
        if (run / 'replay.json').exists():
            try:
                from sepdesign.report import build
                build(run)
            except Exception as exc:
                atomic_json(run / 'report_failure.json', {'error_type': type(exc).__name__})
'''
 ps=f'''$ErrorActionPreference='Stop'
$action=New-ScheduledTaskAction -Execute 'C:\\chemsep-benchmark\\venv\\Scripts\\python.exe' -Argument '"{root}\\wait_for_report.py"' -WorkingDirectory '{root}'
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 5) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName '{name}' -Action $action -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName '{name}'
'''
 print(remote(f'''from pathlib import Path
import base64,subprocess
root=Path({root!r})
(root/'sepdesign/report.py').write_bytes(base64.b64decode({source!r}))
p=root/'sepdesign/runlog.py';text=p.read_text()
if '"reward_norm":' not in text:
 text=text.replace('"backend": backend', '"reward_norm": env.econ.reward_norm, "backend": backend')
 p.write_text(text)
if 'from sepdesign.report import build' not in text:
 assert text.count('    return out')==1
 p.write_text(text.replace('    return out',{hook!r}))
runner=root/'scripts/run_vm_agent.py'
runner_text=runner.read_text()
if '# Final report after terminal status.' not in runner_text:
 runner_text=runner_text.replace('\\n\\nif __name__', {final_hook!r}+'\\n\\nif __name__')
 compile(runner_text,str(runner),'exec')
 runner.write_text(runner_text)
(root/'wait_for_report.py').write_text({waiter!r})
r=subprocess.run(['powershell.exe','-NoProfile','-Command',{ps!r}],capture_output=True,text=True)
assert r.returncode==0, 'Report task registration failed'
print('REPORT=installed:{config['run_id']}')
'''),flush=True)
