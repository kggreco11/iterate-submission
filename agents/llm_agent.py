"""
A language-model agent for the plant-design environment, for Anthropic or OpenAI models, with per-request token and dollar accounting.

Each turn the model sees the task brief (system prompt) and the current state (the plant tree and its simulated result, the best valid score, and a
short history), and calls `submit_edits` with edits to the design (or `finish`). The harness applies the edits, re-simulates from the feed down,
and records everything. The agent never sees any search baseline or reference score.

    run_agent(env, task, seed, provider="anthropic", model="claude-opus-5-5", max_turns=80, max_usd=15, out_dir="runs/llm")

Providers: "anthropic" (messages API with forced tool use), "openai" (Responses API with required tool call; written to the API
documentation but NOT yet exercised), "scripted" (no API: a fixed-setting policy used to test the loop for free).
"""
import json
from copy import deepcopy
import os
import time
import uuid
from contextlib import nullcontext

import numpy as np

from sepdesign.env import EditError
from sepdesign.hc12 import MW, TB_K, HC12
from sepdesign.hc16 import COMPONENT_DATA
from sepdesign.ledger import Ledger
from agents.kimi import Kimi, ToolResponseError

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "note": {"type": "string", "description": "One or two sentences: what you are trying and why."},
        "edits": {"type": "array", "description": "Edits applied in order to the current design, then the whole plant is re-simulated.",
                  "items": {"type": "object", "properties": {
                      "op": {"type": "string", "enum": ["set", "sell", "revert"]},
                      "node": {"type": "string", "description": "'' = the feed, then strings of T (tops), B (bottoms) and, where a column has a side draw, S (side stream), e.g. 'TB'."},
                      "n_stages": {"type": "integer"}, "reflux_ratio": {"type": "number"}, "reboil_ratio": {"type": "number"},
                      "pressure_drop_fraction": {"type": "number"},
                      "side_draw": {"type": "object", "description": "Optional, only if the task allows side draws: a third outlet taken from the middle of this column.",
                                    "properties": {"stage": {"type": "integer"}, "phase": {"type": "string", "enum": ["liquid", "vapour"]},
                                                   "fraction": {"type": "number"}}, "required": ["stage", "phase", "fraction"]},
                      "double_effect": {"type": "object", "description": "Optional, only if the task allows double-effect columns: do this split with two columns at different pressures.",
                                        "properties": {"fraction": {"type": "number"}, "low_pressure_drop_fraction": {"type": "number"}},
                                        "required": ["fraction", "low_pressure_drop_fraction"]}}, "required": ["op"]}}},
    "required": ["edits"]}
EDIT_SCHEMA['properties'].update({
    'evidence_ids': {'type': 'array', 'items': {'type': 'string'}},
    'source_design': {'type': 'string', 'description': 'Retrieved design version to copy before applying edits.'},
})
# Keep the historical schema as the default; opt in per request, never globally.
_V3_OPTIONS = {key: EDIT_SCHEMA['properties']['edits']['items']['properties'].pop(key)
               for key in ('side_draw', 'double_effect')}
EDIT_SCHEMA['properties']['edits']['items']['properties']['node']['description'] = "'' = the feed, then strings of T (tops) and B (bottoms), e.g. 'TB'."


def edit_schema(env=None):
    schema = deepcopy(EDIT_SCHEMA)
    if env is not None and env.econ.task['task_id'].startswith('hc16v3_'):
        props = schema['properties']['edits']['items']['properties']
        for key in _V3_OPTIONS:
            if (env.econ.task.get('levers') or {}).get(key):
                props[key] = deepcopy(_V3_OPTIONS[key])
        if 'side_draw' in props:
            props['node']['description'] += " S names an existing side-draw outlet."
    return schema


FINISH_SCHEMA = {"type": "object", "properties": {"note": {"type": "string"}}}


