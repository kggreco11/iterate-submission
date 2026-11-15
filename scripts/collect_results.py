"""
Collect every result so far into one place: results/all_results.csv and .json (one row per run), plus results/data/designs.jsonl (the best plant of
each run). Re-run after new runs; it reads the committed result folders, the local run folders under runs/ (git-ignored) when present, and the
canonical report bundles. Existing archived robot rows are retained when their raw local files are unavailable.

    python scripts/collect_results.py

Columns: version, task, method, model, condition, seed, budget (told), solves_used, turns, reward, ceiling, share_of_ceiling, best_known,
share_of_best_known, best_at_40/100/200 solves, usd (estimated model spend; blank = not recorded), status, source, note.
"best_known" is the best valid reward any row reached on that task (agents, local polish, re-priced plants); it is a reference, not an optimum.
"""
import csv
import glob
import json
import os
from pathlib import Path
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sepdesign.taskset import find_task  # noqa: E402
from sepdesign.tasks import Economics  # noqa: E402

VERSION = {"hc12": "V1", "hc16v2": "V2", "hc16v3": "V3"}
CEIL = {}


def ceiling(task_id):
    if task_id not in CEIL:
        CEIL[task_id] = Economics(find_task(task_id)).upper_bound_reward
    return CEIL[task_id]


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def at(curve, n):
    """Best valid reward using at most n solves from [(solves, best)]."""
    b = None
    for s, v in curve:
        if s <= n:
            b = v
    return b


def llm_curve(turns):
    best, out = 0.0, []
    for t in turns:
        if t.get("action") != "edit":
            continue
        if t.get("valid") and t["reward"] > best:
            best = t["reward"]
        out.append((t["solves_used"], best))
    return out


def design_of(run):
    tr = run.get("trace") or []
    return tr[-1]["columns"] if tr else {}


def llm_rows(pattern, designs):
    rows = []
    for rf in sorted(glob.glob(pattern)):
        run = json.load(open(rf))
        d = os.path.splitext(rf)[0] if not rf.endswith("run.json") else os.path.dirname(rf)
        summ = json.load(open(os.path.join(d, "summary.json"))) if os.path.exists(os.path.join(d, "summary.json")) else {}
        turns = [json.loads(l) for l in open(os.path.join(d, "turns.jsonl"))] if os.path.exists(os.path.join(d, "turns.jsonl")) else []
        c = llm_curve(turns)
        task = run["task"]
        rows.append({"run_id": summ.get("run_id", os.path.basename(d)), "task": task, "method": "agent", "model": (run.get("llm") or summ).get("model", summ.get("model")), "condition": "single agent",
                     "seed": run.get("seed", summ.get("seed")), "budget": run.get("budget"), "solves_used": run.get("solves_used"),
                     "turns": summ.get("turns", len(turns)), "reward": run.get("best_reward"), "best_at_40": at(c, 40), "best_at_100": at(c, 100),
                     "best_at_200": at(c, 200), "usd": summ.get("usd_estimated_total"), "status": summ.get("status"), "source": rel(rf), "note": ""})
        designs.append({"task": task, "method": "agent", "model": rows[-1]["model"], "seed": rows[-1]["seed"], "reward": run.get("best_reward"),
                        "columns": design_of(run), "products": (run.get("trace") or [{}])[-1].get("products"), "source": rel(rf)})
    return rows


def robot_rows(pattern, note=""):
    rows = []
    for rf in sorted(glob.glob(pattern)):
        run = json.load(open(rf))
        if "best_reward" not in run:
            continue
        c = sorted((int(k), v) for k, v in (run.get("curve") or {}).items() if v is not None)
        rows.append({"task": run["task"], "method": "robot", "model": run.get("entry"), "condition": "search baseline", "seed": run.get("seed"),
                     "budget": run.get("budget"), "solves_used": run.get("solves_used"), "turns": None, "reward": run.get("best_reward"),
                     "best_at_40": at(c, 40), "best_at_100": at(c, 100), "best_at_200": at(c, 200), "usd": 0.0, "status": "budget",
                     "source": rel(rf) + " (local, not committed)", "note": note})
    return rows


def polish_rows(path, method, note):
    rows = []
    if not os.path.exists(path):
        return rows
    for r in json.load(open(path)):
        rows.append({"task": r["task"], "method": method, "model": "claude-opus-5-5 plant + scripts/polish_check.py", "condition": "reference",
                     "seed": 0, "budget": None, "solves_used": r.get("solves_used"), "turns": None, "reward": r["final_reward"], "best_at_40": None,
                     "best_at_100": None, "best_at_200": None, "usd": 0.0, "status": "done", "source": rel(path),
                     "note": f"{note}; starting plant re-simulated at {r['base_reward']:.3f}"})
    return rows


