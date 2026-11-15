"""
Agent teams, version 2 (docs/SWARM_NEXT_ROUND.md). Replaces sepdesign/frameworks.py for new runs (that module is kept so earlier runs stay
reproducible). Differences from version 1:
  * FULL VIEW of other plants: a shared plant is shown with the same detail an agent sees for its own (every stream's composition, what each
    column separates, its cost, what sold and for how much), so copying is never needed just to see how a plant works. `info="settings"` gives the
    version-1 view (settings, reward, revenue, cost, note only) for experiments that vary the level of information.
  * NOTEBOOK: each agent keeps a private notebook it rewrites every turn and sees every round (longer-lived than the 12-turn history).
  * GRAFT: an agent can take one branch (a column and everything below it) from another plant into its own plant, instead of copying a whole plant.
  * REASONING: the model's reasoning text (when the provider returns it) is saved per request, next to the reply.
  * ANY MODAL MODEL: model endpoints are found by name in the workspace's /v1/models list; costs are logged with Modal's cached-input price.
  * ONE GENERAL CONFIGURATION instead of fixed codes: island sizes, how often and along which route islands exchange, information level, whether
    whole-plant copying and grafting are allowed, other-family rule, niche board, strategies, culling, supervisor.

Rounds are synchronous: each active agent makes one request per round (one edit list, then its plant is re-simulated). Every agent has its own solve
budget; the team's answer is the best valid plant any agent evaluated. A solve another agent already paid for is free on the machine (shared cache)
but is charged to the agent that asks for it the first time.
"""
import copy
import json
import math
import os
import random
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from sepdesign.report_archive import write_json
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from agents.kimi import ToolResponseError
from agents.llm_agent import FINISH_SCHEMA, _state_text, edit_schema, system_prompt
from sepdesign.env import EditError
from sepdesign.frameworks import STRATEGIES, column_label, jaccard, niche_of, record_line, structure_of
from sepdesign.ledger import PRICES, Ledger
from sepdesign.service import make_env

# Modal shared-endpoint prices, USD per million tokens: (input, cached input, output). https://modal.com/docs/guide/supported-models, 2026-11-15.
MODAL_PRICES = {
    "kimi-k3.1-pro": (2.00, 0.20, 10.00), "kimi-k3": (3.00, 0.30, 15.00), "glm-5.3": (1.40, 0.26, 4.40), "glm-5.3-flash": (0.45, 0.09, 1.50),
    "glm-5.3-flash-nvfp4": (0.15, 0.03, 0.50), "deepseek-v4.1-flash": (0.30, 0.03, 1.20), "deepseek-v4.1-flash-1017": (0.25, 0.005, 1.00),
    "qwen3.8-max": (2.00, 0.25, 6.00), "qwen3.8-max-vl": (2.00, 0.25, 6.00),
}
for _k, (_i, _c, _o) in MODAL_PRICES.items():          # uncached estimate for the shared Ledger; the cached-price figure is computed below
    PRICES.setdefault(_k, (_i, _o))
MAX_OUTPUT_TOKENS = 16384


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def real_cost(model, tin, tout, cached):
    pi, pc, po = MODAL_PRICES.get(model, (None, None, None))
    if pi is None or tin is None or tout is None:
        return None
    c = min(cached or 0, tin)
    return ((tin - c) * pi + c * pc + tout * po) / 1e6


