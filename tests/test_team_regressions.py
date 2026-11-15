import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from sepdesign import teams
from sepdesign.service import make_service
from sepdesign.taskset import find_task
from sepdesign.team_report import payload, publish_team


def nested(module, name, scope):
    tree = ast.parse(Path(module.__file__).read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), module.__file__, 'exec'), scope)
    return scope[name]


def test_migrant_survives_full_local_history():
    board = teams.Board()
    for i in range(4):
        board.add(agent='mate', island=0, family='mate', reward=10-i, valid=True, design={'n': i}, structure=[str(i)])
    migrant = board.add(agent='neighbor', island=1, family='neighbor', reward=99, valid=True, design={'n': 99}, structure=['99'])
    cfg = teams.config('ring-5x2-k10')
    visible = nested(teams, 'visible', dict(cfg=cfg, board=board, islands=[2]*5, family={}, names=[]))
    records = visible(NS(id='self', island=0), 10)
    assert migrant in [r['id'] for r in records]
    assert len(records) <= 4
    assert migrant not in [r['id'] for r in visible(NS(id='self', island=0), 9)]


@pytest.mark.parametrize('module_name', ['teams', 'frameworks'])
def test_reassignment_cannot_give_budget_to_stopped_worker(module_name):
    import importlib
    module = importlib.import_module('sepdesign.'+module_name)
    class Env:
        solve_budget = 10
        solves_used = 0
        best = None
        @property
        def solves_left(self): return self.solve_budget-self.solves_used
        def score(self): return 0
    workers = [NS(id=x, env=Env(), status='active', strategy=None, notebook='', history=[]) for x in 'ABC']
    actions = [{'type':'reassign','stop_worker':'A','give_to':'B'}, {'type':'reassign','stop_worker':'C','give_to':'A'}]
    sup = NS(id='supervisor', client=NS(call=lambda *a: ('manage', {'actions':actions})))
    scope = dict(workers=workers, cfg={'info':'full'}, names=[], board=teams.Board(), team_best=lambda:0,
                 team_solves=lambda:0, task={}, budgets=[10]*3, team_budget=30, system_prompt=lambda *a:'',
                 save_prompt=lambda *a:None, save_reasoning=lambda *a:None, manage_tools=[], sup=sup,
                 ev=lambda **kw:None, copy=copy)
    manage = nested(module, 'manage', scope)
    if module_name == 'teams': manage(10)
    else: manage(sup, 10, workers)
    assert workers[0].status == 'stopped'
    assert workers[1].env.solve_budget == 20
    assert workers[2].status == 'active'
    assert sum(w.env.solves_left for w in workers if w.status == 'active') == 30


def test_modal_no_windows_dependency(monkeypatch):
    monkeypatch.setenv('MODAL_PROXY_TOKEN', 'unused-test-token')
    monkeypatch.setattr(teams.ModalClient, '_find', lambda *a: {'id':'test', 'supported_features':['tools']})
    client = teams.ModalClient(None, 'test')
    assert client.endpoint_id == 'test'


def test_board_is_saved_before_shutdown(tmp_path):
    path = tmp_path/'board.jsonl'
    board = teams.Board(path)
    board.add(agent='a', design={'root':[]})
    assert json.loads(path.read_text())['id'] == 'R1'


def test_team_report_identity_collection_and_regeneration(tmp_path, monkeypatch):
    from scripts import collect_results, sync_reports
    task = find_task('hc16v3_dev_002')
    for model in ['model-a','model-b']:
        folder = tmp_path/'runs'/'teams'/'campaign'/model/'solo-low'
        teams.run_team(teams.config('solo', budget=2), task, make_service('mock', task=task), str(folder),
                       model=model, provider='scripted', max_rounds=2, log=lambda _:None)
        publish_team(payload(folder), tmp_path)
    manifests = list((tmp_path/'results').glob('*/*/*/*/manifest.json'))
    assert len(manifests) == 2
    monkeypatch.setattr(collect_results, 'ROOT', str(tmp_path))
    rows = collect_results.canonical_rows([])
    assert {r['model'] for r in rows} == {'model-a','model-b'}
    before = {p: p.read_bytes() for p in (tmp_path/'results').rglob('*') if p.is_file()}
    sync_reports.migrate(tmp_path)
    assert all(p.read_bytes() == data for p,data in before.items())


