"""
Non-agent baselines, all budgeted by distinct column solves (env.solve_budget) so their best-so-far curves (env.curve, env.best_so_far_at)
compare directly with an agent's.

  first_cut             the same fixed column settings on every stream that is not pure yet, built one column at a time (breadth first)
  greedy_local          hill climbing from the current design, one setting at a time, deepest column first
  random_designs        repeated random whole designs (random settings per column), keep the best
  random_then_greedy    random designs for 60% of the budget, then greedy refinement of the best one
"""
import random

FIXED = (53, 3.56, 3.56, 0.04)           # n_stages, reflux, boil-up, pressure-drop fraction
MIN_GAIN = 0.002


def _off_spec_leaves(env, res):
    """Streams that are sold for nothing and carry no column: candidates for another column, in breadth-first order (tops before bottoms)."""
    out = [p for p, n in res["nodes"].items() if n["status"] == "sold" and n["value"] <= 0 and p not in env.design]
    return sorted(out, key=lambda p: (len(p), p.replace("T", "0").replace("B", "1")))


def _clip(env, key, v):
    lo, hi = env.bounds[key]
    v = max(lo, min(hi, v))
    return int(round(v)) if key == "n_stages" else round(v, 2)


def first_cut(env, spec=FIXED, chooser=None):
    """Put a column on every impure stream, one at a time, evaluating after each. Stops when nothing is left to separate, the column cap is
    reached or the budget is used up."""
    while True:
        res = env.evaluate()
        todo = _off_spec_leaves(env, res)
        if not todo or env.solves_left <= 0 or len(env.design) >= env.max_columns:
            return res
        env.design[todo[0]] = tuple(chooser(todo[0]) if chooser else spec)


def greedy_local(env, passes=3, log=None):
    """Hill climbing from the best design so far. Moves per column: pressure drop +-0.08; reflux and boil-up x0.8 / x1.25; stages x0.85 / x1.15."""
    if env.best is not None:
        env.design = dict(env.best[1])
    r0 = env.evaluate()
    cur = r0["reward"] if r0["valid"] else -1e18                      # an invalid starting design is replaced by the first valid improvement
    order = lambda: sorted(env.design, key=lambda p: (-len(p), p))   # noqa: E731
    for _ in range(passes):
        improved = False
        for path in order():
            if path not in env.design:
                continue
            for k, key in enumerate(("n_stages", "reflux_ratio", "reboil_ratio", "pressure_drop_fraction")):
                base = env.design[path]
                if key == "n_stages":
                    cands = [base[0] * 0.85, base[0] * 1.15]
                elif key == "pressure_drop_fraction":
                    cands = [base[3] - 0.08, base[3] + 0.08]
                else:
                    cands = [base[k] * 0.8, base[k] * 1.25]
                for c in cands:
                    if env.solves_left <= 0:
                        return env.best[0]
                    new = list(base)
                    new[k] = _clip(env, key, c)
                    if tuple(new) == tuple(base):
                        continue
                    saved = dict(env.design)
                    env.design[path] = tuple(new)
                    res = env.evaluate()
                    if res["valid"] and res["reward"] > cur + MIN_GAIN:
                        cur, improved = res["reward"], True
                        base = env.design[path]
                    else:
                        env.design = saved
                    if log:
                        log(env)
        if not improved:
            break
    return env.best[0]


def random_designs(env, seed=0, until_used=None):
    """Repeated random first cuts until the budget is gone. Each column gets uniformly random settings within the bounds."""
    rnd = random.Random(seed)
    b = env.bounds

    def chooser(path):
        return (rnd.randint(int(b["n_stages"][0]), int(b["n_stages"][1])), round(rnd.uniform(*b["reflux_ratio"]), 2),
                round(rnd.uniform(*b["reboil_ratio"]), 2), round(rnd.uniform(*b["pressure_drop_fraction"]), 2))

    limit = env.solve_budget if until_used is None else min(env.solve_budget, until_used)
    while env.solves_used < limit and env.solves_left > 0:
        env.design = {}
        before = env.solves_used
        first_cut(env, chooser=chooser)
        if env.solves_used == before:
            break
    return env.best[0] if env.best else None


def random_then_greedy(env, seed=0, frac=0.6):
    random_designs(env, seed=seed, until_used=int(frac * env.solve_budget))
    return greedy_local(env)