# ---------------------------------------------------------------------------------------------------------------------- model client
class ModalClient:
    """One tool call per request to a Modal shared endpoint (OpenAI-compatible). The endpoint is looked up by model name in /v1/models.
    Network failures are retried (not charged); a reply that is not exactly one allowed tool call raises ToolResponseError."""
    # Modal shared endpoints accept 16 simultaneous requests per model (measured 2026-11-15); stay under it across all teams in this process.
    _sem = threading.Semaphore(int(os.environ.get("MODAL_MAX_CONCURRENT", "15")))
    _models = None
    _lock = threading.Lock()

    def __init__(self, ledger, model, reasoning_effort="low", think_budget=None):
        if os.name == "nt":
            import truststore
            self.ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            self.ctx = ssl.create_default_context()
        self.ledger, self.model, self.key = ledger, model, os.environ["MODAL_PROXY_TOKEN"]
        self.base = os.environ.get("KIMI_ENDPOINT_URL", "https://inference.us-west.modal.direct").rstrip("/")
        info = self._find(model)
        self.endpoint_id = info["id"]
        efforts = [v for o in (info.get("reasoning_options") or []) for v in o.get("values", [])]
        if efforts and reasoning_effort not in efforts:
            raise ValueError(f"model {model} offers reasoning efforts {efforts}, not {reasoning_effort!r}")
        self.effort = reasoning_effort if efforts else None
        if "tools" not in (info.get("supported_features") or []):
            raise ValueError(f"model {model} does not support tool calls on this endpoint")
        self.real_usd = 0.0
        self.last_reasoning = None
        self.last_effort = None
        self.think_budget = think_budget

    def _post(self, body):
        response, last, failures, busy = None, None, 0, 0
        while failures < 4 and busy < 120:
            req = urllib.request.Request(self.base + "/v1/chat/completions", data=json.dumps(body).encode(), headers={
                "Authorization": "Bearer " + self.key, "Content-Type": "application/json",
                "Modal-Routing-Affinity-Key": self.ledger.run_id + "-" + self.ledger.agent_id})
            try:
                with self._sem:
                    with urllib.request.urlopen(req, timeout=600, context=self.ctx) as r:
                        return json.load(r)
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code == 429:
                    busy += 1
                    time.sleep(5 + random.random() * 10)
                    continue
                failures += 1
                self.ledger.record(None, None, None, ok=False, error=f"http {exc.code}", note=f"attempt {failures}, not charged")
                time.sleep(10 * 2 ** failures + random.random() * 5)
            except Exception as exc:  # noqa: BLE001
                last = exc
                failures += 1
                self.ledger.record(None, None, None, ok=False, error="network: " + type(exc).__name__, note=f"attempt {failures}, not charged")
                time.sleep(10 * 2 ** failures + random.random() * 5)
        raise RuntimeError("Modal request failed: " + type(last).__name__)

    def _account(self, response, ok, error, note=""):
        usage = response.get("usage") or {}
        tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        rc = real_cost(self.model, tin, tout, cached)
        self.real_usd += rc or 0.0
        self.ledger.record(response.get("id"), tin, tout, cached=cached, reasoning=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                           ok=ok, error=error, note=(note + (f" cached-price estimate ${rc:.6f}" if rc is not None else "")).strip())

    def _budgeted(self, system, user, tools):
        """Think step: low effort, hard-stopped at think_budget tokens. If it already called a tool, use that; otherwise an act step with no thinking
        is given the thinking so far and must call a tool. The thinking budget is enforced by us, not left to the model."""
        mk = lambda u, eff, cap, choice: dict(model=self.endpoint_id, messages=[{"role": "system", "content": system}, {"role": "user", "content": u}],  # noqa: E731
                                             tools=[{"type": "function", "function": dict(name=n, description=d, parameters=s_)} for n, d, s_ in tools],
                                             tool_choice=choice, max_tokens=cap, reasoning_effort=eff)
        r1 = self._post(mk(user, self.effort or "low", self.think_budget, "auto"))
        m1 = (r1.get("choices") or [{}])[0].get("message") or {}
        think = m1.get("reasoning_content") or m1.get("reasoning") or ""
        self.last_reasoning = think
        calls = m1.get("tool_calls") or []
        if calls and (r1["choices"][0].get("finish_reason") != "length"):
            self._account(r1, True, None, "think step (acted directly)")
            return self._parse(r1, tools)
        self._account(r1, True, None, "think step")
        u2 = user + "\n\nYOUR THINKING SO FAR (stopped at your thinking budget):\n" + think[-12000:] + "\n\nNow act on it: call submit_edits (or finish)."
        r2 = self._post(mk(u2, "none", 4000, "required"))
        return self._parse(r2, tools, account=True, note="act step")

    def _parse(self, response, tools, account=False, note=""):
        allowed = {n for n, _, _ in tools}
        failure, parsed = None, None
        try:
            choice = response["choices"][0]
            msg = choice["message"]
            if choice.get("finish_reason") == "length":
                raise ToolResponseError("output_limit")
            calls = msg.get("tool_calls") or []
            if len(calls) != 1:
                raise ToolResponseError("missing_tool" if not calls else "multiple_tools")
            fn = calls[0]["function"]
            if fn["name"] not in allowed:
                raise ToolResponseError("unknown_tool")
            args = json.loads(fn["arguments"])
            if not isinstance(args, dict):
                raise ToolResponseError("invalid_tool_arguments")
            if fn["name"] == "submit_edits" and (not isinstance(args.get("edits", []), list) or not all(isinstance(e, dict) for e in args.get("edits", []))):
                raise ToolResponseError("invalid_edits")
            parsed = (fn["name"], args)
        except ToolResponseError as exc:
            failure = exc
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            failure = ToolResponseError("malformed_response")
        if account:
            self._account(response, failure is None, failure.category if failure else None, note)
        if failure:
            raise failure
        return parsed

    def _find(self, model):
        with ModalClient._lock:
            if ModalClient._models is None:
                req = urllib.request.Request(self.base + "/v1/models", headers={"Authorization": "Bearer " + self.key})
                with urllib.request.urlopen(req, timeout=60, context=self.ctx) as r:
                    ModalClient._models = json.load(r).get("data", [])
        want = _norm(model)
        exact = [m for m in ModalClient._models if _norm((m.get("base_model_id") or "").split("/")[-1]) == want]
        if exact:
            return exact[0]
        raise ValueError(f"no Modal endpoint for {model!r}; endpoints in this workspace: "
                         + ", ".join(m.get("base_model_id", "?") for m in ModalClient._models) + ". Create a shared endpoint for it in the Modal dashboard.")

    def call(self, system, user, tools, effort=None):
        """effort: override this request's reasoning effort (e.g. 'none' on a cheap turn)."""
        body = dict(model=self.endpoint_id, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    tools=[{"type": "function", "function": dict(name=n, description=d, parameters=s)} for n, d, s in tools],
                    tool_choice="auto", max_tokens=MAX_OUTPUT_TOKENS)
        if self.think_budget and effort is None:
            self.last_effort = f"{self.effort} capped at {self.think_budget} tokens"
            return self._budgeted(system, user, tools)
        use = effort or self.effort
        if use:
            body["reasoning_effort"] = use
        self.last_effort = use
        response, last, failures, busy = None, None, 0, 0
        while failures < 4 and busy < 120:
            req = urllib.request.Request(self.base + "/v1/chat/completions", data=json.dumps(body).encode(), headers={
                "Authorization": "Bearer " + self.key, "Content-Type": "application/json",
                "Modal-Routing-Affinity-Key": self.ledger.run_id + "-" + self.ledger.agent_id})
            try:
                with self._sem:
                    with urllib.request.urlopen(req, timeout=600, context=self.ctx) as r:
                        response = json.load(r)
                break
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code == 429:                      # over the endpoint's concurrency limit: wait and retry, not a failure (not charged)
                    busy += 1
                    time.sleep(5 + random.random() * 10)
                    continue
                failures += 1
                self.ledger.record(None, None, None, ok=False, error=f"http {exc.code}", note=f"attempt {failures}, not charged")
                time.sleep(10 * 2 ** failures + random.random() * 5)
            except Exception as exc:  # noqa: BLE001
                last = exc
                failures += 1
                self.ledger.record(None, None, None, ok=False, error="network: " + type(exc).__name__, note=f"attempt {failures}, not charged")
                time.sleep(10 * 2 ** failures + random.random() * 5)
        if response is None:
            raise RuntimeError("Modal request failed 4 times: " + type(last).__name__)
        usage = response.get("usage") or {}
        tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        rc = real_cost(self.model, tin, tout, cached)
        self.real_usd += rc or 0.0
        allowed = {n for n, _, _ in tools}
        failure, parsed = None, None
        self.last_reasoning = None
        try:
            choice = response["choices"][0]
            msg = choice["message"]
            self.last_reasoning = msg.get("reasoning_content") or msg.get("reasoning")
            if choice.get("finish_reason") == "length":
                raise ToolResponseError("output_limit")
            calls = msg.get("tool_calls") or []
            if len(calls) != 1:
                raise ToolResponseError("missing_tool" if not calls else "multiple_tools")
            fn = calls[0]["function"]
            if fn["name"] not in allowed:
                raise ToolResponseError("unknown_tool")
            args = json.loads(fn["arguments"])
            if not isinstance(args, dict):
                raise ToolResponseError("invalid_tool_arguments")
            if fn["name"] in ("submit_edits",) and (not isinstance(args.get("edits", []), list) or not all(isinstance(e, dict) for e in args.get("edits", []))):
                raise ToolResponseError("invalid_edits")
            parsed = (fn["name"], args)
        except ToolResponseError as exc:
            failure = exc
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            failure = ToolResponseError("malformed_response")
        self.ledger.record(response.get("id"), tin, tout, cached=cached, reasoning=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                           ok=failure is None, error=failure.category if failure else None,
                           note=f"cached-price estimate ${rc:.6f}" if rc is not None else "")
        if failure:
            raise failure
        return parsed