def load_dotenv(path=".env"):
    """Load KEY=VALUE lines from a local .env into os.environ (never printed, never committed: .env is git-ignored)."""
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def system_prompt(task, budget, env):
    comps = task["components"]
    feed = np.array(task["feed_flows_mol_s"], float)
    price = np.array(task["prices_usd_per_mol"], float)
    sec = env.econ.seconds
    rows = []
    for i, c in enumerate(comps):
        tb = f"{COMPONENT_DATA[c][0]:.1f}" if c in COMPONENT_DATA else "?"
        rows.append(f"| {c} | {tb} | {feed[i]:.0f} | {price[i]:.4f} | {feed[i] * price[i] * sec / 1e6:.0f} |")
    b = env.bounds
    side_text = ""
    if env.side_draw_allowed:
        side_text = (" SIDE DRAWS: a column may also have a side draw. Add \"side_draw\":{\"stage\":s,\"phase\":\"liquid\"|\"vapour\",\"fraction\":f} to its set edit "
                     "to take fraction f (0.02-0.6) of the column's feed as a third outlet at stage s (2 to n-1, not the feed stage; stage 1 is the condenser and "
                     "stage n the reboiler). That outlet is named p+'S' and can be sold or fed to a further column like any other. It lies between the tops and "
                     "the bottoms in volatility, so it can deliver a middle cut (for example a blend) from one column instead of two, but lighter and heavier "
                     "components leak into it, so its purity is limited. A set edit replaces all of a column's settings: repeat the side_draw whenever you re-set "
                     "a column that has one, and omit it to remove the side draw (and the columns below it).")
    if env.double_effect_allowed:
        side_text += (" DOUBLE-EFFECT COLUMNS: a column may instead be built as a double effect. Add \"double_effect\":{\"fraction\":f,"
                      "\"low_pressure_drop_fraction\":d} to its set edit: the split is then done by TWO columns with the same stages, reflux and boil-up. "
                      "A share f (0.2-0.8) of the feed goes to a high-pressure (HP) column whose valve drops the pressure by the column's own "
                      "pressure_drop_fraction; the rest goes to a low-pressure (LP) column whose valve drops it by d (must be larger, up to the bound). Their "
                      "tops are mixed and their bottoms are mixed, so the outlets 'T' and 'B' are as for one column. If the HP condenser is at least 10 K hotter "
                      "than the LP reboiler, the HP condenser's heat boils the LP reboiler: that heat (the smaller of the two duties) is bought once instead of "
                      "twice, which saves its heating and cooling cost; a shared exchanger is added to the capital. Otherwise there is no saving and you pay "
                      "for two columns. A double effect costs two solves and cannot have a side draw. It pays only where the saved energy is worth more than "
                      "the second column: you will see each column's temperatures, the heat passed and the saving in the results.")
    return f"""You are a senior chemical process engineer. Design a distillation plant that separates a hydrocarbon feed into pure, sellable products, as profitably as you can.

FEED (all fixed): {feed.sum():.0f} mol/s at {task['temperature_K']:.0f} K and {task['pressure_Pa'] / 1e5:.1f} bar. {len(comps)} components:
| component | normal boiling point (K) | feed (mol/s) | price ($/mol) | value if all sold pure ($M/yr) |
|---|---|---|---|---|
""" + "\n".join(rows) + f"""

THE PLANT is a tree of distillation columns. Paths name streams: '' is the feed; a column at path p has two outlets, p+'T' (tops, the light fraction) and p+'B' (bottoms, the heavy fraction). A stream with no column is sold as it is. {env.econ.describe_rules()} A column can only be added below an existing column (or at the feed).

EACH COLUMN has four settings you choose: n_stages ({b['n_stages'][0]}-{b['n_stages'][1]}), reflux_ratio ({b['reflux_ratio'][0]}-{b['reflux_ratio'][1]}), reboil_ratio ({b['reboil_ratio'][0]}-{b['reboil_ratio'][1]}) and pressure_drop_fraction ({b['pressure_drop_fraction'][0]}-{b['pressure_drop_fraction'][1]}: the fraction of the incoming pressure dropped by a valve before the column; the column then runs at that lower pressure). The feed enters the middle stage.{side_text} Columns are simulated rigorously (equilibrium stages, Peng-Robinson thermodynamics).

OBJECTIVE: maximise reward = (annual value of all products sold - annual cost of all columns) / {env.econ.reward_norm / 1e6:.0f} ($M/yr, the value of the most valuable pure stream in the feed). Each column's annual cost covers its size (stages, diameter), its heat duties, and the temperature of its condenser and reboiler (a cold condenser needs expensive refrigeration). More stages and more reflux give purer products but cost more; you are not required to separate everything. The empty design (no columns) scores 0.

BUDGET: you may use at most {budget} distinct column solves. A column counts once per distinct (feed, settings); re-evaluating columns that have not changed is free. When the budget is spent, columns not yet simulated are not evaluated.

HOW YOU WORK: each turn call submit_edits with a list of edits applied to the current design: {{"op":"set","node":"TB","n_stages":60,"reflux_ratio":4,"reboil_ratio":4,"pressure_drop_fraction":0.1}}, {{"op":"sell","node":"T"}} (remove that column and everything below it) or {{"op":"revert"}} (back to your best valid design). You may change many columns at once. The whole plant is then re-simulated from the feed down and you see each column's result. A design counts only if every column in it converged (a failed column makes the design invalid). Your final score is the best valid design you evaluated. Call finish when you have nothing more worth trying. Always respond by calling one of the two tools (submit_edits or finish), never with plain text alone. Spend your solves wisely: the budget is the limiting resource."""


