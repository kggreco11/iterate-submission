"""Prepare or launch Opus against a source-only copy of the Sol 200 runtime.

No credentials travel through Azure Run Command. Provision ANTHROPIC_API_KEY
on the VM as a machine environment variable or in the documented secret file.
"""
import os
import argparse
import base64
import json
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r'C:\iterate-hackathon\azure-runtime-opus-200-20261114'
SOURCE = r'C:\iterate-hackathon\azure-runtime-sol-fast-five-20261114'
SECRET = r'C:\iterate-hackathon\secrets\opus-200\anthropic.env'
PYTHON = r'C:\chemsep-benchmark\venv\Scripts\python.exe'
RUN_ID = 'opus-200-20261114'
OUT = ROOT / 'runs' / 'azure-control'


def invoke(script):
    marker = 'OPUS_' + uuid.uuid4().hex + '='
    command = "$ErrorActionPreference='Stop'\n" + script.replace('OPUS=', marker)
    result = subprocess.run(['az', 'vm', 'run-command', 'invoke', '-g', os.environ['AZURE_RESOURCE_GROUP'],
        '-n', 'chemsep-01', '--command-id', 'RunPowerShellScript', '--scripts', command,
        '-o', 'json'], capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError('Azure command failed; no credentials or remote output displayed')
    messages = '\n'.join(v.get('message', '') for v in json.loads(result.stdout).get('value', []))
    rows = [line[len(marker):] for line in messages.splitlines() if line.startswith(marker)]
    if len(rows) != 1:
        raise RuntimeError('Remote operation did not confirm success')
    return json.loads(rows[0])


def prepare_script():
    encoded = base64.b64encode((ROOT / 'infrastructure/azure/opus200/run_opus.py').read_bytes()).decode()
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
[IO.File]::WriteAllBytes("$r\run_opus.py",[Convert]::FromBase64String('{encoded}'))
$hashes=@{{}}
foreach ($file in @('agents\llm_agent.py','scripts\run_vm_agent.py','sepdesign\env.py','tasks\hc12_dev_000.json')) {{
 $a=(Get-FileHash "$s\$file").Hash; $b=(Get-FileHash "$r\$file").Hash
 if ($a -ne $b) {{ throw 'Source mismatch' }}
 $hashes[$file]=$b
}}
$hashes|ConvertTo-Json|Set-Content "$r\source-hashes.json"
& '{PYTHON}' -m py_compile "$r\run_opus.py"
if ($LASTEXITCODE -ne 0) {{ throw 'Compile failed' }}
$hasKey=![string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','Machine'))
Write-Output ('OPUS='+(@{{state='prepared';machine_key=$hasKey;credential_file=(Test-Path '{SECRET}');hashes=$hashes}}|ConvertTo-Json -Compress))
"""


def launch_script():
    wrapper = rf"""$ErrorActionPreference='Stop'
Set-Location '{REMOTE}'
$env:ANTHROPIC_API_KEY=[Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','Machine')
if (Test-Path '{SECRET}') {{
 $line=Get-Content '{SECRET}' | Where-Object {{ $_ -match '^ANTHROPIC_API_KEY=' }} | Select-Object -First 1
 if ($line) {{ $env:ANTHROPIC_API_KEY=$line.Substring('ANTHROPIC_API_KEY='.Length).Trim() }}
}}
if ([string]::IsNullOrWhiteSpace($env:ANTHROPIC_API_KEY)) {{ throw 'Missing Anthropic key' }}
& '{PYTHON}' run_opus.py --run-id {RUN_ID} --provider anthropic --model claude-opus-5-5 --budget 200 --max-turns 400 > '{REMOTE}\{RUN_ID}.log' 2>&1
exit $LASTEXITCODE
"""
    encoded = base64.b64encode(wrapper.encode()).decode()
    return rf"""
$r='{REMOTE}'
if (!(Test-Path "$r\run_opus.py")) {{ throw 'Prepare first' }}
if (Test-Path "$r\runs\runtime\{RUN_ID}") {{ throw 'Run exists' }}
$hasKey=![string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','Machine'))
if (!$hasKey -and !(Test-Path '{SECRET}')) {{ throw 'Provision Anthropic key first' }}
$name='iterate-runtime-{RUN_ID}'
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {{ throw 'Task exists' }}
[IO.File]::WriteAllBytes("$r\launch.ps1",[Convert]::FromBase64String('{encoded}'))
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File "{REMOTE}\launch.ps1"' -WorkingDirectory $r
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Settings $settings -User 'SYSTEM' -RunLevel Highest | Out-Null
Start-ScheduledTask -TaskName $name
Write-Output 'OPUS={{"state":"launched"}}'
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['prepare', 'launch'])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    result = invoke(prepare_script() if args.action == 'prepare' else launch_script())
    controller = dict(run_id=RUN_ID, model='claude-opus-5-5', task='hc12_dev_000',
        simulator_budget=200, max_turns=400, remote=REMOTE, source_remote=SOURCE,
        provider='anthropic', effort='medium', max_output_tokens=6000,
        automatic_solver_retries=False, max_usd=None, **result)
    path = OUT / (RUN_ID + '-controller.json')
    if args.action == 'launch' and path.exists():
        controller = {**json.loads(path.read_text()), **controller}
    path.write_text(json.dumps(controller, indent=2))
    print(json.dumps(controller, indent=2))


if __name__ == '__main__':
    main()