class AnthropicClient:
    """Claude models through the Anthropic API (for reference runs in the same harness). No hidden thinking; cost = Ledger estimate."""

    def __init__(self, ledger, model):
        import anthropic
        self.c, self.model, self.ledger = anthropic.Anthropic(max_retries=4, timeout=300), model, ledger
        self.real_usd, self.last_reasoning, self.last_effort = 0.0, None, None

    def call(self, system, user, tools, effort=None):
        r = self.c.messages.create(model=self.model, max_tokens=16000, system=system, messages=[{"role": "user", "content": user}],
                                   tools=[{"name": n, "description": d, "input_schema": s_} for n, d, s_ in tools])
        u = r.usage
        before = self.ledger.usd
        uses = [b for b in r.content if b.type == "tool_use"]
        text = " ".join(b.text for b in r.content if b.type == "text")
        self.last_reasoning = text or None
        ok = len(uses) == 1
        self.ledger.record(r.id, u.input_tokens, u.output_tokens, cached=getattr(u, "cache_read_input_tokens", None), ok=ok,
                           error=None if ok else ("missing_tool" if not uses else "multiple_tools"))
        self.real_usd += self.ledger.usd - before
        if not ok:
            raise ToolResponseError("missing_tool" if not uses else "multiple_tools")
        return uses[0].name, dict(uses[0].input)


class ScriptedClient:
    """No API, for plumbing tests on the mock backend."""

    def __init__(self, ledger, env=None):
        self.ledger, self.env, self.real_usd, self.last_reasoning, self.last_effort = ledger, env, 0.0, "scripted reasoning", None

    def call(self, system, user, tools, effort=None):
        self.last_effort = effort
        from sepdesign import baselines
        self.ledger.record("scripted", 0, 0, usd_billed=0.0, note="scripted")
        names = [n for n, _, _ in tools]
        if "manage" in names:
            m = re.search(r"record (R\d+)", user)
            return "manage", {"actions": [{"type": "branch", "stop_worker": "agent-9", "from_record": m.group(1), "strategy": "scripted"},
                                          {"type": "reassign", "stop_worker": "agent-8", "give_to": "agent-1"}] if m else []}
        env = self.env
        todo = [""] if env.last is None else baselines._off_spec_leaves(env, env.last)
        if not todo or len(env.design) >= env.max_columns:
            return "finish", {"note": "scripted: nothing left"}
        args = {"note": "scripted", "notebook": f"scripted notebook after {len(env.design)} columns",
                "edits": [{"op": "set", "node": todo[0], "n_stages": 53, "reflux_ratio": 3.56, "reboil_ratio": 3.56, "pressure_drop_fraction": 0.04}]}
        m = re.search(r"\[(R\d+)\] by", user)
        sch = json.dumps([s for _, _, s in tools])
        if m and '"graft"' in sch and random.random() < 0.3:
            args = {"note": "scripted graft", "graft": {"from_record": m.group(1), "from_path": "", "to_path": todo[0]}, "edits": [], "notebook": "graft"}
        elif m and '"copy_from"' in sch and random.random() < 0.2:
            args = {"note": "scripted copy", "copy_from": m.group(1), "edits": [], "notebook": "copied"}
        return "submit_edits", args


# ---------------------------------------------------------------------------------------------------------------------- configuration
DEFAULT = dict(n=10, budget=100, min_finish=None, unsold_info=False, effort="low", think_budget=None, plan=False, think_every=None, think_when_stuck=None, cheap_effort="none", islands=None, share_within=True, migrate_every=None, route="ring", info="full", copy=True, graft=True,
               copy_rule=None, niche_board=False, strategies=None, notebook=True, cull_every=None, supervisor_every=None, max_shown=4)
PRESETS = {
    # controls
    "solo":          dict(n=1, budget=500, islands=[1], share_within=False),
    "independent":   dict(islands=[1] * 10, share_within=False),
    "open":          dict(islands=[10]),                                       # everyone sees everyone every round (full view)
    # island sweep (full view, copying and grafting allowed)
    "ring-5x2-k5":   dict(islands=[2] * 5, migrate_every=5),
    "ring-5x2-k10":  dict(islands=[2] * 5, migrate_every=10),
    "ring-5x2-k20":  dict(islands=[2] * 5, migrate_every=20),
    "ring-10x1-k10": dict(islands=[1] * 10, migrate_every=10),
    "ring-3isl-k10": dict(islands=[3, 3, 4], migrate_every=10),
    "all-5x2-k10":   dict(islands=[2] * 5, migrate_every=10, route="all"),
    # how ideas move
    "open-nocopy":   dict(islands=[10], copy=False),                          # see everything, borrow by grafting or writing columns
    "open-inspire":  dict(islands=[10], copy=False, graft=False),             # see everything, must write every edit itself
    "open-settings": dict(islands=[10], info="settings"),                     # version-1 view, for comparison only
    # diversity mechanisms
    "other-family":  dict(islands=[10], copy_rule="other_family"),
    "niche":         dict(islands=[10], niche_board=True),
    "strategies":    dict(islands=[2] * 5, strategies="per_island"),
    "cull":          dict(islands=[1] * 10, share_within=False, cull_every=10),
    "managed":       dict(n=10, islands=[1] * 9, share_within=False, supervisor_every=10),
}


