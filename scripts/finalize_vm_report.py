"""Download saved VM evidence, verify it, and generate HTML locally under results/."""
import os
import base64, fcntl, gzip, hashlib, json, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sepdesign.report_archive import publish, publish_swarm, segment, index as index_reports


def remote(code):
    encoded=base64.b64encode(code.encode()).decode()
    ps="& 'C:\\chemsep-benchmark\\venv\\Scripts\\python.exe' -c \"import base64;exec(base64.b64decode('"+encoded+"'))\""
    for attempt in range(20):
        p=subprocess.run(['az','vm','run-command','invoke','--resource-group',os.environ['AZURE_RESOURCE_GROUP'],'--name','chemsep-01','--command-id','RunPowerShellScript','--scripts',ps,'-o','json'],capture_output=True,text=True)
        if p.returncode and '(Conflict)' in p.stderr:
            time.sleep(15)
            continue
        if p.returncode:raise RuntimeError('Azure report operation failed')
        for value in json.loads(p.stdout).get('value',[]):
            for line in value.get('message','').splitlines():
                if line.startswith('REPORT='):return line[7:]
        raise RuntimeError('Azure report response missing; report export can be retried')
    raise RuntimeError('Azure command slot remained busy')


def finalize(controller):
    controller=Path(controller)
    config=json.loads(controller.read_text())
    for key in ('task','model','run_id'):
        if key in config:segment(config[key])
    local=ROOT/'runs'/config.get('task','hc12_dev_000')/'single-agent'/config['model']/config['run_id']
    local.mkdir(parents=True,exist_ok=True)
    with (local/'report.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (local/'report-data.json').exists():
            return publish(json.loads((local/'report-data.json').read_text()), ROOT)
        root=config['remote'];run=root+'\\runs\\runtime\\'+config['run_id']
        metadata=json.loads(remote(f'''import sys,json,gzip,base64,hashlib
from pathlib import Path
root=Path({root!r});run=Path({run!r})
status=json.loads((run/'status.json').read_text())
assert status['state'] in ('complete','failed'), 'Run has not finished'
sys.path.insert(0,str(root))
from sepdesign.report import collect
data=collect(run)
payload=gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0)
(run/'report-data.json.gz').write_bytes(payload)
print('REPORT='+json.dumps(dict(size=len(payload),sha256=hashlib.sha256(payload).hexdigest())))
'''))
        data = download(local, metadata, run)
        return publish(data, ROOT)


def download(local, metadata, run, filename="report-data.json.gz"):
    parts=local/'download';parts.mkdir(exist_ok=True)
    old=parts/'metadata.json'
    if old.exists() and json.loads(old.read_text())!=metadata:
        for p in parts.glob('*.part'):p.unlink()
    old.write_text(json.dumps(metadata))
    chunks=[]
    for offset in range(0,metadata['size'],2400):
        part=parts/f'{offset:08d}.part'
        if not part.exists():
            value=remote(f"from pathlib import Path\nimport base64\np=Path({run!r})/{filename!r}\nprint('REPORT='+base64.b64encode(p.read_bytes()[{offset}:{offset+2400}]).decode())")
            part.write_bytes(base64.b64decode(value,validate=True))
        chunks.append(part.read_bytes())
        print(f"Report data: {min(offset+2400,metadata['size'])}/{metadata['size']} bytes",flush=True)
    payload=b''.join(chunks)
    if hashlib.sha256(payload).hexdigest()!=metadata['sha256']:raise RuntimeError('Report export checksum mismatch')
    data=json.loads(gzip.decompress(payload))
    (local/'report-data.json').write_text(json.dumps(data))
    return data


def finalize_swarm(controller):
    controller=Path(controller)
    config=json.loads(controller.read_text())
    for key in ('task','model','run_id'):
        if key in config:segment(config[key])
    local=ROOT/'runs/report-downloads'/(config['run_id']+'-swarm')
    local.mkdir(parents=True,exist_ok=True)
    with (local/'report.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (local/'report-data.json').exists():
            return publish_swarm(json.loads((local/'report-data.json').read_text()),ROOT)
        root=config['remote']
        metadata=json.loads(remote(f'''import sys,json,gzip,hashlib
from pathlib import Path
root=Path({root!r})
sys.path.insert(0,str(root))
from sepdesign.report import collect
pair=json.loads((root/'runs'/{config['run_id']!r}/'status.json').read_text())
assert pair['state'] in ('complete','failed'), 'Pair has not finished'
candidates=list((root/'runs'/{config['task']!r}).glob('shared-memory-*/*/swarm-*'))
assert len(candidates)==1, 'Expected one swarm in isolated deployment'
run=candidates[0]
summary=json.loads((run/'metrics/summary.json').read_text())
configuration=json.loads((run/'config.json').read_text())
data=dict(summary=summary,config=configuration,agents={{a:collect(run/'raw'/a) for a in summary['agents']}})
payload=gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0)
(root/'swarm-report-data.json.gz').write_bytes(payload)
print('REPORT='+json.dumps(dict(size=len(payload),sha256=hashlib.sha256(payload).hexdigest())))
'''))
        data=download(local,metadata,root,'swarm-report-data.json.gz')
        return publish_swarm(data,ROOT)

def index_runs():
    return index_reports(ROOT)

if __name__=='__main__' :print(finalize(Path(sys.argv[1])))
