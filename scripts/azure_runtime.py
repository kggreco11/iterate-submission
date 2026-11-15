"""Credential-free Azure control plane for isolated persistent runtimes.

Deployment includes only allowlisted tracked source. Never copies .env or runs.
The scripted provider is intentional: paid providers require a separate approved
VM credential destination/security decision, and are launched on the VM itself.
"""
import os
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import time
import zipfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
PYTHON = r'C:\chemsep-benchmark\venv\Scripts\python.exe'


def bundle():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(paths)):
            if (name.startswith('sepdesign/') and name.endswith('.py')) or name in {
                'agents/llm_agent.py', 'agents/kimi.py', 'scripts/run_swarm.py', 'scripts/run_controls.py', 'scripts/run_v2_kimi_pair.py', 'scripts/run_vm_agent.py', 'tasks/hc12_dev_000.json', 'tasks/hc16v2_dev_000.json',
                'sepdesign/data/column_pr76.sep.tmpl', 'sepdesign/data/cost_params.json'}:
                archive.writestr(name, (ROOT / name).read_bytes())
    return output.getvalue()


def invoke(script, log, operation='diagnostic', *, run_id):
    operation_id = uuid.uuid4().hex
    marker = f'RUNTIME:{run_id}:{operation}:{operation_id}='
    script = script.replace('RUNTIME=', marker)
    start = time.perf_counter()
    p = subprocess.run(['az', 'vm', 'run-command', 'invoke', '--resource-group', os.environ['AZURE_RESOURCE_GROUP'],
                        '--name', 'chemsep-01', '--command-id', 'RunPowerShellScript', '--scripts',
                        "$ErrorActionPreference='Stop';\n" + script, '--output', 'json'], capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    with log.open('a') as f:
        f.write(json.dumps(dict(operation=operation, run_id=run_id, operation_id=operation_id, control_plane_s=elapsed, returncode=p.returncode)) + '\n')
    if p.returncode:
        match = re.search(r'ERROR: \(([A-Za-z0-9_.-]+)\)', p.stderr)
        reason = match.group(1) if match else 'CLI request failed'
        if reason == 'Conflict':
            raise RuntimeError('Azure control slot is busy; another status or report request is active')
        raise RuntimeError('Azure control command failed: ' + reason)
    data = json.loads(p.stdout)
    messages = '\n'.join(v.get('message', '') for v in data.get('value', []))
    matches = [line.split(marker, 1)[1].strip() for line in messages.splitlines() if line.startswith(marker)]
    if len(matches) != 1:
        raise RuntimeError('Remote response missing, duplicated, or mismatched operation marker; output withheld')
    return matches[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['deploy', 'launch', 'status', 'report', 'export'])
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--budget', type=int, default=50)
    ap.add_argument('--backend', choices=['chemsep', 'mock'], default='chemsep')
    ap.add_argument('--pilot-dir', type=Path, required=True, help='Frozen pilot directory; terminal marker required before every Azure operation')
    ap.add_argument('--out', type=Path, default=ROOT / 'runs' / 'azure-control')
    a = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', a.run_id):
        ap.error('invalid run-id')
    if not any((a.pilot_dir / name).is_file() for name in ('summary.json', 'failure.json')):
        ap.error('frozen pilot is not terminal; no Azure command issued')
    if a.budget < 1 or a.budget > 50:
        ap.error('budget must be 1..50 for this transport validation launcher')
    a.out.mkdir(parents=True, exist_ok=True)
    log = a.out / (a.run_id + '-transport.jsonl')
    remote = 'C:\\iterate-hackathon\\azure-runtime-' + a.run_id
    run = remote + '\\runs\\runtime\\' + a.run_id
    if a.action == 'deploy':
        content = bundle()
        encoded = base64.b64encode(content).decode()
        digest = hashlib.sha256(content).hexdigest()
        script = f"""
if (Test-Path '{remote}') {{ throw 'Deployment already exists' }}
New-Item -ItemType Directory -Path '{remote}' | Out-Null
[IO.File]::WriteAllBytes('{remote}\\source.zip',[Convert]::FromBase64String('{encoded}'))
if ((Get-FileHash '{remote}\\source.zip' -Algorithm SHA256).Hash -ne '{digest}') {{ throw 'Hash mismatch' }}
Expand-Archive '{remote}\\source.zip' '{remote}'
Write-Output 'RUNTIME=deployed:{digest}'
"""
        print(invoke(script, log, a.action, run_id=a.run_id))
    elif a.action == 'launch':
        # Scheduled Task survives Run Command process cleanup; unique task/root, no desktop.
        script = f"""
if (Test-Path '{run}') {{ throw 'Run already exists' }}
if (!(Test-Path '{remote}\\scripts\\run_vm_agent.py')) {{ throw 'Deploy first' }}
$name='iterate-runtime-{a.run_id}'
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {{ throw 'Task already exists' }}
$action=New-ScheduledTaskAction -Execute '{PYTHON}' -Argument 'scripts\\run_vm_agent.py --run-id {a.run_id} --provider scripted --backend {a.backend} --budget {a.budget}' -WorkingDirectory '{remote}'
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Settings $settings -User 'SYSTEM' -RunLevel Highest | Out-Null
Start-ScheduledTask -TaskName $name
Write-Output 'RUNTIME=launched'
"""
        print(invoke(script, log, a.action, run_id=a.run_id))
    elif a.action == 'status':
        script = f"""
if (Test-Path '{run}\\status.json') {{
$s=Get-Content '{run}\\status.json' -Raw
Write-Output ('RUNTIME='+[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($s)))
}} else {{ Write-Output ('RUNTIME='+[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('{{"state":"not_started"}}'))) }}
"""
        print(base64.b64decode(invoke(script, log, a.action, run_id=a.run_id)).decode())
    elif a.action == 'report':
        script = f"""
$b=[IO.File]::ReadAllBytes('{run}\\runtime.json')
$m=New-Object IO.MemoryStream
$g=New-Object IO.Compression.GZipStream($m,[IO.Compression.CompressionMode]::Compress,$true)
$g.Write($b,0,$b.Length); $g.Dispose()
Write-Output ('RUNTIME='+[Convert]::ToBase64String($m.ToArray()))
"""
        import gzip
        report = gzip.decompress(base64.b64decode(invoke(script, log, a.action, run_id=a.run_id)))
        (a.out / (a.run_id + '-runtime.json')).write_bytes(report)
        print(report.decode())
    else:
        # Freeze an archive after terminal status, then download bounded chunks.
        script = f"""
$s=Get-Content '{run}\\status.json' -Raw | ConvertFrom-Json
if ($s.state -notin @('complete','failed')) {{ throw 'Run is active' }}
if (!(Test-Path '{remote}\\export.zip')) {{ Compress-Archive -Path '{run}\\*' -DestinationPath '{remote}\\export.zip' }}
$f=Get-Item '{remote}\\export.zip'
Write-Output ('RUNTIME='+$f.Length+':'+(Get-FileHash $f.FullName -Algorithm SHA256).Hash)
"""
        size, digest = invoke(script, log, a.action, run_id=a.run_id).split(':')
        output = bytearray()
        for offset in range(0, int(size), 2100):
            script = f"""
$f=[IO.File]::OpenRead('{remote}\\export.zip')
try {{ $f.Position={offset}; $b=New-Object byte[] 2100; $n=$f.Read($b,0,2100); Write-Output ('RUNTIME='+[Convert]::ToBase64String($b,0,$n)) }} finally {{ $f.Dispose() }}
"""
            output.extend(base64.b64decode(invoke(script, log, a.action, run_id=a.run_id), validate=True))
        if len(output) != int(size) or hashlib.sha256(output).hexdigest().upper() != digest:
            raise RuntimeError('Export integrity check failed')
        path = a.out / (a.run_id + '.zip')
        path.write_bytes(output)
        print(path)


if __name__ == '__main__':
    main()