def parse_islands(spec):
    """'3x10' = 10 islands of 3 agents; '30' = one island of 30; '4,4,4' = explicit sizes."""
    if "x" in spec:
        size, count = spec.split("x")
        return [int(size)] * int(count)
    return [int(x) for x in spec.split(",")]


def finish_fraction(value):
    """Validate the minimum budget fraction before a run starts."""
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("min_finish must be a finite fraction between 0 and 1")
    return value


def config(preset, agents=None, islands=None, **over):
    """Preset plus overrides. agents rescales the team (independent, open, cull and similar presets scale directly; island presets need islands)."""
    c = dict(DEFAULT)
    c.update(PRESETS[preset])
    c.update({k: v for k, v in over.items() if v is not None})
    if c.get("min_finish") is not None:
        c["min_finish"] = finish_fraction(c["min_finish"])
    if islands:
        c["islands"] = parse_islands(islands)
        c["n"] = sum(c["islands"]) + (1 if c.get("supervisor_every") else 0)
    elif agents and preset != "solo":
        base = PRESETS[preset].get("islands") or [10]
        if all(x == 1 for x in base):
            c["islands"] = [1] * (agents - (1 if c.get("supervisor_every") else 0))
        elif len(base) == 1:
            c["islands"] = [agents]
        else:
            raise ValueError(f"preset {preset} has islands {base}: give --islands for a team of {agents}")
        c["n"] = agents
    c["preset"] = preset
    return c


