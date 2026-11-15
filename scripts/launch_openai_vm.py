"""Queue an approved OpenAI VM run after a legacy pilot terminates.

The caller must already have permission to reuse and provision the source key.
Only encrypted key material crosses Azure Run Command. No plaintext credentials
are included in its arguments or logs. Requires local cryptography.
"""
import argparse
import base64
import json
import sys
import time
from pathlib import Path, PureWindowsPath
from xml.etree import ElementTree
from azure_runtime import invoke, bundle, PYTHON
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pilot-dir', type=Path, required=True)
    ap.add_argument('--source-env', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--budget', type=int, default=5)
    ap.add_argument('--swarm', action='store_true')
    a = ap.parse_args()
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]+', a.run_id): ap.error('Invalid run id')
    a.out.mkdir(parents=True, exist_ok=True)
    log = a.out / (a.run_id + '-transport.jsonl')
    state = a.out / (a.run_id + '-controller.json')
    def status(stage):
        state.write_text(json.dumps({'stage': stage, 'run_id': a.run_id, 'updated': time.time()}))
        print(stage, flush=True)
    def call(script, stage):
        status(stage)
        return invoke(script, log, stage, run_id=a.run_id)
    status('waiting_for_legacy_pilot')
    while not any((a.pilot_dir / n).is_file() for n in ('summary.json', 'failure.json')):
        time.sleep(10)
    # Read only the requested key; never echo source contents or exceptions.
    key = None
    values = {}
    for line in a.source_env.read_text().splitlines():
        name, sep, value = line.strip().partition('=')
        if sep and name in ('OPENAI_API_KEY', 'PAST_API_KEY'): values[name] = value.strip().strip('"\'')
    names = ['OPENAI_API_KEY', 'PAST_API_KEY'] if a.swarm else ['OPENAI_API_KEY']
    if any(not values.get(n) for n in names): raise ValueError('Missing requested credential')
    key = '\n'.join(n+'='+values[n] for n in names)
    if not key or '\r' in key: raise ValueError('Missing or invalid key')
    secret_dir = str(PureWindowsPath('C:/iterate-hackathon/secrets') / a.run_id)
    private = secret_dir + '\\' + a.run_id + '-transfer.xml'
    envfile = secret_dir + r'\openai.env'
    public_xml = call(f"""
if (Test-Path '{secret_dir}') {{ throw 'Credential destination already exists' }}
New-Item -ItemType Directory -Force '{secret_dir}' | Out-Null
icacls '{secret_dir}' /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) {{ throw 'ACL setup failed' }}
$r=New-Object Security.Cryptography.RSACryptoServiceProvider(4096)
$r.PersistKeyInCsp=$false
[IO.File]::WriteAllText('{private}',$r.ToXmlString($true))
Write-Output ('RUNTIME='+$r.ToXmlString($false))
$r.Dispose()
""", 'prepare_credential_destination')
    xml = ElementTree.fromstring(public_xml)
    number = lambda name: int.from_bytes(base64.b64decode(xml.findtext(name)), 'big')
    pub = rsa.RSAPublicNumbers(number('Exponent'), number('Modulus')).public_key()
    ciphertext = base64.b64encode(pub.encrypt(key.encode(), padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None))).decode()
    del key
    call(f"""
$r=New-Object Security.Cryptography.RSACryptoServiceProvider
$r.PersistKeyInCsp=$false
try {{
$r.FromXmlString([IO.File]::ReadAllText('{private}'))
$b=$r.Decrypt([Convert]::FromBase64String('{ciphertext}'),$true)
[IO.File]::WriteAllText('{envfile}', [Text.Encoding]::UTF8.GetString($b), (New-Object Text.UTF8Encoding($false)))
icacls '{envfile}' /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
if ($LASTEXITCODE -ne 0) {{ throw 'Credential ACL failed' }}
Write-Output 'RUNTIME=credential_ready'
}} finally {{ $r.Dispose(); Remove-Item '{private}' -ErrorAction SilentlyContinue }}
""", 'provision_credential')
    remote = r'C:\iterate-hackathon\azure-runtime-' + a.run_id
    content = bundle()
    encoded = base64.b64encode(content).decode()
    digest = hashlib.sha256(content).hexdigest()
    call(f"""
if (Test-Path '{remote}') {{ throw 'Deployment already exists' }}
New-Item -ItemType Directory '{remote}' | Out-Null
[IO.File]::WriteAllBytes('{remote}\\source.zip',[Convert]::FromBase64String('{encoded}'))
if ((Get-FileHash '{remote}\\source.zip').Hash -ne '{digest}') {{ throw 'Hash mismatch' }}
Expand-Archive '{remote}\\source.zip' '{remote}'
$ErrorActionPreference='Continue'
& '{PYTHON}' -m pip install openai numpy truststore > '{remote}\\dependencies.log' 2>&1
$code=$LASTEXITCODE
$ErrorActionPreference='Stop'
if ($code -ne 0) {{ throw 'Dependency install failed' }}
Write-Output 'RUNTIME=deployed'
""", 'deploy')
    # The wrapper reads the restricted file into the child process only.
    command = (f'scripts/run_swarm.py --agents 3 --rounds 5 --memory past --backend chemsep --provider openai --model gpt-6.1-sol --env-file {envfile}' if a.swarm else f'scripts/run_vm_agent.py --run-id {a.run_id} --provider openai --model gpt-6.1-sol --budget {a.budget} --max-turns 80')
    wrapper = f"""$ErrorActionPreference='Continue'
Set-Location '{remote}'
$env:CHEMSEP_DIR='C:/Users/chemsepadmin/Desktop'
foreach ($line in [IO.File]::ReadAllLines('{envfile}')) {{ $parts=$line.Split('=',2); [Environment]::SetEnvironmentVariable($parts[0],$parts[1],'Process') }}
& '{PYTHON}' {command} > '{remote}\\runner.log' 2>&1
exit $LASTEXITCODE
"""
    wrapper64 = base64.b64encode(wrapper.encode()).decode()
    call(f"""
[IO.File]::WriteAllBytes('{remote}\\launch.ps1',[Convert]::FromBase64String('{wrapper64}'))
$name='iterate-runtime-{a.run_id}'
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {{ throw 'Task already exists' }}
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File "{remote}\\launch.ps1"' -WorkingDirectory '{remote}'
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Settings $settings -User 'SYSTEM' -RunLevel Highest | Out-Null
Start-ScheduledTask -TaskName $name
Write-Output 'RUNTIME=launched'
""", 'launch')
    status('launched')

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('Controller failed: ' + type(exc).__name__ + ' (details withheld)', flush=True)
        sys.exit(1)
