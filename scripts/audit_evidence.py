"""Offline, exhaustive structural audit of the Git-tracked evidence at a revision.

Reads Git blobs (not ignored live runs), never executes model/simulator calls. Every
tracked file receives a hash and a coverage classification; every JSON value and
JSONL line is visited. Scientific meaning of free text is outside automated checks.
"""
from __future__ import annotations
import argparse
import base64
import gzip
import posixpath
import collections
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {'.md', '.txt', '.log', '.json', '.jsonl', '.csv', '.html', '.py', '.js', '.toml', '.ini', '.sh', '.ps1', '.tmpl', '.svg'}
# Specific credential shapes, not arbitrary strings or personal identifiers.
SECRET_PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'github_token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'openai_key': re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}\b'),
}
COUNTERS = {'input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_tokens', 'requests', 'cumulative_requests', 'solves_used', 'team_solves', 'backend_calls', 'team_distinct_queries'}
NUMBERS = COUNTERS | {'reward', 'best_reward', 'best_valid_reward', 'team_best', 'usd', 'cumulative_usd', 'usd_cum', 'usd_estimated_total', 'usd_logged', 'usd_real', 'usd_cached_price_estimate', 'elapsed_s', 'wall_s'}
RECORD_ROLES = {'usage', 'turns', 'events', 'board', 'trajectory', 'simulator', 'timings', 'transport', 'response-diagnostics', 'designs', 'fingerprints', 'trace', 'curve', 'team_curve'}
REQUIRED = {'usage': {'run_id', 'agent_id', 'model', 'provider', 'request_id', 'ok', 'input_tokens', 'output_tokens', 'usd', 'cumulative_usd', 'cumulative_requests'}, 'events': {'kind'}, 'turns': {'turn'}, 'board': {'agent', 'reward', 'valid', 'design'}, 'trajectory': {'kind', 'run_id'}}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def close(a, b):
    return number(a) and number(b) and math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-7)