# ---------------------------------------------------------------------------------------------------------------------- board
class Board:
    def __init__(self, path=None):
        self.records, self.lock = [], threading.Lock()
        self.path = path

    def add(self, **r):
        with self.lock:
            r["id"] = f"R{len(self.records) + 1}"
            self.records.append(r)
            if self.path:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(r, default=str) + "\n")
                    f.flush()
            return r["id"]

    def get(self, rid):
        return next((r for r in self.records if r["id"] == rid), None)

    def best(self, where=lambda r: True, k=1):
        rs = sorted((r for r in self.records if r["valid"] and r["reward"] > 0 and where(r)), key=lambda r: -r["reward"])
        out, seen = [], set()
        for r in rs:
            key = json.dumps(r["design"], sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                out.append(r)
            if len(out) >= k:
                break
        return out


def show(r, info):
    head = (f"[{r['id']}] by {r['agent']} (island {r['island']}, family {r['family']}, round {r['round']}): reward {r['reward']:.3f}"
            f"{'' if r['valid'] else ' INVALID'} | their note: {r['note'][:200]}")
    sett = "  settings (path: stages/reflux/boil-up/pressure-drop): " + design_text(r["design"])
    if info == "full":
        return head + "\n" + sett + "\n  what it does (same view as your own plant):\n" + "\n".join("    " + l for l in r["view"].splitlines())
    return head + "\n" + sett + f"\n  revenue ${r['revenue'] / 1e6:.0f}M/yr, cost ${r['tac'] / 1e6:.0f}M/yr, {r['columns']} columns"


def design_text(design):
    def one(p, s):
        t = f"'{p}': {s[0]}/{s[1]}/{s[2]}/{s[3]}"
        if len(s) > 4 and s[4] is not None:
            t += f" side {s[4][1]} stage {s[4][0]} fraction {s[4][2]}"
        if len(s) > 5:
            t += f" double effect {s[5][0]} to HP, LP dp {s[5][1]}"
        return t
    return "; ".join(one(p, s) for p, s in sorted(design.items(), key=lambda kv: (len(kv[0]), kv[0]))) or "(no columns)"


# ---------------------------------------------------------------------------------------------------------------------- agents
class Agent:
    def __init__(self, aid, env, client, island):
        self.id, self.env, self.client, self.island = aid, env, client, island
        self.history, self.error, self.t_best, self.status, self.errors_in_row = [], None, 0, "active", 0
        self.result, self.first_positive, self.strategy, self.notebook = None, None, None, ""
        self.turns = []


def run_team(cfg, task, service, out_dir, model="kimi-k3.1-pro", provider="modal", seed=0, max_rounds=250, log=print):
    min_finish = finish_fraction(cfg["min_finish"]) if cfg.get("min_finish") is not None else 0
    rnd = random.Random(seed)
    if os.path.exists(os.path.join(out_dir, "config.json")):
        raise FileExistsError("Run destination already contains evidence: " + str(out_dir))
    os.makedirs(out_dir, exist_ok=True)
    run_id = f"{task['task_id']}-{cfg['preset']}-{uuid.uuid4().hex[:8]}"
    names = task["components"]
    sup_mode = cfg["supervisor_every"] is not None
    islands = list(cfg["islands"] or [cfg["n"]])
    n_workers = sum(islands)
    budgets = [cfg["budget"]] * n_workers if cfg["n"] > 1 else [cfg["budget"]]
    island_of = [i for i, size in enumerate(islands) for _ in range(size)]
    strat = {}
    if cfg["strategies"] == "per_island":
        picks = rnd.sample(STRATEGIES, len(islands))
        strat = {w: picks[island_of[w]] for w in range(n_workers)}

    def client_for(ledger, env):
        if provider == "anthropic":
            return AnthropicClient(ledger, model)
        return (ModalClient(ledger, model, reasoning_effort=cfg.get("effort", "low"), think_budget=cfg.get("think_budget"))
                if provider == "modal" else ScriptedClient(ledger, env))
    workers = []
    for w in range(n_workers):
        aid = f"agent-{w}"
        env = make_env(task, service, budget=budgets[w])
        led = Ledger(os.path.join(out_dir, "agents", aid), run_id, agent_id=aid, provider=provider, model=model)
        a = Agent(aid, env, client_for(led, env), island_of[w])
        a.strategy = strat.get(w)
        workers.append(a)
    sup = None
    if sup_mode:
        led = Ledger(os.path.join(out_dir, "agents", "supervisor"), run_id, agent_id="supervisor", provider=provider, model=model)
        sup = Agent("supervisor", workers[0].env, client_for(led, workers[0].env), None)
    everyone = workers + ([sup] if sup else [])
    family = {a.id: a.id for a in workers}
    board = Board(os.path.join(out_dir, "board.jsonl"))
    team_curve = []
    events = open(os.path.join(out_dir, "events.jsonl"), "w")
    t0 = time.time()
    json.dump(dict(run_id=run_id, config=cfg, task=task["task_id"], model=model, provider=provider, seed=seed, islands=islands,
                   budgets={a.id: a.env.solve_budget for a in workers}, strategies={a.id: a.strategy for a in workers if a.strategy},
                   started=time.strftime("%Y-%m-%d %H:%M:%S"), simulator_retries="ChemSep alternative initialisations on"),
              open(os.path.join(out_dir, "config.json"), "w"), indent=1)

    def ev(**e):
        e["t"] = round(time.time() - t0, 2)
        events.write(json.dumps(e, default=str) + "\n")
        events.flush()

    def team_best():
        b = [a.env.score() for a in workers if a.env.score() is not None]
        return max(b) if b else 0.0

    def team_solves():
        return sum(a.env.solves_used for a in workers)

    def usd():
        return sum(a.client.ledger.usd for a in everyone), sum(a.client.real_usd for a in everyone)

    for a in workers:
        a.result = a.env.evaluate()

    # ------------------------------------------------------------ what each agent may see
    def visible(a, rnd_no):
        """Records shown to agent a this round (at most cfg['max_shown']), most useful first."""
        out = []
        if cfg["niche_board"]:
            elites = {}
            for r in board.records:
                if r["valid"] and r["reward"] > 0 and (r["niche"] not in elites or r["reward"] > elites[r["niche"]]["reward"]):
                    elites[r["niche"]] = r
            mine = niche_of(a.result, names, len(a.env.design)) if a.result else None
            return sorted((r for k, r in elites.items() if k != mine), key=lambda r: -r["reward"])[: cfg["max_shown"]]
        if cfg["share_within"]:
            mates = lambda r: r["island"] == a.island and r["agent"] != a.id  # noqa: E731
            if cfg["copy_rule"] == "other_family":
                mates = lambda r: r["island"] == a.island and r["family"] != family[a.id]  # noqa: E731
            out += board.best(mates, k=2)
            latest = [r for r in reversed(board.records) if mates(r) and r not in out][:2]
            out += latest
        if cfg["migrate_every"] and rnd_no % cfg["migrate_every"] == 0:
            if cfg["route"] == "ring":
                src = [(a.island + 1) % len(islands)]
            else:
                src = [i for i in range(len(islands)) if i != a.island]
            for i in src:
                out = board.best(lambda r, i=i: r["island"] == i, k=1) + out
        if cfg["copy_rule"] == "other_family" and out:
            cur = structure_of(a.result, names) if a.result else []
            pool = [r for r in board.best(lambda r: r["family"] != family[a.id], k=12)]
            if pool:
                far = max(pool, key=lambda r: jaccard(cur, r.get("structure", [])))
                if far not in out:
                    out.insert(0, far)
        seen, uniq = set(), []
        for r in out:
            if r["id"] not in seen:
                seen.add(r["id"])
                uniq.append(r)
        return uniq[: cfg["max_shown"]]

    def intro(a):
        if cfg["n"] == 1:
            return ""
        s = (f"\n\nTEAM: you are {a.id}, one of {n_workers} agents designing plants for the same feed. The team's score is the best valid plant any member "
             f"evaluates. Your own solve budget is {a.env.solve_budget}. ")
        if len(islands) > 1 or not cfg["share_within"]:
            s += f"You are on island {a.island} ({islands[a.island]} agent{'s' if islands[a.island] > 1 else ''}). "
        if cfg["share_within"] and islands[a.island] > 1:
            s += "Every turn you see good plants from your island in full detail (the same view you have of your own plant). "
        if cfg["migrate_every"]:
            s += (f"Every {cfg['migrate_every']} rounds you also see the best plant of "
                  + ("the next island" if cfg["route"] == "ring" else "every other island") + " in full detail. ")
        if cfg["niche_board"]:
            s += "Every turn you see the team's best plants of other kinds (niche: the first column's cut and the plant's size) in full detail. "
        if cfg["copy_rule"] == "other_family":
            s += ("A family is the line of plants descended from one agent's work. You see plants from other families, including the one most different "
                  "from yours, and may copy or graft only from other families. ")
        if not cfg["share_within"] and not cfg["migrate_every"] and not cfg["niche_board"]:
            s += "You work alone and do not see teammates' plants. "
        uses = []
        if cfg["copy"]:
            uses.append("copy a shown plant (copy_from)")
        if cfg["graft"]:
            uses.append("graft one branch of a shown plant into yours (graft)")
        uses.append("use what you learn from it in your own edits")
        if any([cfg["share_within"], cfg["migrate_every"], cfg["niche_board"]]):
            s += "From a shown plant you may " + ", ".join(uses) + ". Think about WHY a plant or a column works before reusing it. "
        if cfg["cull_every"]:
            s += f"Every {cfg['cull_every']} rounds the weaker half of the team (by best valid reward) is stopped and its unused solves go to the stronger half. "
        if sup_mode:
            s += (f"Every {cfg['supervisor_every']} rounds a supervisor reviews the team and may stop workers that make little progress, give their solves to "
                  "others, or restart a worker from another plant with a new strategy. ")
        if a.strategy:
            s += f"\nYOUR STRATEGY: {a.strategy}"
        return s

    def unsold_text(a):
        """For each unsold stream of the agent's plant: how close it is to a sellable spec, and what it would earn if it met it."""
        if not cfg["unsold_info"] or a.result is None:
            return ""
        e = a.env.econ
        rows = []
        for p, nd in a.result["nodes"].items():
            if nd.get("status") != "sold" or nd.get("value", 0) > 0:
                continue
            fl = np.asarray(nd["feed"], float)
            tot = fl.sum()
            if tot <= 0 or e.negligible(fl):
                continue
            i = int(np.argmax(fl))
            opts = [(fl[i] / tot, e.purity, f"pure {names[i]}", fl[i] * e.prices[i] * e.seconds)]
            for gname, idx, minf, price in e.groups:
                f = fl[idx].sum()
                opts.append((f / tot, minf, gname, f * price * e.seconds))
            opts.sort(key=lambda o: -(o[3] if o[0] >= o[1] - 0.25 else 0))
            share, need, label, val = opts[0]
            rows.append(f"[{p or 'feed'}] {tot:.0f} mol/s: {label} is {100 * share:.0f}% (needs {100 * need:.0f}%); worth about ${val / 1e6:.0f}M/yr if it met that")
        return ("\n\nUNSOLD STREAMS IN YOUR PLANT (worth 0 now), closest sellable product and its value if it met spec:\n" + "\n".join(rows)) if rows else ""

    def notebook_text(a):
        if not cfg["notebook"]:
            return ""
        return ("\n\nYOUR NOTES (kept between turns and saved in the run's logs; rewrite them in full in every reply, at most about 1,500 characters. Start it with a line "
                "'PLAN:' giving the multi-step plan you are carrying out and which step you are on; keep that plan from turn to turn unless results show "
                "it is wrong. Then: what you have learned from your own results and from other plants, and why):\n" + (a.notebook or "(empty)"))

    def tools_for(a):
        sch = copy.deepcopy(edit_schema(a.env))
        sch["properties"].pop("evidence_ids", None)
        sch["properties"].pop("source_design", None)
        sharing = any([cfg["share_within"], cfg["migrate_every"], cfg["niche_board"]])
        if sharing and cfg["copy"]:
            sch["properties"]["copy_from"] = {"type": "string", "description": "Optional: a shown record id (e.g. 'R12'); that whole plant replaces yours before your edits."}
        if sharing and cfg["graft"]:
            sch["properties"]["graft"] = {"type": "object", "description": "Optional: take the column at from_path of a shown record, with every column below it, and put it at to_path in your plant (replacing what is there) before your edits.",
                                          "properties": {"from_record": {"type": "string"}, "from_path": {"type": "string"}, "to_path": {"type": "string"}},
                                          "required": ["from_record", "from_path", "to_path"]}
        if cfg["plan"]:
            sch["properties"] = {"plan": {"type": "string", "description": "Before your edits, in at most about 150 words: (1) what limits your plant now, "
                                          "(2) the multi-step plan you are working toward and why it should pay, (3) what this turn's edits test."},
                                 **sch["properties"]}
            sch["required"] = list(dict.fromkeys(["plan"] + list(sch.get("required", []))))
        if cfg["notebook"]:
            sch["properties"]["notebook"] = {"type": "string", "description": "Your full updated notebook (replaces the previous one)."}
            sch.setdefault("required", [])
            if "notebook" not in sch["required"]:
                sch["required"] = list(sch["required"]) + ["notebook"]
        return [("submit_edits", "Edit your plant (optionally copying or grafting from a shown plant first), then re-simulate.", sch),
                ("finish", "Stop: nothing more worth trying.", FINISH_SCHEMA)]

    def save_prompt(who, rnd_no, system, user):
        d = os.path.join(out_dir, "agents", who)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "prompts.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"round": rnd_no, "system_chars": len(system), "user_chars": len(user), "system": system if rnd_no == 1 else None, "user": user}) + "\n")

    shown_ids = {}

    def ask(a, rnd_no):
        system = system_prompt(task, a.env.solve_budget, a.env) + intro(a)
        vis = visible(a, rnd_no)
        shown_ids[a.id] = [r["id"] for r in vis]
        user = _state_text(a.env, a.result, rnd_no, a.env.solve_budget, a.history, a.error, a.t_best) + unsold_text(a) + notebook_text(a)
        if vis:
            user += "\n\nOTHER PLANTS YOU CAN SEE THIS TURN:\n" + "\n\n".join(show(r, cfg["info"]) for r in vis)
        save_prompt(a.id, rnd_no, system, user)
        effort = None
        if cfg["think_every"] or cfg["think_when_stuck"]:
            stuck = cfg["think_when_stuck"] and rnd_no - max(a.t_best, 1) >= cfg["think_when_stuck"]
            sched = cfg["think_every"] and (rnd_no - 1) % cfg["think_every"] == 0
            effort = cfg["effort"] if (sched or stuck) else cfg["cheap_effort"]
        return a.client.call(system, user, tools_for(a), effort=effort)

    # ------------------------------------------------------------ culling and supervisor
    def cull(rnd_no):
        live = [w for w in workers if w.status == "active" and w.env.solves_left > 0]
        if len(live) <= 2:
            return
        live.sort(key=lambda w: -(w.env.score() if w.env.score() is not None else -1e9))
        keep, stop = live[: (len(live) + 1) // 2], live[(len(live) + 1) // 2:]
        pool_ = sum(w.env.solves_left for w in stop)
        for w in stop:
            w.env.solve_budget, w.status = w.env.solves_used, "culled"
        for k, w in enumerate(keep):
            extra = pool_ // len(keep) + (1 if k < pool_ % len(keep) else 0)
            w.env.solve_budget += extra
            w.history.append(f"{rnd_no}: you survived the cut and received {extra} more solves")
        ev(kind="cull", round=rnd_no, stopped=[w.id for w in stop], kept=[w.id for w in keep], solves_moved=pool_)

    manage_tools = [("manage", "Decide what to do with the workers after this review.", {"type": "object", "properties": {
        "actions": {"type": "array", "items": {"type": "object", "properties": {
            "type": {"type": "string", "enum": ["reassign", "branch"]}, "stop_worker": {"type": "string"},
            "give_to": {"type": "string"}, "from_record": {"type": "string"}, "strategy": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["type", "stop_worker"]}}, "note": {"type": "string"}}, "required": ["actions"]})]

    def manage(rnd_no):
        live = [w for w in workers if w.status == "active" and w.env.solves_left > 0]
        rows = []
        for w in workers:
            b = w.env.best[2] if w.env.best else None
            rows.append(f"{w.id}: status {w.status}, best reward {w.env.score() if w.env.score() is not None else 'none'}, solves {w.env.solves_used}/"
                        f"{w.env.solve_budget}, best plant structure {structure_of(b, names) if b else '-'}" + (f", strategy: {w.strategy}" if w.strategy else "")
                        + (f"\n    notebook: {w.notebook[:400]}" if w.notebook else ""))
        best = board.best(k=4)
        user = (f"Review at round {rnd_no}. Team best {team_best():.3f}; team solves {team_solves()}.\n\nWORKERS:\n" + "\n".join(rows)
                + ("\n\nBEST PLANTS:\n" + "\n\n".join(show(r, cfg["info"]) for r in best) if best else "")
                + "\n\nYou may stop up to 3 active workers. For each, either REASSIGN its unused solves to another active worker, or BRANCH: restart it (same "
                  "remaining solves) from an existing plant (from_record) with a new strategy that differs from what the team is already doing. An empty "
                  "action list changes nothing.")
        system = (system_prompt(task, sum(budgets), workers[0].env) + "\n\nYour role: SUPERVISOR of a portfolio of worker agents. You use no solves. Keep "
                  "the portfolio diverse and put solves where they are most likely to improve the team's best plant.")
        save_prompt("supervisor", rnd_no, system, user)
        _, args = sup.client.call(system, user, manage_tools)
        save_reasoning(sup, rnd_no)
        done = []
        for act in (args.get("actions") or [])[:3]:
            if not isinstance(act, dict):
                continue
            w = next((x for x in live if x.id == act.get("stop_worker") and x.status == "active" and x.env.solves_left > 0), None)
            if w is None:
                done.append({"action": act, "applied": False, "why": "not an active worker"})
                continue
            if act.get("type") == "reassign":
                g = next((x for x in live if x.id == act.get("give_to") and x is not w and x.status == "active" and x.env.solves_left > 0), None)
                if g is None:
                    done.append({"action": act, "applied": False, "why": "give_to is not another active worker"})
                    continue
                left = w.env.solves_left
                w.env.solve_budget, w.status = w.env.solves_used, "stopped"
                g.env.solve_budget += left
                g.history.append(f"{rnd_no}: the supervisor gave you {left} more solves")
                done.append({"action": act, "applied": True, "solves_moved": left})
            elif act.get("type") == "branch":
                rec = board.get(str(act.get("from_record")))
                if rec is None:
                    done.append({"action": act, "applied": False, "why": "unknown record"})
                    continue
                w.env.design = copy.deepcopy(rec["design"])
                w.result = w.env.evaluate()
                w.strategy = str(act.get("strategy") or "Explore a different direction from this plant.")[:400]
                w.history = [f"{rnd_no}: restarted by the supervisor from {rec['id']} (reward {rec['reward']:.3f}) with a new strategy"]
                w.error, w.t_best, w.notebook = None, rnd_no, ""
                family[w.id] = rec["family"]
                done.append({"action": act, "applied": True})
        ev(kind="portfolio", round=rnd_no, actions=done, note=args.get("note"))

    def save_reasoning(a, rnd_no, reply=None):
        d = os.path.join(out_dir, "agents", a.id)
        with open(os.path.join(d, "reasoning.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"round": rnd_no, "effort": getattr(a.client, "last_effort", None), "reasoning": a.client.last_reasoning,
                                "reply": reply}, default=str) + "\n")

    # ------------------------------------------------------------ main loop
    status = "round_limit"
    if cfg["n"] == 1:
        max_rounds = max(max_rounds, 2 * cfg["budget"])
    try:
        with ThreadPoolExecutor(max_workers=max(4, n_workers)) as pool:
            for rnd_no in range(1, max_rounds + 1):
                for a in workers:
                    if a.status == "active" and a.env.solves_left <= 0:
                        a.status = "budget_exhausted"
                active = [a for a in workers if a.status == "active"]
                if not active:
                    status = "all_done"
                    break
                futs = {pool.submit(ask, a, rnd_no): a for a in active}
                proposals = {}
                for f, a in futs.items():
                    try:
                        proposals[a.id] = f.result()
                        a.errors_in_row = 0
                    except (ToolResponseError, RuntimeError) as exc:
                        a.errors_in_row += 1
                        a.error = "Your last reply could not be used (" + str(getattr(exc, "category", exc)) + "). Call submit_edits or finish."
                        ev(kind="model_error", round=rnd_no, agent=a.id, error=str(getattr(exc, "category", exc)))
                        if a.errors_in_row >= 3:
                            a.status = "model_errors"
                    save_reasoning(a, rnd_no, proposals.get(a.id))
                for a in active:
                    if a.id not in proposals:
                        continue
                    name, args = proposals[a.id]
                    if cfg["notebook"] and isinstance(args.get("notebook"), str) and args["notebook"].strip():
                        a.notebook = args["notebook"][:2500]
                    need = math.ceil(min_finish * a.env.solve_budget)
                    if name == "finish" and a.env.solves_used < need:
                        a.error = (f"Finishing is not allowed yet: you have used {a.env.solves_used} of {a.env.solve_budget} solves; keep improving the plant "
                                   f"until you have used at least {need}.")
                        ev(kind="finish_refused", round=rnd_no, agent=a.id, note=args.get("note"))
                        continue
                    if name == "finish":
                        a.status = "finished"
                        ev(kind="finish", round=rnd_no, agent=a.id, note=args.get("note"))
                        continue
                    before_design, before_best = copy.deepcopy(a.env.design), a.env.score()
                    copied, graft = args.get("copy_from"), args.get("graft")
                    allowed = set(shown_ids.get(a.id, []))
                    try:
                        if copied:
                            if not cfg["copy"]:
                                raise EditError("copying whole plants is not allowed in this team")
                            rec = board.get(str(copied))
                            if rec is None or rec["id"] not in allowed:
                                raise EditError(f"record {copied!r} was not shown to you this turn")
                            a.env.design = copy.deepcopy(rec["design"])
                            family[a.id] = rec["family"]
                        if graft:
                            if not cfg["graft"]:
                                raise EditError("grafting is not allowed in this team")
                            rec = board.get(str(graft.get("from_record")))
                            if rec is None or rec["id"] not in allowed:
                                raise EditError(f"record {graft.get('from_record')!r} was not shown to you this turn")
                            fp, tp = str(graft.get("from_path", "")), str(graft.get("to_path", ""))
                            if fp not in rec["design"]:
                                raise EditError(f"record {rec['id']} has no column at {fp!r}")
                            if tp and tp[:-1] not in a.env.design:
                                raise EditError(f"cannot graft to {tp!r}: its parent {tp[:-1]!r} has no column in your plant")
                            new = {p: s for p, s in a.env.design.items() if not p.startswith(tp)}
                            for p, s in rec["design"].items():
                                if p.startswith(fp):
                                    new[tp + p[len(fp):]] = copy.deepcopy(s)
                            a.env.design = new
                        a.env.apply(args.get("edits") or [])
                    except (EditError, KeyError, TypeError, ValueError, AttributeError) as exc:
                        a.env.design = before_design
                        a.error = str(exc)
                        a.history.append(f"{rnd_no}: rejected edits ({str(exc)[:80]})")
                        a.turns.append({"turn": rnd_no, "action": "rejected", "error": str(exc), "edits": args.get("edits"), "copy_from": copied, "graft": graft})
                        continue
                    a.error = None
                    res = a.env.evaluate()
                    a.result = res
                    if a.env.score() is not None and (before_best is None or a.env.score() > before_best):
                        a.t_best = rnd_no
                    if res["valid"] and res["reward"] > 0 and a.first_positive is None:
                        a.first_positive = a.env.solves_used
                    note = str(args.get("note", ""))
                    a.history.append(f"{rnd_no}: reward {res['reward']:.3f}, {'valid' if res['valid'] else 'INVALID'}, {a.env.solves_used} solves"
                                     + (f", copied {copied}" if copied else "") + (f", grafted {graft.get('from_record')}:{graft.get('from_path')}" if graft else "")
                                     + f" | {note[:140]}")
                    rid = board.add(agent=a.id, island=a.island, family=family[a.id], round=rnd_no, reward=float(res["reward"]), valid=bool(res["valid"]),
                                    design=copy.deepcopy(a.env.design), columns=len(a.env.design), revenue=float(res["revenue"]), tac=float(res["tac"]),
                                    note=note, copied=copied, graft=graft, shown=shown_ids.get(a.id, []), solves=a.env.solves_used,
                                    structure=structure_of(res, names), niche=niche_of(res, names, len(a.env.design)),
                                    view=a.env.render(res, top=6))
                    a.turns.append({"turn": rnd_no, "action": "edit", "record": rid, "note": note, "edits": args.get("edits"), "copy_from": copied,
                                    "graft": graft, "notebook": a.notebook if cfg["notebook"] else None, "shown": shown_ids.get(a.id, []),
                                    "plan": args.get("plan"), "effort": getattr(a.client, "last_effort", None),
                                    "reward": res["reward"], "valid": res["valid"], "solves_used": a.env.solves_used})
                    team_curve.append((team_solves(), team_best(), round(time.time() - t0, 1)))
                if cfg["cull_every"] and rnd_no % cfg["cull_every"] == 0:
                    cull(rnd_no)
                if sup_mode and rnd_no % cfg["supervisor_every"] == 0:
                    try:
                        manage(rnd_no)
                    except (ToolResponseError, RuntimeError) as exc:
                        ev(kind="supervisor_error", round=rnd_no, error=str(getattr(exc, "category", exc)))
                write_json(Path(out_dir) / "team_curve.json", team_curve)
                for worker in workers:
                    with open(os.path.join(out_dir, "agents", worker.id, "turns.jsonl"), "w", encoding="utf-8") as f:
                        for turn in worker.turns:
                            f.write(json.dumps(turn, default=str) + "\n")
                logged, real = usd()
                ev(kind="round", round=rnd_no, team_best=team_best(), team_solves=team_solves(), active=len(active), usd_logged=logged, usd_real=real)
                log(f"[{cfg['preset']}/{model}] round {rnd_no}: team best {team_best():.3f}, team solves {team_solves()}, active {len(active)}, ${real:.2f} real (${logged:.2f} logged)")
    except Exception as exc:  # noqa: BLE001
        status = f"failed: {type(exc).__name__}: {exc}"
        ev(kind="failure", error=status)
    finally:
        events.close()
        with open(os.path.join(out_dir, "board.jsonl"), "w") as f:
            for r in board.records:
                f.write(json.dumps(r, default=str) + "\n")
        json.dump(team_curve, open(os.path.join(out_dir, "team_curve.json"), "w"))
        per = {}
        for a in everyone:
            os.makedirs(os.path.join(out_dir, "agents", a.id), exist_ok=True)
            with open(os.path.join(out_dir, "agents", a.id, "turns.jsonl"), "w") as f:
                for t in a.turns:
                    f.write(json.dumps(t, default=str) + "\n")
            s = a.client.ledger.summary({"status": a.status, "island": a.island, "strategy": a.strategy, "best_valid_reward": a.env.score() if a is not sup else None,
                                         "solves_used": a.env.solves_used if a is not sup else 0, "first_positive_at_solves": a.first_positive,
                                         "usd_cached_price_estimate": a.client.real_usd, "notebook": a.notebook, "task": task["task_id"]})
            per[a.id] = {k: s.get(k) for k in ("status", "island", "best_valid_reward", "solves_used", "first_positive_at_solves", "requests",
                                               "usd_estimated_total", "usd_cached_price_estimate")}

        def at(n_):
            b = 0.0
            for ts, tb, _ in team_curve:
                if ts <= n_:
                    b = tb
            return b
        best_rec = board.best(k=1)
        logged, real = usd()
        summary = dict(run_id=run_id, preset=cfg["preset"], model=model, task=task["task_id"], status=status, wall_s=round(time.time() - t0, 1),
                       team_best=team_best(), team_solves=team_solves(), best_at={k: at(k) for k in (100, 250, 500, 1000)},
                       team_first_positive_at_team_solves=next((ts for ts, tb, _ in team_curve if tb > 0), None),
                       agents_off_zero=sum(1 for a in workers if a.first_positive is not None), workers=len(workers),
                       best_record=best_rec[0]["id"] if best_rec else None, best_columns=best_rec[0]["columns"] if best_rec else 0,
                       best_design=best_rec[0]["design"] if best_rec else None, copies=sum(1 for r in board.records if r.get("copied")),
                       grafts=sum(1 for r in board.records if r.get("graft")), records=len(board.records),
                       distinct_structures=len({tuple(r["structure"]) for r in board.records}),
                       usd_logged=logged, usd_cached_price_estimate=real, requests=sum(a.client.ledger.n for a in everyone), agents=per, config=cfg)
        json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w"), indent=1, default=str)
    return summary