def canonical_rows(designs):
    """Read published bundles without depending on a remote branch or VM."""
    rows = []
    for path in sorted(Path(ROOT, 'results').glob('*/*/*/*/manifest.json')):
        m = json.loads(path.read_text())
        if m.get('schema') != 'report-bundle-v1':
            continue
        folder = path.parent
        summary = json.loads((folder/'summary.json').read_text())
        data = json.loads((folder/'report-data.json').read_text()) if (folder/'report-data.json').exists() else {}
        if data.get('schema') == 'team-report-v1':
            cfg = data['config']
            curve = [(e[0], e[1]) for e in (data.get('team_curve') or [])]
            used = summary.get('team_solves')
            checkpoint = lambda n: at(curve, n) if used is not None and n <= used else None
            rows.append(dict(run_id=m['run_id'], task=m['task'], method='agent', model=m['model'], condition=m['condition'],
                seed=cfg.get('seed'), budget=sum(cfg.get('budgets', {}).values()), solves_used=summary.get('team_solves'),
                reward=summary.get('team_best'), best_at_40=checkpoint(40), best_at_100=checkpoint(100), best_at_200=checkpoint(200),
                usd=summary.get('usd_cached_price_estimate'), status=summary.get('status'), source=rel(folder/'report-data.json'),
                note=data.get('limitations', '') + (' Saved plant evidence unavailable.' if not data['board'] else ' Saved team plant evidence.')))
            best = {}
            for rec in data['board']:
                if rec.get('valid') and (rec['agent'] not in best or rec['reward'] > best[rec['agent']]['reward']):
                    best[rec['agent']] = rec
            for agent, rec in best.items():
                designs.append(dict(run_id=m['run_id'], agent_id=agent, task=m['task'], method='agent', model=m['model'],
                    seed=cfg.get('seed'), reward=rec['reward'], columns=rec['design'], source=rows[-1]['source']))
            continue
        team = 'agents' in data and 'config' in data
        replay = data.get('replay', {})
        curve = llm_curve(data.get('turns', []))
        if team:
            reward = max((a.get('best_valid_reward') for a in summary['agents'].values()
                          if a.get('best_valid_reward') is not None), default=None)
            budget = sum(data['config']['allocations'])
            used = summary['team_distinct_queries']
            usd = summary.get('known_llm_usd') if summary.get('unknown_cost_requests') == 0 else None
        else:
            reward = replay.get('best_reward', summary.get('best_valid_reward', summary.get('best_reward')))
            budget = replay.get('budget')
            used = summary.get('solves_used')
            usd = summary.get('usd_estimated_total') if summary.get('requests_with_unknown_cost') == 0 else None
        rows.append(dict(run_id=m['run_id'], task=m['task'], method='agent', model=m['model'],
            condition=m['condition'], seed=summary.get('seed', data.get('config',{}).get('repetition')),
            budget=budget, solves_used=used, turns=summary.get('submissions' if team else 'turns'),
            reward=reward, best_at_40=at(curve,40), best_at_100=at(curve,100), best_at_200=at(curve,200),
            usd=usd, status=summary.get('status', summary.get('stop_reason', m['status'])),
            source=rel(folder/('report-data.json' if data else 'summary.json')),
            note='Best team design; unequal total budgets; model cost excludes VM/memory.' if team else
                 ('Legacy HTML and summary only; replay/budget unavailable.' if not data else 'Canonical saved report evidence.')))
        payloads = data['agents'].items() if team else [(None, data)]
        for agent, payload in payloads:
            r = payload.get('replay', {})
            if r.get('trace'):
                designs.append(dict(run_id=m['run_id'], agent_id=agent, task=m['task'], method='agent', model=m['model'],
                    seed=rows[-1]['seed'], reward=r.get('best_reward'), columns=design_of(r),
                    products=r['trace'][-1].get('products'), source=rows[-1]['source']))
    return rows