def _state_text(env, result, turn, budget, history, error, t_best):
    best = env.score()
    head = f"Turn {turn}. Solves used {env.solves_used}/{budget}. Best valid reward so far: " + (f"{best:.3f} (turn {t_best})" if best is not None else "none yet")
    parts = [head]
    if error:
        parts.append(f"YOUR LAST EDITS WERE REJECTED (nothing was changed, no solves charged): {error}")
    if result is None:
        parts.append("Current design: empty (no columns). Reward 0.")
    else:
        parts.append("Current design (path: stages/reflux/boil-up/pressure-drop[, side draw]): " + "; ".join(
            f"'{p}': {s[0]}/{s[1]}/{s[2]}/{s[3]}" + (f" side {s[4][1]} stage {s[4][0]} {s[4][2]}" if len(s) > 4 and s[4] is not None else "")
            + (f" double effect {s[5][0]} to HP, LP dp {s[5][1]}" if len(s) > 5 else "")
            for p, s in sorted(env.design.items(), key=lambda kv: (len(kv[0]), kv[0]))))
        parts.append("Result of the current design (each stream: its six largest components):\n" + env.render(result, top=6))
    if history:
        parts.append("Recent turns (turn: reward, valid, solves used | your note):\n" + "\n".join(history[-12:]))
    return "\n\n".join(parts)


class _Anthropic:
    def __init__(self, model, ledger):
        import anthropic
        self.c, self.model, self.ledger = anthropic.Anthropic(max_retries=2), model, ledger
        self.tools = [{"name": "submit_edits", "description": "Edit the design, then re-simulate the plant.", "input_schema": EDIT_SCHEMA},
                      {"name": "finish", "description": "Stop: nothing more worth trying.", "input_schema": FINISH_SCHEMA}]

    def call(self, system, user, env=None):
        self.tools[0]['input_schema'] = edit_schema(env)
        try:
            r = self.c.messages.create(model=self.model, max_tokens=6000, system=system, tools=self.tools,
                                       messages=[{"role": "user", "content": user}])
        except Exception as ex:  # noqa: BLE001
            self.ledger.record(None, None, None, ok=False, error=f"{type(ex).__name__}: {str(ex)[:200]}")
            raise
        u = r.usage
        self.ledger.record(r.id, u.input_tokens, u.output_tokens, cached=getattr(u, "cache_read_input_tokens", None))
        for b in r.content:
            if b.type == "tool_use":
                return b.name, b.input
        return "noop", {"note": " ".join(getattr(b, "text", "") for b in r.content)[:200]}


class _OpenAI:
    def __init__(self, model, ledger):
        import openai
        self.c, self.model, self.ledger = openai.OpenAI(max_retries=2), model, ledger
        self.tools = [{"type": "function", "function": {"name": "submit_edits", "description": "Edit the design, then re-simulate.", "parameters": EDIT_SCHEMA}},
                      {"type": "function", "function": {"name": "finish", "description": "Stop.", "parameters": FINISH_SCHEMA}}]

    def call(self, system, user, env=None):
        self.tools[0]['function']['parameters'] = edit_schema(env)
        try:
            r = self.c.responses.create(model=self.model,
                tools=[dict(type='function', strict=False, **t['function']) for t in self.tools],
                tool_choice='required', parallel_tool_calls=False,
                reasoning={'effort': 'low'}, max_output_tokens=2500, store=False,
                input=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}])
        except Exception as ex:  # noqa: BLE001
            self.ledger.record(None, None, None, ok=False, error=f"{type(ex).__name__}: {str(ex)[:200]}")
            raise
        u = r.usage
        self.ledger.record(r.id, u.input_tokens, u.output_tokens,
            cached=getattr(getattr(u, 'input_tokens_details', None), 'cached_tokens', None),
            reasoning=getattr(getattr(u, 'output_tokens_details', None), 'reasoning_tokens', None))
        calls = [item for item in r.output if item.type == 'function_call']
        if len(calls) != 1:
            raise ValueError('Expected one complete function call from model')
        return calls[0].name, json.loads(calls[0].arguments)


class _Scripted:
    """No API: puts the same fixed settings on every impure stream, then finishes. Costs nothing; tests the loop, ledger and logging."""

    def __init__(self, ledger):
        self.ledger = ledger

    def call(self, system, user, env=None):
        from sepdesign import baselines
        todo = []
        if env.last is not None:
            todo = baselines._off_spec_leaves(env, env.last)
        if env.last is None:
            todo = [""]
        if not todo or len(env.design) >= env.max_columns:
            self.ledger.record("scripted", 0, 0, note="scripted: no API call")
            return "finish", {"note": "scripted policy done"}
        self.ledger.record("scripted", 0, 0, note="scripted: no API call")
        return "submit_edits", {"note": "scripted: fixed settings on the next impure stream",
                                "edits": [{"op": "set", "node": todo[0], "n_stages": 53, "reflux_ratio": 3.56, "reboil_ratio": 3.56,
                                           "pressure_drop_fraction": 0.04}]}


