import copy
import pytest
from sepdesign import hc12_tasks, make_env, make_service
from sepdesign.validation import validate_result

COL={'op':'set','node':'','n_stages':50,'reflux_ratio':3,'reboil_ratio':3,'pressure_drop_fraction':0.1}

def setup():
    env=make_env(hc12_tasks('dev')[0],make_service('mock'),budget=10)
    env.evaluate()
    env.apply([COL])
    result=env.evaluate()
    return env,result

def test_empty_is_valid_and_failed_column_cannot_replace_it():
    env=make_env(hc12_tasks('dev')[0],make_service('mock'),budget=10)
    assert env.evaluate()['validation']['eligible']
    env.apply([{**COL,'reflux_ratio':30,'reboil_ratio':30}])
    assert not env.evaluate()['validation']['eligible']
    assert env.best[1]=={}

@pytest.mark.parametrize('corruption',['mass','nan','cost','topology','pressure','budget','skipped','root_state','child_state'])
def test_checker_rejects_corrupt_outputs(corruption):
    env,r=setup(); assert r['validation']['eligible']
    r=copy.deepcopy(r)
    if corruption=='mass':r['nodes']['']['column_result']['tops']['flows'][0]+=1
    if corruption=='nan':r['nodes']['']['column_result']['qr']=float('nan')
    if corruption=='cost':r['tac']=0
    if corruption=='topology':del r['nodes']['T']
    if corruption=='pressure':r['nodes']['']['column_result']['tops']['P']=-1
    if corruption=='budget':r['nodes']['']['status']='not_solved_budget'
    if corruption=='skipped':r['nodes']['']['status']='negligible_feed'
    if corruption=='root_state':r['nodes']['']['T']+=10
    if corruption=='child_state':r['nodes']['T']['T']+=10
    assert not validate_result(env.design,r,env.econ,env.bounds,env.max_columns)['eligible']

def test_missing_cost_is_failure():
    from sepdesign.service import SolveService
    from sepdesign.mock_backend import MockBackend
    class MissingCost(MockBackend):
        def solve_column(self,case):
            r=super().solve_column(case);r['tac_usd_per_year']=None;return r
    env=make_env(hc12_tasks('dev')[0],SolveService(MissingCost()),budget=10)
    env.apply([COL]);r=env.evaluate()
    assert r['failed']==[''] and not r['validation']['eligible']