def main():
    designs = []
    rows = []
    rows += llm_rows(os.path.join(ROOT, "results/opus-5-5-dev-first-look/*/run.json"), designs)
    rows += llm_rows(os.path.join(ROOT, "results/hc16v2-first-look/opus-5-5/*.json"), designs)
    rows += llm_rows(os.path.join(ROOT, "results/hc16v3-first-look/opus-5-5/*.json"), designs)
    rows += llm_rows(os.path.join(ROOT, "results/hc16v3-first-look/kimi-k3.1-pro/*.json"), designs)
    for r in rows:
        if r["task"].startswith("hc12"):
            r["note"] = "cut short by API credit exhaustion (lower bound)"
    rows += robot_rows(os.path.join(ROOT, "runs/bench/*.json"), "V1 robots ran on an earlier revision of the validity gate")
    rows += robot_rows(os.path.join(ROOT, "runs/v2_bench/*.json"))
    rows += robot_rows(os.path.join(ROOT, "runs/v3_bench/*.json"), "V3 robot campaign stopped after 9 of 28 runs; robots do not use side draws or double effects")
    rows += polish_rows(os.path.join(ROOT, "results/opus-5-5-dev-first-look/polish_check.json"), "agent plant + local polish", "Opus V1 plant polished")
    rows += polish_rows(os.path.join(ROOT, "results/hc16v2-first-look/polish_check.json"), "agent plant + local polish", "Opus V2 plant polished")
    rows += polish_rows(os.path.join(ROOT, "results/hc16v3-first-look/polish_check.json"), "agent plant + local polish", "Opus V3 plant polished")
    rows += polish_rows(os.path.join(ROOT, "results/hc16v3-first-look/polish_v2plants_at_v3.json"), "other version's plant re-priced + polish",
                        "Opus V2 plant scored at V3 prices, then polished")
    canonical_designs = []
    canonical = canonical_rows(canonical_designs)
    published_ids = {r['run_id'] for r in canonical}
    rows = [r for r in rows if r.get('run_id') not in published_ids] + canonical
    published_sources = {r['source'] for r in rows}
    archive = Path(ROOT, 'results/all_results.json')
    if archive.exists():
        for old in json.loads(archive.read_text())['rows']:
            if old['method'] == 'robot' and old['source'] not in published_sources:
                old = dict(old)
                marker = ' Archived aggregate; raw local run unavailable in this checkout.'
                if marker.strip() not in old.get('note',''):
                    old['note'] = old.get('note','') + marker
                rows.append(old)
    canonical_keys = {(d['task'], d['model'], d['seed'], d['reward']) for d in canonical_designs}
    designs = [d for d in designs if (d['task'],d['model'],d['seed'],d['reward']) not in canonical_keys] + canonical_designs
    best = {}
    for r in rows:
        if r["reward"] is not None and "UNFINISHED" not in str(r["status"]):
            best[r["task"]] = max(best.get(r["task"], -1e9), r["reward"])
    for r in rows:
        fam = r["task"].split("_")[0]
        r["version"] = VERSION.get(fam, fam)
        r["ceiling"] = ceiling(r["task"])
        r["share_of_ceiling"] = r["reward"] / r["ceiling"] if r["reward"] is not None else None
        r["best_known"] = best.get(r["task"])
        r["share_of_best_known"] = r["reward"] / r["best_known"] if r["reward"] is not None and r["best_known"] else None
    order = ["run_id", "version", "task", "method", "model", "condition", "seed", "budget", "solves_used", "turns", "reward", "ceiling", "share_of_ceiling",
             "best_known", "share_of_best_known", "best_at_40", "best_at_100", "best_at_200", "usd", "status", "source", "note"]
    rows.sort(key=lambda r: (r["version"], r["task"], r["method"], str(r["model"]), str(r["condition"]), r["seed"] or 0))
    os.makedirs(os.path.join(ROOT, "results/data"), exist_ok=True)
    with open(os.path.join(ROOT, "results/all_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=order, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in ((k, r.get(k)) for k in order)})
    json.dump({"generated_by": "scripts/collect_results.py", "rows": [{k: r.get(k) for k in order} for r in rows]},
              open(os.path.join(ROOT, "results/all_results.json"), "w"), indent=1)
    with open(os.path.join(ROOT, "results/data/designs.jsonl"), "w") as f:
        for d in designs:
            f.write(json.dumps(d) + "\n")
    n = {}
    for r in rows:
        n[(r["version"], r["method"])] = n.get((r["version"], r["method"]), 0) + 1
    print(f"{len(rows)} rows, {len(designs)} designs:", {f"{a} {b}": c for (a, b), c in sorted(n.items())})


if __name__ == "__main__":
    main()