def run_agent(env, task, seed=0, provider="anthropic", model="claude-opus-5-5", max_turns=80, max_usd=None, out_dir="runs/llm", run_id=None, agent_id="agent-0", timings=None):
    load_dotenv()
    run_id = run_id or f"{task['task_id']}_{provider}_{model}_s{seed}_{uuid.uuid4().hex[:6]}"
    run_dir = os.path.join(out_dir, run_id)
    ledger = Ledger(run_dir, run_id, agent_id=agent_id, provider=provider, model=model)
    llm = {"anthropic": _Anthropic, "openai": _OpenAI, "modal": Kimi}.get(provider, None)
    llm = llm(model, ledger) if llm else _Scripted(ledger)
    system = system_prompt(task, env.solve_budget, env)
    history, error, result, t_best, status = [], None, env.evaluate(), 0, "max_turns"
    turns_f = open(os.path.join(run_dir, "turns.jsonl"), "w")
    consecutive_errors = 0
    no_tool = 0
    try:
        for turn in range(1, max_turns + 1):
            if env.solves_left <= 0:
                status = "budget_exhausted"
                break
            if max_usd is not None and ledger.unknown:
                status = "unknown_usage"
                break
            if max_usd is not None and ledger.usd >= max_usd:
                status = "spend_cap"
                break
            user = _state_text(env, result, turn, env.solve_budget, history, error, t_best)
            try:
                with timings.measure("model") if timings else nullcontext():
                    name, args = llm.call(system, user, env)
            except ToolResponseError as ex:
                status = ex.stop_reason
                turns_f.write(json.dumps({'turn': turn, 'action': 'model_response_error',
                    'error': ex.category, 'solves_used': env.solves_used}) + '\n')
                break
            except Exception as ex:  # noqa: BLE001
                consecutive_errors += 1
                status = f"api_error: {type(ex).__name__}"
                if consecutive_errors >= 3:
                    break
                time.sleep(5)
                continue
            consecutive_errors = 0
            if name == "noop":
                error = "You replied without calling a tool. Call submit_edits (or finish)."
                history.append(f"{turn}: no tool call")
                turns_f.write(json.dumps({"turn": turn, "action": "no_tool_call", "text": args.get("note")}) + "\n")
                no_tool += 1
                if no_tool >= 3:
                    status = "no_tool_call"
                    break
                continue
            no_tool = 0
            if name == "finish":
                status = "finished"
                turns_f.write(json.dumps({"turn": turn, "action": "finish", "note": args.get("note")}) + "\n")
                break
            error = None
            before = env.score()
            try:
                env.apply(args.get("edits", []))
            except EditError as ex:
                error = str(ex)
                history.append(f"{turn}: rejected edits ({error[:80]})")
                turns_f.write(json.dumps({"turn": turn, "action": "rejected", "error": error, "edits": args.get("edits")}) + "\n")
                continue
            with timings.measure("evaluation") if timings else nullcontext():
                result = env.evaluate()
                if result.get('unsolved_budget') and env.solves_left == 0:
                    turns_f.write(json.dumps(dict(turn=turn, action='budget_cleanup',
                        proposed_design=env.design, original_result=result,
                        solves_used=env.solves_used)) + '\n')
                    result = env.cleanup_unsolved()
            if env.score() is not None and (before is None or env.score() > before):
                t_best = turn
            history.append(f"{turn}: reward {result['reward']:.3f}, {'valid' if result['valid'] else 'INVALID'}, {env.solves_used} solves | {args.get('note', '')[:140]}")
            turns_f.write(json.dumps({"turn": turn, "action": "edit", "note": args.get("note"), "edits": args.get("edits"), "reward": result["reward"],
                                      "valid": result["valid"], "solves_used": env.solves_used, "usd_cum": ledger.usd}) + "\n")
            turns_f.flush()
    except BaseException as ex:
        status = f"failed: {type(ex).__name__}"
        turns_f.write(json.dumps({"turn": locals().get("turn", 0), "action": "failed",
            "error_type": type(ex).__name__, "edits": locals().get("args", {}).get("edits"),
            "design": env.design, "solves_used": env.solves_used}) + "\n")
        raise
    finally:
        turns_f.close()
        ledger.summary({"status": status, "turns": len(history), "best_valid_reward": env.score(),
            "solves_used": env.solves_used, "max_usd_cap": max_usd, "task": task["task_id"], "seed": seed})
    return ledger.summary({"status": status, "turns": len(history), "best_valid_reward": env.score(), "solves_used": env.solves_used, "max_usd_cap": max_usd,
                           "task": task["task_id"], "seed": seed})
