"""50-evaluation single-agent pilot; local API key, Azure-hosted ChemSep."""
import argparse, base64, datetime, gzip, io, json, os, pathlib, re, subprocess, sys, time, urllib.request, zipfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.llm_agent import load_dotenv
from sepdesign.ledger import Ledger
MODEL = 'gpt-6-luna'

def azure(script, out):
    path = out/'command.ps1'
    path.write_text(script)
    start = time.monotonic()
    p = subprocess.run(['az','vm','run-command','invoke','-g',os.environ['AZURE_RESOURCE_GROUP'],'-n','chemsep-01',
        '--command-id','RunPowerShellScript','--scripts','@'+str(path),'-o','json'],capture_output=True,text=True,timeout=600)
    if p.returncode: raise RuntimeError('Azure command failed: '+p.stderr[:1000])
    data = json.loads(p.stdout)
    text = '\n'.join(v.get('message','') for v in data['value'])
    return text, time.monotonic()-start

def main():
    global MODEL
    ap=argparse.ArgumentParser(); ap.add_argument('--model',default=MODEL,choices=['gpt-6-luna','gpt-6.1-sol']); args=ap.parse_args()
    MODEL=args.model
    run_id = MODEL+'-pilot-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT/'runs'/'hc12_dev_000'/'single-agent'/MODEL/run_id/'raw'; out.mkdir(parents=True)
    load_dotenv(str(ROOT/'.env'))
    key = os.environ.get('OPENAI_API_KEY')
    ledger = Ledger(str(out), run_id, provider='openai', model=MODEL)
    if not key: raise RuntimeError('Missing OPENAI_API_KEY')
    config = dict(run_id=run_id,task_id='hc12_dev_000',condition='single-agent',model=MODEL,simulator_budget=50,max_requests=60,max_output_tokens=2500,
        wall_limit_s=3600,reasoning_effort='low',memory='own transcript; no past.dev',automatic_solver_retries=False,
        cost_usd=None,cost_status='unknown: model pricing not verified',transport='Azure Run Command',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    (out/'config.json').write_text(json.dumps(config,indent=2))
    # Upload source only: never credentials, local configuration, or earlier results.
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for p in (ROOT/'sepdesign').rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts: z.write(p,p.relative_to(ROOT))
        for name in ['scripts/pilot_remote.py','tasks/hc12_dev_000.json']: z.write(ROOT/name,name)
    encoded=base64.b64encode(buf.getvalue()).decode()
    remote='C:\\iterate-hackathon\\'+run_id
    prefix="$ErrorActionPreference='Stop'\n$env:CHEMSEP_DIR='C:\\Users\\chemsepadmin\\Desktop'\n"
    deploy=prefix+f"$r='{remote}'\nNew-Item -ItemType Directory -Force -Path $r | Out-Null\n[IO.File]::WriteAllBytes(\"$r\\source.zip\",[Convert]::FromBase64String('{encoded}'))\nExpand-Archive -Force \"$r\\source.zip\" $r\nWrite-Output 'DEPLOYED:{run_id}'"
    print('Run directory:',out,flush=True)
    try:
        text,_=azure(deploy,out)
        if 'DEPLOYED:'+run_id not in text:
            raise RuntimeError('Deployment did not return the expected run-specific marker; no model calls started')
    except Exception as ex:
        (out/'failure.json').write_text(json.dumps({'stage':'deployment','error':str(ex),'solves_used':0,'model_requests':0}))
        raise
    task=json.loads((ROOT/'tasks/hc12_dev_000.json').read_text())
    messages=[{'role':'system','content':(ROOT/'tasks/hc12-economic-design/instruction.md').read_text()},
              {'role':'user','content':'Task data: '+json.dumps(task)+'\nStart with the empty design. Return JSON with reason and edits.'}]
    start=time.monotonic(); used=0; stop='request_limit'; total_in=total_out=0
    try:
        for turn in range(config['max_requests']):
            if time.monotonic()-start>config['wall_limit_s']: stop='wall_limit'; break
            body=dict(model=MODEL,input=messages,max_output_tokens=config['max_output_tokens'],
                      reasoning={'effort':'low'},text={'format':{'type':'json_object'}},store=False)
            (out/f'request-{turn:03}.json').write_text(json.dumps(body))
            req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(body).encode(),
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            t0=time.monotonic()
            try:
                with urllib.request.urlopen(req,timeout=180) as r: response=json.load(r)
            except urllib.error.HTTPError as e:
                # API errors do not contain the Authorization header.
                (out/f'error-{turn:03}.json').write_bytes(e.read())
                ledger.record(None, None, None, ok=False, error=f'HTTP {e.code}')
                raise RuntimeError(f'Model request HTTP {e.code}; details saved') from None
            (out/f'response-{turn:03}.json').write_text(json.dumps(response))
            usage=response.get('usage',{})
            total_in+=usage.get('input_tokens',0); total_out+=usage.get('output_tokens',0)
            event=dict(turn=turn,model=response.get('model'),response_id=response.get('id'),usage=usage,
                wall_s=time.monotonic()-t0,cost_usd=None)
            ledger.record(response.get('id'), usage.get('input_tokens'), usage.get('output_tokens'),
                cached=usage.get('input_tokens_details',{}).get('cached_tokens'),
                reasoning=usage.get('output_tokens_details',{}).get('reasoning_tokens'))
            with (out/'request-timing.jsonl').open('a') as f: f.write(json.dumps(event)+'\n')
            answer=''.join(c.get('text','') for item in response.get('output',[]) for c in item.get('content',[]) if c.get('type')=='output_text')
            messages.append({'role':'assistant','content':answer})
            try:
                proposal=json.loads(answer); edits=proposal['edits']
                if not isinstance(edits,list) or not all(isinstance(e,dict) for e in edits): raise ValueError('edits must be a list of objects')
            except (ValueError,KeyError) as ex:
                messages.append({'role':'user','content':'Invalid JSON proposal: '+str(ex)+'. Return reason and edits.'}); continue
            payload=base64.b64encode(json.dumps(edits).encode()).decode()
            script=prefix+f"& 'C:\\chemsep-benchmark\\venv\\Scripts\\python.exe' '{remote}\\scripts\\pilot_remote.py' '{run_id}' '{payload}'\nif ($LASTEXITCODE -ne 0) {{ throw 'Pilot evaluation failed' }}"
            text,transport=azure(script,out)
            match=re.search(r'PILOT=([A-Za-z0-9+/=]+)',text)
            if not match: raise RuntimeError('No simulator feedback: '+text[-1500:])
            feedback=json.loads(gzip.decompress(base64.b64decode(match[1])))
            used=feedback['solves_used']
            event=dict(turn=turn,proposal=proposal,feedback=feedback,transport_wall_s=transport,elapsed_s=time.monotonic()-start)
            with (out/'trajectory.jsonl').open('a') as f: f.write(json.dumps(event)+'\n')
            print(json.dumps(dict(turn=turn,solves=used,best=feedback['best_reward'],valid=feedback['valid'])),flush=True)
            messages.append({'role':'user','content':json.dumps(feedback)+'\nContinue improving. Return reason and edits as JSON.'})
            if used>=50: stop='simulator_budget'; break
        summary=dict(stop_reason=stop,solves_used=used,input_tokens=total_in,output_tokens=total_out,cost_usd=None,
            wall_s=time.monotonic()-start,remote_directory=remote,best_reward=feedback['best_reward'] if used else 0)
        ledger.summary(summary)
        print(json.dumps(summary),flush=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/organize_run.py'),str(out)],check=True)
    except Exception as ex:
        (out/'failure.json').write_text(json.dumps({'error':str(ex),'solves_used':used,'input_tokens':total_in,'output_tokens':total_out}))
        raise

if __name__=='__main__': main()