def audit(revision='HEAD'):
    commit = git('rev-parse', revision).decode().strip()
    entries = [x.split(b'\t', 1) for x in git('ls-tree', '-r', '-z', commit).split(b'\0') if x]
    findings, files, documents, streams = [], [], {}, []
    checks = collections.Counter()
    schemas = collections.Counter()
    visited = collections.Counter()

    def finding(code, path, location, detail, severity='warning'):
        findings.append(dict(code=code, severity=severity, path=path, location=location, detail=detail))

    def visit(value, path, location='$'):
        visited['json_values'] += 1
        if isinstance(value, float) and not math.isfinite(value):
            finding('non_finite_number', path, location, 'Non-finite JSON number.', 'error')
        if isinstance(value, dict):
            visited['json_objects'] += 1
            for key, item in value.items():
                # Historical summaries can contain map-valued counts; only scalar metric fields apply.
                if key in NUMBERS and item is not None and not isinstance(item, (dict, list)) and '/checks' not in location:
                    checks['numeric_fields'] += 1
                    if not number(item):
                        finding('metric_type', path, location+'/'+key, 'Expected a finite numeric metric; saved type is '+type(item).__name__)
                    elif key in COUNTERS and (item < 0 or int(item) != item):
                        finding('counter_value', path, location+'/'+key, 'Expected a nonnegative integer.', 'error')
                if key in ('error', 'errors') and item:
                    visited['nonempty_error_fields'] += 1
                visit(item, path, location+'/'+str(key))
        elif isinstance(value,str) and location.endswith('/message'):
            for match in re.finditer(r'REPORT_GZIP_BASE64=([A-Za-z0-9+/=]+)',value):
                loc=location+'/decoded_report'
                try:
                    decoded=gzip.decompress(base64.b64decode(match.group(1),validate=True))
                    payload=json.loads(decoded)
                except (ValueError,OSError,EOFError) as exc:
                    finding('transport_decode_error',path,loc,type(exc).__name__,'error')
                    continue
                visited['decoded_transport_reports'] += 1
                visit(payload,path,loc)
                embedded(payload,path,loc)
                for name,pattern in SECRET_PATTERNS.items():
                    if pattern.search(decoded.decode('utf-8')): finding('sensitive_pattern_'+name,path,loc,'Potential credential pattern in decoded payload; value withheld.','error')
        elif isinstance(value, list):
            visited['json_arrays'] += 1
            for i, item in enumerate(value):
                visit(item, path, location+'/'+str(i))

    def stream(role, rows, path, location, raw=False, source_lines=None):
        if not isinstance(rows, list):
            return
        schema_count = collections.Counter()
        def loc(i): return 'line:'+str(source_lines[i]) if source_lines else f'{location}/{i}'
        for i, row in enumerate(rows):
            checks['records'] += 1
            if isinstance(row, dict):
                sig=','.join(sorted(row))
                schema_count[sig] += 1
                schemas[(role, sig)] += 1
                required = REQUIRED.get(role, set())
                if role == 'usage' and not raw and 'run_id' not in row:
                    required = {'elapsed_s', 'input_tokens', 'output_tokens', 'usd'}
                for field in required:
                    if field not in row:
                        finding('missing_record_field', path, loc(i)+'/'+field, f'{role} record is missing required field.', 'error')
            elif role not in ('curve', 'team_curve'):
                finding('record_type', path, loc(i), 'Record is not an object.', 'error')
        detail = dict(path=path, location=location, role=role, records=len(rows), raw=raw,
                      schemas=[dict(fields=k.split(','), records=v) for k,v in sorted(schema_count.items())])
        streams.append(detail)
        if role == 'usage' and rows and all(isinstance(r, dict) and 'run_id' in r for r in rows):
            for field in ('run_id', 'agent_id', 'model', 'provider'):
                vals = {str(r.get(field)) for r in rows}
                checks['usage_identity'] += len(rows)
                if len(vals)>1:
                    finding('mixed_usage_identity', path, location+'/'+field, f'{len(vals)} identities in one agent usage stream.')
            total = 0.0
            ids = set()
            for i, row in enumerate(rows):
                request_id=row.get('request_id')
                if request_id is not None and not isinstance(request_id,str):
                    finding('request_id_type',path,loc(i),'Request ID must be a string or null.','error')
                    request_id=None
                if request_id is not None and request_id in ids:
                    finding('duplicate_request_id', path, loc(i), 'Repeated request ID in one usage stream.' + (' Scripted qualification fixture, not provider billing.' if row.get('request_id')=='scripted' else ''))
                ids.add(request_id)
                if number(row.get('usd')): total += row['usd']
                checks['usage_cumulative'] += 1
                if number(row.get('cumulative_usd')) and not close(total, row['cumulative_usd']):
                    finding('usage_cost_cumulative', path, loc(i), 'Cumulative logged USD differs from sum of available per-request USD.')
                if row.get('cumulative_requests') != i+1:
                    finding('usage_request_sequence', path, loc(i), 'Cumulative request count differs from available stream position.')
        if role == 'usage' and rows and all(isinstance(r,dict) for r in rows):
            missing=sum(r.get('request_id') is None for r in rows)
            unknown=sum(r.get('usd') is None for r in rows)
            if missing: finding('request_id_unavailable',path,location,f'{missing} records lack provider request IDs; uniqueness cannot be verified.','coverage')
            if unknown: finding('unknown_request_cost',path,location,f'{unknown} records lack per-request cost; recorded totals are incomplete estimates.','coverage')
        if role in ('turns', 'events', 'curve', 'team_curve'):
            prev = {}
            for i,row in enumerate(rows):
                vals = {k:row[k] for k in ('turn','team_solves','solves_used','team_best') if k in row} if isinstance(row,dict) else ({'queries':row[0], 'best':row[1]} if isinstance(row,list) and len(row)>=2 else {})
                for field,val in vals.items():
                    if number(val):
                        checks['monotonic_fields'] += 1
                        if field in prev and val < prev[field]-1e-8:
                            finding('nonmonotonic_'+field, path, loc(i), f'{field} decreases in recorded order.')
                        prev[field]=val

    def embedded(value, path, location='$'):
        if isinstance(value,dict):
            for key,item in value.items():
                loc=location+'/'+key
                if key in RECORD_ROLES and isinstance(item,list):
                    stream(key,item,path,loc)
                elif key in ('usage','turns') and isinstance(item,dict):
                    for agent,rows in item.items():
                        if isinstance(rows,list): stream(key,rows,path,loc+'/'+agent)
                embedded(item,path,loc)
        elif isinstance(value,list):
            for i,item in enumerate(value): embedded(item,path,location+'/'+str(i))

    # Read all immutable blobs with one Git process.
    blobs = subprocess.run(['git', 'cat-file', '--batch'], cwd=ROOT, input=b''.join(meta.split()[2]+b'\n' for meta,_ in entries), capture_output=True, check=True).stdout
    cursor=0
    # Audit the selected immutable snapshot, including sources outside results/.
    for meta, encoded in entries:
        end=blobs.index(b'\n',cursor); size=int(blobs[cursor:end].split()[-1]); cursor=end+1
        data=blobs[cursor:cursor+size]; cursor+=size+1
        path = encoded.decode()
        if path.startswith('results/evidence-audit/'):
            continue  # Generated audit outputs would otherwise audit themselves.
        suffix = PurePosixPath(path).suffix
        record = dict(path=path, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), checks=['sha256'])
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            record.update(classification='opaque_binary', lines=None)
            files.append(record)
            continue
        record.update(classification='text_scanned', lines=len(text.splitlines()))
        record['checks'] += ['utf8', 'every_line_sensitive_patterns']
        for lineno,line in enumerate(text.splitlines(),1):
            for name,pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    finding('sensitive_pattern_'+name,path,str(lineno),'Potential credential pattern; value intentionally withheld.', 'error')
        if suffix in ('.json', '.jsonl'):
            record['checks'] += ['parse_every_record', 'recursive_values', 'metric_types', 'schema_profile']
            record['classification']='structured_evidence' if path.startswith('results/') else 'structured_other'
            rows=[]
            row_locations=[]
            # Duplicate keys must not silently disappear under json.loads.
            def pairs(items):
                obj={}
                for key,val in items:
                    if key in obj: finding('duplicate_json_key',path,'parse',f'Duplicate key: {key}', 'error')
                    obj[key]=val
                return obj
            source = list(enumerate(text.splitlines(),1)) if suffix=='.jsonl' else [(1,text)]
            for lineno,line in source:
                if not line.strip():
                    if suffix=='.jsonl': record['blank_lines']=record.get('blank_lines',0)+1
                    continue
                try: value=json.loads(line,object_pairs_hook=pairs)
                except ValueError as exc:
                    finding('invalid_json',path,str(lineno),str(exc),'error')
                    continue
                rows.append(value)
                row_locations.append(lineno)
                location='line:'+str(lineno) if suffix=='.jsonl' else '$'
                visit(value,path,location)
                embedded(value,path,location)
            record['parsed_records']=len(rows)
            if suffix=='.jsonl':
                documents[path]=rows
                stream(PurePosixPath(path).stem,rows,path,'line',True,row_locations)
                record['checks'].append('role_specific_records')
                record['ends_in_newline']=data.endswith(b'\n')
            elif rows: documents[path]=rows[0]
        elif suffix in ('.csv','.tsv'):
            parsed=list(csv.reader(io.StringIO(text),delimiter='\t' if suffix=='.tsv' else ','))
            record['csv_rows']=max(len(parsed)-1,0)
            record['checks'].append('csv_width')
            if parsed:
                for i,row in enumerate(parsed[1:],2):
                    if len(row)!=len(parsed[0]): finding('csv_width',path,str(i),'CSV row width differs from header.','error')
                    for key,item in zip(parsed[0],row):
                        if key in NUMBERS and item.strip() not in ('','None','null','unknown','nan'):
                            checks['csv_numeric_fields'] += 1
                            try: val=float(item)
                            except ValueError: finding('csv_metric_type',path,f'{i}/{key}','Numeric CSV field cannot be parsed.','error');continue
                            if not math.isfinite(val): finding('csv_nonfinite',path,f'{i}/{key}','Nonfinite CSV metric.','error')
        files.append(record)

    def safe_sum(rows, field):
        values=[r.get(field) for r in rows]
        return sum(values) if all(number(v) for v in values) else None

    def compare(path, field, actual, expected, detail):
        if not number(actual) or not number(expected):
            checks['aggregate_comparisons_unavailable'] += 1
            return
        checks['aggregate_comparisons'] += 1
        if not close(actual,expected):
            finding('aggregate_mismatch',path,field,f'{detail}: saved={actual}, recomputed={expected}.')

    # Each raw usage file reconciles against its adjacent agent/solo summary.
    for path,rows in documents.items():
        if not path.endswith('/usage.jsonl') or not isinstance(rows,list):continue
        if not all(isinstance(r,dict) for r in rows):continue
        summary_path=str(PurePosixPath(path).with_name('summary.json'))
        summary=documents.get(summary_path)
        if not isinstance(summary,dict):
            finding('missing_adjacent_usage_summary',path,'$', 'No tracked adjacent summary; per-request accounting checked, endpoint reconciliation unavailable.','coverage')
            continue
        for field in ('run_id','agent_id','model','provider'):
            for i,row in enumerate(rows):
                if summary.get(field) is not None and row.get(field)!=summary[field]:
                    finding('summary_identity_mismatch',path,f'line/{i+1}/{field}','Usage identity differs from adjacent summary.','error')
        for field in ('input_tokens','output_tokens'):
            compare(summary_path,field,summary.get(field),safe_sum(rows,field),'Available usage sum')
        compare(summary_path,'requests',summary.get('requests'),len(rows),'Available usage count')
        compare(summary_path,'usd_estimated_total',summary.get('usd_estimated_total'),safe_sum(rows,'usd'),'Available logged USD sum')

    # Endpoint reward and high-water queries, without treating sparse snapshots as full trajectories.
    for path,summary in documents.items():
        if not path.endswith('/summary.json') or not isinstance(summary,dict):continue
        parent=PurePosixPath(path).parent
        for name,field in [('turns.jsonl','best_valid_reward'),('board.jsonl','team_best')]:
            rows=documents.get(str(parent/name))
            if not isinstance(rows,list):continue
            best=max([0.0]+[r['reward'] for r in rows if isinstance(r,dict) and r.get('valid') and number(r.get('reward'))])
            compare(path,field,summary.get(field),best,'Best available valid record (zero floor)')
        limit=summary.get('team_solves',summary.get('solves_used'))
        checkpoints=summary.get('best_at',{})
        if not isinstance(checkpoints,dict):
            finding('checkpoint_schema',path,'best_at','Checkpoint container must be an object.','error'); checkpoints={}
        for checkpoint,value in checkpoints.items():
            try: point=float(checkpoint)
            except (ValueError,TypeError):
                finding('checkpoint_schema',path,'best_at','Checkpoint key must be numeric.','error');continue
            if number(limit) and point>limit and value is not None:
                finding('unobserved_checkpoint',path,'best_at/'+checkpoint,'Checkpoint exceeds consumed queries; carried-forward endpoint is not an observed checkpoint.','historical')
        agents=summary.get('agents')
        if isinstance(agents,dict):
            for field,child in [('team_solves','solves_used'),('requests','requests'),('input_tokens','input_tokens'),('output_tokens','output_tokens')]:
                if agents and all(isinstance(a,dict) and number(a.get(child)) for a in agents.values()):
                    compare(path,field,summary.get(field),sum(a[child] for a in agents.values()),'Sum of agent endpoints')
        config=documents.get(str(parent/'config.json'),{})
        if not isinstance(config,dict):
            finding('config_schema',path,'config','Adjacent config must be an object.','error'); config={}
        for field in ('run_id','task','model'):
            if summary.get(field) is not None and config.get(field) is not None and summary[field]!=config[field]:
                finding('config_summary_identity',path,field,'Configuration and summary disagree.','error')
        budgets=config.get('budgets')
        if isinstance(budgets,dict) and all(number(v) for v in budgets.values()) and number(limit) and limit>sum(budgets.values()):
            finding('budget_exceeded',path,'team_solves','Consumed solves exceed configured initial team allocation.')

    # Every tracked manifest hash that resolves locally is verified; remote/missing refs are explicit.
    hashes={f['path']:f['sha256'] for f in files}
    for path,manifest in documents.items():
        if not path.endswith('/manifest.json') or not isinstance(manifest,dict):continue
        mapping=manifest.get('files',manifest.get('sha256',{}))
        if isinstance(mapping,list) and all(isinstance(x,dict) and 'path' in x and 'sha256' in x for x in mapping):
            mapping={x['path']:x['sha256'] for x in mapping}
        if not isinstance(mapping,dict):
            finding('manifest_hash_schema_unhandled',path,'$', 'Manifest hash mapping is not a dictionary.','coverage');continue
        for relative,expected in mapping.items():
            target=posixpath.normpath(str(PurePosixPath(path).parent/relative))
            if target not in hashes:
                finding('manifest_source_unavailable',path,relative,'Referenced hash source is not tracked at this revision.','coverage')
            elif not isinstance(expected,str):
                finding('manifest_hash_schema_unhandled',path,relative,'Hash entry is not a plain string.','coverage')
            elif isinstance(expected,str):
                checks['source_hashes'] += 1
                if hashes[target]!=expected: finding('manifest_hash_mismatch',path,relative,'Tracked source hash differs from manifest.','error')

    # Extracted V3 reports preserve hashes of raw files that may not be published.
    def reconcile_exports(value,path,location='$'):
        if isinstance(value,dict):
            for key in ('trajectory_sha256','simulator_sha256','usage_sha256'):
                if value.get(key) and value[key] not in hashes.values():
                    finding('raw_hash_without_tracked_source',path,location+'/'+key,'Raw source hash retained, but no tracked blob has that hash; full raw-stream recomputation unavailable.','coverage')
            if 'reconciliation' in value and 'summary' in value and 'agents' in value:
                summary=value['summary']; agents=value['agents']; recs=value['reconciliation']
                if not isinstance(summary,dict) or not isinstance(agents,dict) or not all(isinstance(a,dict) for a in agents.values()) or not isinstance(recs,dict):
                    finding('export_schema',path,location,'Extracted summary, agents or reconciliation has an invalid container type.','error')
                else:
                    compare(path,location+'/team_distinct_queries',summary.get('team_distinct_queries'),safe_sum(list(agents.values()),'queries'),'Extracted per-agent query sum')
                    rewards=[a['best'] for a in agents.values() if number(a.get('best'))]
                    curve=value.get('curve',[])
                    if isinstance(curve,list) and curve and isinstance(curve[-1],dict) and rewards:
                        compare(path,location+'/curve_endpoint',curve[-1].get('reward'),max(rewards),'Extracted best-agent endpoint')
                    summaries=summary.get('agents',{})
                    for agent,rec in recs.items():
                        endpoint=summaries.get(agent,{}) if isinstance(summaries,dict) else {}
                        usage=endpoint.get('usage',{}) if isinstance(endpoint,dict) else {}
                        if not isinstance(rec,dict) or not isinstance(rec.get('summed',{}),dict) or not isinstance(usage,dict):
                            finding('export_schema',path,location+'/'+agent,'Invalid usage reconciliation container.','error');continue
                        for field,total in rec.get('summed',{}).items():
                            compare(path,location+'/'+agent+'/'+field,usage.get(field),total,'Saved usage reconciliation versus summary (raw absence reported separately)')
            for key,item in value.items():reconcile_exports(item,path,location+'/'+key)
        elif isinstance(value,list):
            for i,item in enumerate(value):reconcile_exports(item,path,location+'/'+str(i))
    for path,value in documents.items():reconcile_exports(value,path)

    # Reconcile the presentation inventory against canonical team report configs.
    inventory=documents.get('results/results-so-far/runs.json',[])
    indexed={r['run_id']:r for r in inventory if isinstance(r,dict) and 'run_id' in r}
    canonical=[]
    for path,report in documents.items():
        if not isinstance(report,dict) or report.get('schema')!='team-report-v1':continue
        config=report.get('config'); summary=report.get('summary')
        if not isinstance(config,dict) or not isinstance(summary,dict) or not isinstance(config.get('run_id'),str):
            finding('canonical_report_schema',path,'$','Canonical config/summary/run_id is missing or invalid.','error');continue
        rid=config['run_id']; budgets=config.get('budgets',{})
        if not isinstance(budgets,dict) or not all(number(v) for v in budgets.values()):
            finding('canonical_report_schema',path,'config/budgets','Budgets must map agent IDs to finite numeric values.','error');continue
        board=report.get('board',[]);turns=report.get('turns',{})
        if not isinstance(board,list) or not isinstance(turns,(dict,list)) or (isinstance(turns,dict) and not all(isinstance(v,list) for v in turns.values())):
            finding('canonical_report_schema',path,'board/turns','Invalid board or turns container.','error');continue
        entry=indexed.get(rid)
        canonical.append(dict(path=path,run_id=rid,agents=len(budgets),status=summary.get('status'),board_records=len(report.get('board',[])),turn_records=sum(len(x) for x in report.get('turns',{}).values()) if isinstance(report.get('turns'),dict) else len(report.get('turns',[]))))
        if not entry:
            finding('inventory_missing_run',path,'config/run_id','Canonical report run is missing from inventory.','error');continue
        for field,expected in [('agents',len(budgets)),('budget_total',sum(budgets.values())),('queries',summary.get('team_solves')),('reward',summary.get('team_best')),('model_usd',summary.get('usd_cached_price_estimate',summary.get('usd')))]:
            actual=entry.get(field)
            if expected is not None and actual is None:
                finding('inventory_missing_metric',path,field,'Canonical metric exists but inventory value is missing.')
            else: compare(path,'inventory/'+field,actual,expected,'Inventory versus canonical team report')
        for field in ('model','task'):
            if entry.get(field)!=config.get(field): finding('inventory_identity',path,field,'Inventory identity differs from canonical report.','error')
        if not board and not (any(turns.values()) if isinstance(turns,dict) else turns):
            finding('missing_plant_records',path,'board/turns','Events and usage exist, but no plant submissions are available to reconstruct evolution.','coverage')

    severity=collections.Counter(f['severity'] for f in findings)
    return dict(schema='evidence-audit-v1',source_commit=commit,
        scope='Every tracked blob at source_commit, excluding generated results/evidence-audit/. No ignored/live files or external services.',
        limitations=['Automated structural and arithmetic checks are not manual semantic review of every note, prompt or scientific conclusion.', 'No ChemSep reruns, independent physical validation, remote retrieval, full Git-history credential audit or billing-provider reconciliation.', 'Embedded HTML/JavaScript is scanned as text, not executed; standalone JSON/JSONL is authoritative for record checks.', 'Repeated exports are counted as file occurrences, not independent experiments. Missing raw records remain unverified.'],
        totals=dict(files=len(files),text_files=sum(f['lines'] is not None for f in files),text_lines=sum(f['lines'] or 0 for f in files),json_files=sum(f['path'].endswith('.json') for f in files),jsonl_files=sum(f['path'].endswith('.jsonl') for f in files),jsonl_records=sum(f.get('parsed_records',0) for f in files if f['path'].endswith('.jsonl')),binary_files=sum(f['lines'] is None for f in files),**visited),
        checks=dict(checks),finding_counts=dict(severity),findings=findings,files=files,streams=streams,canonical_team_reports=canonical)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',default='HEAD')
    parser.add_argument('--output',type=Path,default=ROOT/'results/evidence-audit/manifest.json')
    args=parser.parse_args()
    result=audit(args.revision)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    # One entry per line keeps the complete coverage ledger diffable without
    # expanding every repeated schema field into thousands of lines.
    parts=[]
    for key,value in result.items():
        encoded='[\n'+',\n'.join('    '+json.dumps(item,sort_keys=True) for item in value)+'\n  ]' if isinstance(value,list) else json.dumps(value,sort_keys=True)
        parts.append('  '+json.dumps(key)+': '+encoded)
    args.output.write_text('{\n'+',\n'.join(parts)+'\n}\n')
    print(json.dumps({k:result[k] for k in ('source_commit','totals','checks','finding_counts')},indent=2))
    return 1 if result['finding_counts'].get('error') else 0


if __name__=='__main__':
    raise SystemExit(main())
