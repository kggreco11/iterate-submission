"""Prepare or launch Kimi against a source-only copy of the Sol 200 runtime.

No credentials travel through Azure Run Command. Provision MODAL_PROXY_TOKEN
on the VM as a machine environment variable or in the documented secret file.
"""
import os
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r'C:\iterate-hackathon\azure-runtime-kimi-200-20261114'
SOURCE = r'C:\iterate-hackathon\azure-runtime-sol-fast-five-20261114'
SECRET = r'C:\iterate-hackathon\secrets\kimi-200\modal.env'
PYTHON = r'C:\chemsep-benchmark\venv\Scripts\python.exe'
RUN_ID = 'kimi-200-20261114'
OUT = ROOT / 'runs' / 'azure-control'


def invoke(script):
    marker = 'KIMI_' + uuid.uuid4().hex + '='
    command = "$ErrorActionPreference='Stop'\n" + script.replace('KIMI=', marker)
    for attempt in range(3):
        result = subprocess.run(['az', 'vm', 'run-command', 'invoke', '-g', os.environ['AZURE_RESOURCE_GROUP'],
            '-n', 'chemsep-01', '--command-id', 'RunPowerShellScript', '--scripts', command,
            '-o', 'json'], capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            break
        if '(Conflict)' in result.stderr and attempt < 2:
            print('Azure control slot busy; retrying in 20 seconds.', flush=True)
            time.sleep(20)
            continue
        raise RuntimeError('Azure command failed; no credentials or remote output displayed')
    messages = '\n'.join(v.get('message', '') for v in json.loads(result.stdout).get('value', []))
    rows = [line[len(marker):] for line in messages.splitlines() if line.startswith(marker)]
    if len(rows) != 1:
        raise RuntimeError('Remote operation did not confirm success')
    return json.loads(rows[0])


def prepare_script():
    encoded = base64.b64encode((ROOT / 'infrastructure/azure/kimi200/run_kimi.py').read_bytes()).decode()
    return rf"""
$r='{REMOTE}'
$s='{SOURCE}'
$terminal=Get-Content "$s\runs\runtime\sol-200-20261114\status.json" -Raw | ConvertFrom-Json
if ($terminal.state -notin @('complete','failed')) {{ throw 'Sol must finish first' }}
if (Test-Path $r) {{ throw 'Destination exists; refusing overwrite' }}
New-Item -ItemType Directory -Path $r | Out-Null
foreach ($dir in @('agents','sepdesign','scripts')) {{
 Copy-Item -Recurse -Path "$s\$dir" -Destination "$r\$dir" -Exclude '__pycache__'
}}
New-Item -ItemType Directory -Path "$r\tasks" | Out-Null
Copy-Item "$s\tasks\hc12_dev_000.json" "$r\tasks\hc12_dev_000.json"
[IO.File]::WriteAllBytes("$r\run_kimi.py",[Convert]::FromBase64String('{encoded}'))
$hashes=@{{}}
foreach ($file in @('agents\llm_agent.py','scripts\run_vm_agent.py','sepdesign\env.py','tasks\hc12_dev_000.json')) {{
 $a=(Get-FileHash "$s\$file").Hash; $b=(Get-FileHash "$r\$file").Hash
 if ($a -ne $b) {{ throw 'Source mismatch' }}
 $hashes[$file]=$b
}}
$hashes|ConvertTo-Json|Set-Content "$r\source-hashes.json"
& '{PYTHON}' -m py_compile "$r\run_kimi.py"
if ($LASTEXITCODE -ne 0) {{ throw 'Compile failed' }}
$hasKey=![string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('MODAL_PROXY_TOKEN','Machine'))
Write-Output ('KIMI='+(@{{state='prepared';machine_key=$hasKey;credential_file=(Test-Path '{SECRET}');hashes=$hashes}}|ConvertTo-Json -Compress))
"""


def launch_script():
    wrapper = rf"""$ErrorActionPreference='Stop'
Set-Location '{REMOTE}'
foreach ($key in @('MODAL_PROXY_TOKEN','KIMI_ENDPOINT_URL','KIMI_MODEL')) {{
 [Environment]::SetEnvironmentVariable($key,[Environment]::GetEnvironmentVariable($key,'Machine'),'Process')
}}
if (Test-Path '{SECRET}') {{
 foreach ($line in (Get-Content '{SECRET}')) {{
  if ($line -match '^(MODAL_PROXY_TOKEN|KIMI_ENDPOINT_URL|KIMI_MODEL)=(.+)$') {{
   [Environment]::SetEnvironmentVariable($Matches[1],$Matches[2].Trim(),'Process')
  }}
 }}
}}
foreach ($key in @('MODAL_PROXY_TOKEN','KIMI_ENDPOINT_URL','KIMI_MODEL')) {{
 if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key))) {{ throw 'Missing Modal endpoint configuration' }}
}}
& '{PYTHON}' run_kimi.py --run-id {RUN_ID} --provider openai --model kimi-k3.1-pro --budget 200 --max-turns 400 --max-usd 20 > '{REMOTE}\{RUN_ID}.log' 2>&1
exit $LASTEXITCODE
"""
    encoded = base64.b64encode(wrapper.encode()).decode()
    return rf"""
$r='{REMOTE}'
if (!(Test-Path "$r\run_kimi.py")) {{ throw 'Prepare first' }}
if (Test-Path "$r\runs\runtime\{RUN_ID}") {{ throw 'Run exists' }}
$hasKey=![string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('MODAL_PROXY_TOKEN','Machine'))
if (!$hasKey -and !(Test-Path '{SECRET}')) {{ throw 'Provision Modal endpoint configuration first' }}
$name='iterate-runtime-{RUN_ID}'
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {{ throw 'Task exists' }}
[IO.File]::WriteAllBytes("$r\launch.ps1",[Convert]::FromBase64String('{encoded}'))
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File "{REMOTE}\launch.ps1"' -WorkingDirectory $r
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Settings $settings -User 'SYSTEM' -RunLevel Highest | Out-Null
Start-ScheduledTask -TaskName $name
Write-Output 'KIMI={{"state":"launched"}}'
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['prepare', 'launch'])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    result = invoke(prepare_script() if args.action == 'prepare' else launch_script())
    controller = dict(run_id=RUN_ID, model='kimi-k3.1-pro', task='hc12_dev_000',
        simulator_budget=200, max_turns=400, remote=REMOTE, source_remote=SOURCE,
        provider='openai', effort='provider default', max_output_tokens=6000,
        automatic_solver_retries=False, max_usd=20, **result)
    path = OUT / (RUN_ID + '-controller.json')
    if args.action == 'launch' and path.exists():
        controller = {**json.loads(path.read_text()), **controller}
    path.write_text(json.dumps(controller, indent=2))
    print(json.dumps(controller, indent=2))


if __name__ == '__main__':
    main()
