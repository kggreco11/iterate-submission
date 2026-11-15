from agents.llm_agent import run_agent
from sepdesign import hc12_tasks, make_env, make_service


def test_scripted_run_retains_empty_design_baseline(tmp_path):
    task = hc12_tasks('dev')[0]
    env = make_env(task, make_service('mock'), budget=8)
    summary = run_agent(env, task, provider='scripted', out_dir=str(tmp_path))
    assert summary['solves_used'] == 8
    assert summary['best_valid_reward'] >= 0
    assert env.best[2]['valid']