def test_exact_checkpoints_and_missing_evidence(tmp_path, monkeypatch):
    from scripts import collect_results
    data = dict(schema='team-report-v1', config=dict(run_id='run-a', model='model-a', task='hc16v3_dev_002', config={'preset':'open'}, budgets={'a':200}),
                summary={'status':'incomplete snapshot','team_solves':110,'team_best':3}, board=[], usage={}, turns={},
                events=[{'kind':'round','team_solves':110,'team_best':3}], team_curve=[[20,1,1],[95,3,2],[110,3,3]])
    publish_team(data,tmp_path)
    monkeypatch.setattr(collect_results,'ROOT',str(tmp_path))
    row=collect_results.canonical_rows([])[0]
    assert row['best_at_100']==3
    assert row['best_at_200'] is None
    data['team_curve']=None
    publish_team(data,tmp_path)
    assert collect_results.canonical_rows([])[0]['best_at_100'] is None


def test_export_preserves_models_and_shows_snapshot_status(tmp_path,monkeypatch):
    from scripts import summarize_teams
    import sepdesign.team_report as report
    import sys
    camp=tmp_path/'campaign'
    for model in ['model-a','model-b']:
        folder=camp/model/'solo-low'
        folder.mkdir(parents=True)
        (folder/'config.json').write_text(json.dumps(dict(run_id=model+'-run',model=model,task='hc16v3_dev_002',config={'preset':'solo'},islands=[1])))
        (folder/'events.jsonl').write_text(json.dumps(dict(kind='round',round=1,team_solves=4,team_best=1,usd_real=0,t=1))+'\n')
    out=tmp_path/'export'
    monkeypatch.setattr(report,'publish_team',lambda data: None)
    monkeypatch.setattr(sys,'argv',['summarize',str(camp),'--out',str(out)])
    summarize_teams.main()
    assert len(list(out.glob('*/*/config.json')))==2
    rows=json.loads((out/'summary.json').read_text())
    assert {r['model'] for r in rows}=={'model-a','model-b'}
    assert all(r['best_at']['100'] is None for r in rows)
    assert 'stopped early' in (out/'summary.md').read_text()


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), -0.1, 1.1])
def test_min_finish_rejects_invalid_programmatic_configuration(value, tmp_path):
    with pytest.raises(ValueError, match='finite fraction'):
        teams.config('solo', min_finish=value)
    cfg = teams.config('solo')
    cfg['min_finish'] = value
    with pytest.raises(ValueError, match='finite fraction'):
        teams.run_team(cfg, {}, None, str(tmp_path/'run'))
    assert not (tmp_path/'run').exists()


@pytest.mark.parametrize('value', ['nan', 'inf', '-inf', '-0.1', '1.1'])
def test_cli_rejects_invalid_min_finish_before_setup(value, monkeypatch, tmp_path):
    import sys
    from scripts import run_teams
    def unexpected(*args, **kwargs):
        pytest.fail('Invalid min_finish must be rejected before setup or provider access')
    monkeypatch.setattr(run_teams, 'load_dotenv', unexpected)
    monkeypatch.setattr(run_teams, 'make_service', unexpected)
    monkeypatch.setattr(sys, 'argv', ['run_teams', '--min-finish='+value, '--out', str(tmp_path/'run')])
    with pytest.raises(SystemExit) as error:
        run_teams.main()
    assert error.value.code == 2
    assert not (tmp_path/'run').exists()


@pytest.mark.parametrize('value', [None, 0, 0.5, 1])
def test_min_finish_accepts_optional_fraction_and_boundaries(value):
    assert teams.config('solo', min_finish=value)['min_finish'] == value


def test_min_finish_refuses_then_accepts_at_rounded_up_threshold(tmp_path, monkeypatch):
    task = find_task('hc16v3_dev_002')
    prompts = []
    def call(self, system, user, tools, effort=None):
        prompts.append(user)
        if len(prompts) in (2, 4):
            return 'finish', {'note': 'try finishing'}
        return 'submit_edits', {'edits': [{'op': 'set', 'node': '', 'n_stages': 50+len(prompts),
                                          'reflux_ratio': 3.56, 'reboil_ratio': 3.56,
                                          'pressure_drop_fraction': 0.04}]}
    monkeypatch.setattr(teams.ScriptedClient, 'call', call)
    summary = teams.run_team(teams.config('solo', budget=3, min_finish=0.5), task,
                             make_service('mock', task=task), str(tmp_path),
                             provider='scripted', max_rounds=4, log=lambda _: None)
    events = [json.loads(line) for line in (tmp_path/'events.jsonl').read_text().splitlines()]
    assert [(event['kind'], event['round']) for event in events
            if event['kind'] in ('finish_refused', 'finish')] == [('finish_refused', 2), ('finish', 4)]
    assert 'until you have used at least 2.' in prompts[2]
    assert summary['team_solves'] == 2
    assert summary['status'] == 'all_done'
