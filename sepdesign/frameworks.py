"""
Agent-team frameworks for the swarm study (docs/SWARM_FRAMEWORKS.md). A separate runner beside sepdesign/swarm.py (the shared-memory runner,
unchanged): it reuses the task brief and state text of agents/llm_agent.py, the Kimi endpoint settings of agents/kimi.py, the Ledger and DesignEnv.

Every condition is run in synchronous ROUNDS: each active solving agent makes one model request per round (one edit list, then its plant is
re-simulated), so "every round" and "every 5 rounds" mean the same thing in every condition. The team's answer is the best valid plant any of its
agents evaluated. Every condition has the same TEAM budget of distinct column solves (default 500), split equally between the agents that solve;
critics and the supervisor solve nothing but their requests are logged and priced. A solve another agent already paid for is free on the machine
(shared cache) but is still charged to the agent that asks for it the first time, as in the shared-memory runner.

Conditions (code: what is different)
  C0 solo                one agent, the whole team budget
  C1 independent         10 agents, no communication
  F1 broadcast           every round: the team's best plant (copyable) and the latest results of teammates
  F2 lessons             every round: the team's best score and teammates' one-line lessons; designs cannot be copied
  F3 islands             alone until an agent has used 70% of its budget, then the team's top 3 plants (copyable) every round
  F4 strategies          each agent is assigned one of 10 strategies; the team's best plant every 5 rounds
  F5 teams               2 teams of 5: own team's best plant and results every round, the other team's best plant every 10 rounds
  F6 roles               3 proposers (structure), 4 experimenters (tune the team's best plant), 3 critics (review each proposal before it is
                         simulated: approve, amend, or veto)
  F7 supervisor          a supervisor reads the board each round and gives each of 9 workers one concrete experiment
  G1 ring islands        5 islands of 2: share inside the island every round; every 10 rounds each island sees the next island's best plant (ring)
  G2 other family        F1, but an agent may copy only from a different lineage than its own, and sees the plant most different from its own
  G3 niche board         the board keeps the best plant of each niche (first column's cut x plant size); agents see elites of other niches
  G4 protected strategy  5 strategies x 2 agents; an agent sees and may copy only plants of its own strategy group
  G5 cull                independent agents; every 10 rounds the weaker half is stopped and its unused solves go to the stronger half
  G6 managed portfolio   9 independent workers and a supervisor who, every 10 rounds, may stop a worker and either give its solves to another
                         worker or restart it from an existing plant with a new strategy to explore
Lineage ("family"): every agent starts its own; copying a record joins that record's family. Structure labels: what each column separates
(see column_label), as in scripts/plant_fingerprints.py.
"""
import copy
import json
import os
import random
import ssl
import threading
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from agents.kimi import MAX_OUTPUT_TOKENS, REASONING_EFFORT, ToolResponseError, endpoint_url
from agents.llm_agent import FINISH_SCHEMA, _state_text, edit_schema, system_prompt
from sepdesign.env import EditError
from sepdesign.ledger import Ledger
from sepdesign.service import make_env

STRATEGIES = [
    "Direct sequence: take the lightest components off first, one split at a time, working down the volatility order.",
    "Indirect sequence: take the heaviest components off first, working up the volatility order.",
    "Middle-out: make the first split in the middle of the volatility range, then work outwards on both sides.",
    "Blend-heavy: sell the C3, C4, C5 and C6 mixtures as blends instead of separating their close-boiling members.",
    "Premium-heavy: push the most valuable products to 99% purity to earn the premium grade.",
    "Double effects: look for close splits where a double-effect column saves enough energy to pay for the second column.",
    "Side draws: look for middle cuts (for example blends) that a side draw can deliver from one column instead of two.",
    "Lean plant: few columns, sell only the most valuable products, keep energy use low.",
    "Pressure-staged: use the valves' pressure drops to keep condensers out of expensive refrigeration.",
    "Energy-lean columns: more stages and lower reflux and boil-up to cut energy, the largest cost at these prices.",
]

CONDITIONS = {
    "C0": dict(name="solo", n=1),
    "C1": dict(name="independent", n=10),
    "F1": dict(name="broadcast", n=10),
    "F2": dict(name="lessons", n=10),
    "F3": dict(name="islands", n=10),
    "F4": dict(name="strategies", n=10),
    "F5": dict(name="teams", n=10),
    "F6": dict(name="roles", n=10),
    "F7": dict(name="supervisor", n=10),
    "G1": dict(name="ring islands", n=10),
    "G2": dict(name="other-family copying", n=10),
    "G3": dict(name="niche board", n=10),
    "G4": dict(name="protected strategies", n=10),
    "G5": dict(name="cull the weaker half", n=10),
    "G6": dict(name="managed portfolio", n=10),
}
COPY_CODES = ("F1", "F3", "F4", "F5", "F6", "F7", "G1", "G2", "G3", "G4")
SHORT = {"Ethane": "C2", "Propylene": "C3=", "Propane": "C3", "Isobutane": "iC4", "N-butane": "nC4", "Isopentane": "iC5", "N-pentane": "nC5",
         "2,2-dimethylbutane": "22DMB", "2-methylpentane": "2MP", "3-methylpentane": "3MP", "N-hexane": "nC6", "Methylcyclopentane": "MCP",
         "Cyclohexane": "CH", "N-heptane": "nC7", "N-octane": "nC8", "N-nonane": "nC9"}


def column_label(feed, tops, names, spec):
    """'<lightest>..<heaviest> | <light key>/<heavy key>' over components with >= 1% of the column feed (+side / +2fx)."""
    feed, tops = np.asarray(feed, float), np.asarray(tops, float)
    sig = [i for i in range(len(feed)) if feed[i] >= 0.01 * feed.sum()]
    if not sig:
        return "empty"
    up = [i for i in sig if tops[i] / feed[i] >= 0.5]
    lk = max(up) if up else None
    later = [i for i in sig if lk is not None and i > lk]
    hk = min(later) if later else None
    sn = lambda i: SHORT.get(names[i], names[i]) if i is not None else "-"  # noqa: E731
    lab = f"{sn(sig[0])}..{sn(sig[-1])} | {sn(lk)}/{sn(hk)}"
    if len(spec) > 4 and spec[4] is not None:
        lab += " +side"
    if len(spec) > 5:
        lab += " +2fx"
    return lab


def structure_of(res, names):
    return sorted(column_label(n["feed"], n["tops"], names, n["spec"]) for n in res["nodes"].values() if n.get("status") == "ok" and n.get("tops"))


def niche_of(res, names, ncols):
    root = res["nodes"].get("", {})
    cut = column_label(root["feed"], root["tops"], names, root["spec"]).split("| ")[-1] if root.get("status") == "ok" else "none"
    size = "1-2" if ncols <= 2 else "3-4" if ncols <= 4 else "5-7" if ncols <= 7 else "8+"
    return f"first cut {cut}, {size} columns"


def jaccard(a, b):
    a, b = set(a), set(b)
    return 0.0 if not a and not b else 1.0 - len(a & b) / len(a | b)


# ---------------------------------------------------------------------------------------------------------------------- model calls
class KimiClient:
    """One tool call per request to the Modal Kimi endpoint (same endpoint, model, output limit and reasoning effort as agents/kimi.py).
    Network failures are retried (they are not charged); a response that is not exactly one allowed tool call raises ToolResponseError."""
    _sem = threading.Semaphore(int(os.environ.get("KIMI_MAX_CONCURRENT", "40")))

    def __init__(self, ledger):
        if os.name == "nt":
            import truststore
            self.ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            self.ctx = ssl.create_default_context()
        self.ledger = ledger
        self.key = os.environ["MODAL_PROXY_TOKEN"]
        self.url = endpoint_url(os.environ["KIMI_ENDPOINT_URL"])
        self.model = os.environ["KIMI_MODEL"]

    def call(self, system, user, tools):
        body = dict(model=self.model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    tools=[{"type": "function", "function": dict(name=n, description=d, parameters=s)} for n, d, s in tools],
                    tool_choice="auto", max_tokens=MAX_OUTPUT_TOKENS, reasoning_effort=REASONING_EFFORT)
        response, last = None, None
        for attempt in range(4):
            req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers={
                "Authorization": "Bearer " + self.key, "Content-Type": "application/json",
                "Modal-Routing-Affinity-Key": self.ledger.run_id + "-" + self.ledger.agent_id})
            try:
                with self._sem:
                    with urllib.request.urlopen(req, timeout=240, context=self.ctx) as r:
                        response = json.load(r)
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
                self.ledger.record(None, None, None, ok=False, error="network: " + type(exc).__name__, note=f"attempt {attempt + 1}, not charged")
                time.sleep(10 * 2 ** attempt + random.random() * 5)
        if response is None:
            raise RuntimeError("Modal request failed 4 times: " + type(last).__name__)
        usage = response.get("usage") or {}
        allowed = {n for n, _, _ in tools}
        failure, parsed = None, None
        try:
            choice = response["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ToolResponseError("output_limit")
            calls = choice["message"].get("tool_calls") or []
            if len(calls) != 1:
                raise ToolResponseError("missing_tool" if not calls else "multiple_tools")
            fn = calls[0]["function"]
            if fn["name"] not in allowed:
                raise ToolResponseError("unknown_tool")
            args = json.loads(fn["arguments"])
            if not isinstance(args, dict):
                raise ToolResponseError("invalid_tool_arguments")
            if fn["name"] in ("submit_edits", "amend") and (not isinstance(args.get("edits", []), list)
                                                            or not all(isinstance(e, dict) for e in args.get("edits", []))):
                raise ToolResponseError("invalid_edits")
            parsed = (fn["name"], args)
        except ToolResponseError as exc:
            failure = exc
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            failure = ToolResponseError("malformed_response")
        self.ledger.record(response.get("id"), usage.get("prompt_tokens"), usage.get("completion_tokens"),
                           cached=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                           reasoning=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                           ok=failure is None, error=failure.category if failure else None)
        if failure:
            raise failure
        return parsed


class ScriptedClient:
    """No API (plumbing tests on the mock backend): workers put fixed settings on the next impure stream, sometimes copying the team's best plant;
    critics approve; the supervisor assigns the same instruction to everyone."""

    def __init__(self, ledger, env=None):
        self.ledger, self.env = ledger, env

    def call(self, system, user, tools):
        from sepdesign import baselines
        self.ledger.record("scripted", 0, 0, usd_billed=0.0, note="scripted: no API call")
        names = [n for n, _, _ in tools]
        if "assign" in names:
            return "assign", {"assignments": [{"worker": f"agent-{i}", "instruction": "extend the plant on an impure stream"} for i in range(1, 10)]}
        if "manage" in names:
            import re
            m = re.search(r"record (R\d+)", user)
            acts = [{"type": "branch", "stop_worker": "agent-9", "from_record": m.group(1), "strategy": "scripted branch"},
                    {"type": "reassign", "stop_worker": "agent-8", "give_to": "agent-1"}] if m else []
            return "manage", {"actions": acts, "note": "scripted"}
        if "approve" in names:
            return "approve", {"note": "scripted critic approves"}
        env = self.env
        todo = [""] if env.last is None else baselines._off_spec_leaves(env, env.last)
        if not todo or len(env.design) >= env.max_columns:
            return "finish", {"note": "scripted: nothing left"}
        args = {"note": "scripted: fixed settings on the next impure stream", "lesson": "scripted lesson",
                "edits": [{"op": "set", "node": todo[0], "n_stages": 53, "reflux_ratio": 3.56, "reboil_ratio": 3.56, "pressure_drop_fraction": 0.04}]}
        if "copy_from" in json.dumps([s for _, _, s in tools]) and "Team best plant" in user and random.random() < 0.3:
            rid = user.split("Team best plant: record ")[1].split(" ")[0] if "Team best plant: record " in user else None
            if rid:
                args["copy_from"] = rid
                args["edits"] = []
        return "submit_edits", args


# ---------------------------------------------------------------------------------------------------------------------- the board
def design_text(design):
    def one(p, s):
        t = f"'{p}': {s[0]}/{s[1]}/{s[2]}/{s[3]}"
        if len(s) > 4 and s[4] is not None:
            t += f" side {s[4][1]} stage {s[4][0]} fraction {s[4][2]}"
        if len(s) > 5:
            t += f" double effect {s[5][0]} to HP, LP dp {s[5][1]}"
        return t
    return "; ".join(one(p, s) for p, s in sorted(design.items(), key=lambda kv: (len(kv[0]), kv[0]))) or "(no columns)"


class Board:
    def __init__(self):
        self.records, self.lock = [], threading.Lock()

    def add(self, **r):
        with self.lock:
            r["id"] = f"R{len(self.records) + 1}"
            self.records.append(r)
            return r["id"]

    def get(self, rid):
        return next((r for r in self.records if r["id"] == rid), None)

    def best(self, team=None, k=1):
        rs = [r for r in self.records if r["valid"] and r["reward"] > 0 and (team is None or r["team"] == team)]
        rs.sort(key=lambda r: -r["reward"])
        out, seen = [], set()
        for r in rs:                                     # distinct designs only
            key = json.dumps(r["design"], sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                out.append(r)
            if len(out) >= k:
                break
        return out

    def recent(self, exclude=None, team=None, k=4):
        rs = [r for r in self.records if r["agent"] != exclude and (team is None or r["team"] == team)]
        return rs[-k:]


def record_line(r, with_design=False):
    t = (f"record {r['id']} by {r['agent']} (round {r['round']}): reward {r['reward']:.3f}{'' if r['valid'] else ' INVALID'}, "
         f"{r['columns']} columns, revenue ${r['revenue'] / 1e6:.0f}M/yr, cost ${r['tac'] / 1e6:.0f}M/yr | {r['note'][:160]}")
    if with_design:
        t += "\n    settings (path: stages/reflux/boil-up/pressure-drop): " + design_text(r["design"])
    return t


# ---------------------------------------------------------------------------------------------------------------------- one condition
class Agent:
    def __init__(self, aid, role, env, client, team=None, strategy=None):
        self.id, self.role, self.env, self.client, self.team, self.strategy = aid, role, env, client, team, strategy
        self.history, self.error, self.t_best, self.status, self.errors_in_row = [], None, 0, "active", 0
        self.result, self.assignment, self.first_positive = None, None, None
        self.turns = []


def _allocate(total, n):
    return [total // n + (1 if i < total % n else 0) for i in range(n)]


def run_condition(code, task, service, out_dir, team_budget=500, max_rounds=150, provider="modal", seed=0, log=print):
    """Run one condition; returns its summary dict. Artifacts: out_dir/{config,summary}.json, board.jsonl, events.jsonl, team_curve.json, agents/<id>/."""
    cond = CONDITIONS[code]
    rnd = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)
    run_id = f"{task['task_id']}-{code}-{uuid.uuid4().hex[:8]}"
    n = cond["n"]
    roles = ["solver"] * n
    teams = [None] * n
    if code == "F6":
        roles = ["proposer"] * 3 + ["experimenter"] * 4 + ["critic"] * 3
    if code in ("F7", "G6"):
        roles = ["supervisor"] + ["worker"] * 9
    if code == "G1":
        teams = [f"I{i // 2}" for i in range(n)]
    if code == "G4":
        teams = [f"S{i // 2}" for i in range(n)]
    if code == "F5":
        teams = ["A"] * 5 + ["B"] * 5
    solvers = [i for i, r in enumerate(roles) if r not in ("critic", "supervisor")]
    budgets = dict(zip(solvers, _allocate(team_budget, len(solvers))))
    strategies = rnd.sample(STRATEGIES, len(STRATEGIES)) if code == "F4" else [None] * n
    if code == "G4":
        five = rnd.sample(STRATEGIES, 5)
        strategies = [five[i // 2] for i in range(n)]
    agents = []
    for i in range(n):
        aid = f"agent-{i}"
        env = make_env(task, service, budget=budgets.get(i, 1))
        ledger = Ledger(os.path.join(out_dir, "agents", aid), run_id, agent_id=aid, provider=provider, model="kimi-k3.1-pro")
        client = KimiClient(ledger) if provider == "modal" else ScriptedClient(ledger, env)
        agents.append(Agent(aid, roles[i], env, client, teams[i], strategies[i] if code in ("F4", "G4") else None))
    family = {f"agent-{i}": f"agent-{i}" for i in range(n)}
    names = task["components"]
    board = Board()
    events = open(os.path.join(out_dir, "events.jsonl"), "w")
    team_curve = []
    config = dict(run_id=run_id, code=code, name=cond["name"], task=task["task_id"], team_budget=team_budget, agents=n, roles=roles, teams=teams,
                  budgets={agents[i].id: b for i, b in budgets.items()}, strategies={a.id: a.strategy for a in agents if a.strategy},
                  max_rounds=max_rounds, provider=provider, model="kimi-k3.1-pro", seed=seed, simulator_retries="ChemSep alternative initialisations on",
                  started=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(config, open(os.path.join(out_dir, "config.json"), "w"), indent=1)
    t0 = time.time()

    def ev(**e):
        e["t"] = round(time.time() - t0, 2)
        events.write(json.dumps(e, default=str) + "\n")
        events.flush()

    for a in agents:
        if a.role not in ("critic", "supervisor"):
            a.result = a.env.evaluate()

    def team_best():
        b = [a.env.score() for a in agents if a.role not in ("critic", "supervisor") and a.env.score() is not None]
        return max(b) if b else 0.0

    def team_solves():
        return sum(a.env.solves_used for a in agents if a.role not in ("critic", "supervisor"))

    # ---------------------------------------------------------------- prompt pieces
    def team_intro(a):
        if code in ("C0", "C1"):
            return ""
        s = (f"\n\nTEAM: you are {a.id}, one of {len(solvers)} agents designing plants for the same feed. The team's score is the best valid plant "
             f"any member evaluates. Your own solve budget is {a.env.solve_budget}. ")
        if code == "F1":
            s += "Every turn you see the team's best plant so far and teammates' latest results. You may copy the team's best plant (copy_from) and edit it, or keep working on your own."
        elif code == "F2":
            s += ("Every turn you see the team's best score and short lessons written by teammates. You cannot see or copy their plants. In each "
                  "submission, add a one-line 'lesson' your teammates can use (a finding, not a plan).")
        elif code == "F3":
            s += (f"You work alone until you have used 70% of your budget ({int(0.7 * a.env.solve_budget)} solves). After that you see the team's "
                  "three best plants every turn and may copy one (copy_from) to refine it with your remaining budget.")
        elif code == "F4":
            s += ("You are assigned a strategy (below); explore it seriously. Every 5 rounds you see the team's best plant and may copy it "
                  f"(copy_from).\nYOUR STRATEGY: {a.strategy}")
        elif code == "F5":
            s += (f"You are on team {a.team} (5 agents). Every turn you see your team's best plant and teammates' latest results and may copy it "
                  "(copy_from). Every 10 rounds you also see the other team's best plant.")
        elif code == "F6":
            if a.role == "proposer":
                s += ("Your role: PROPOSER. Make structural changes: add or remove columns, change which components each column separates, try side "
                      "draws or double effects. A critic reviews each proposal before it is simulated and may approve, amend or veto it. You see "
                      "the team's best plant and may copy it (copy_from).")
            else:
                s += ("Your role: EXPERIMENTER. Improve the team's best plant by tuning settings (stages, reflux, boil-up, pressure drop) of its "
                      "existing columns. Copy it (copy_from) when it is better than your current plant.")
        elif code == "F7":
            s += ("Your role: WORKER. Each turn a supervisor gives you one concrete experiment; carry it out as well as you can. You may copy the "
                  "team's best plant (copy_from) when the instruction is about it.")
        elif code == "G1":
            s += (f"You are on island {a.team} with one teammate. Every turn you see your island's best plant and your teammate's latest results "
                  "and may copy (copy_from). Every 10 rounds you also see the best plant of one neighbouring island and may copy it.")
        elif code == "G2":
            s += ("Every turn you see good plants from OTHER design families than your own (a family is the line of plants descended from one "
                  "agent's work; copying a plant joins its family), including the one most different from yours. You may copy (copy_from) only "
                  "plants from a family other than your own.")
        elif code == "G3":
            s += ("The team keeps the best plant of each kind (niche: the first column's cut and the plant's size). Every turn you see the best plants "
                  "of other niches than your current plant's. You may copy one (copy_from). Filling an empty or weak niche with a good plant helps the "
                  "team even if it is not the overall best.")
        elif code == "G4":
            s += (f"You and one teammate share a strategy (below); explore it seriously. Every turn you see the best plant and latest results of your "
                  f"strategy group only and may copy them (copy_from).\nYOUR STRATEGY: {a.strategy}")
        elif code == "G5":
            s += ("You work alone; you do not see teammates' plants. Every 10 rounds the weaker half of the team (by best valid reward) is stopped and "
                  "its unused solves are given to the stronger half.")
        elif code == "G6":
            s += ("Your role: WORKER. You work alone; you do not see teammates' plants. Every 10 rounds a supervisor reviews the team and may stop "
                  "workers that make little progress, give their solves to others, or restart a worker from another plant with a new strategy.")
            if a.strategy:
                s += f"\nYOUR CURRENT STRATEGY (given by the supervisor): {a.strategy}"
        return s

    def packet(a, rnd_no):
        if code in ("C0", "C1", "G5", "G6"):
            return ""
        lines = []
        if code == "G2":
            mine = family[a.id]
            others = [r for r in board.best(k=40) if r.get("family") != mine]
            if not others:
                return "\n\nPlants from other families: none with a positive reward yet."
            cur = structure_of(a.result, names) if a.result else []
            far = max(others[:12], key=lambda r: jaccard(cur, r.get("structure", [])))
            shown = [others[0]] + ([far] if far["id"] != others[0]["id"] else []) + [r for r in others[1:3] if r["id"] != far["id"]]
            return "\n\nGOOD PLANTS FROM OTHER FAMILIES (yours is " + mine + "):\n" + "\n".join(
                ("[most different from yours] " if r["id"] == far["id"] else "") + record_line(r, True) + f" | family {r.get('family')}" for r in shown)
        if code == "G3":
            elites = {}
            for r in board.records:
                if r["valid"] and r["reward"] > 0 and (r["niche"] not in elites or r["reward"] > elites[r["niche"]]["reward"]):
                    elites[r["niche"]] = r
            mine = niche_of(a.result, names, len(a.env.design)) if a.result else None
            shown = sorted((r for k, r in elites.items() if k != mine), key=lambda r: -r["reward"])[:5]
            lines.append(f"TEAM: best reward {team_best():.3f}; {len(elites)} niches filled. Your current plant's niche: {mine}.")
            if shown:
                lines.append("BEST PLANTS OF OTHER NICHES:\n" + "\n".join(f"[{r['niche']}] " + record_line(r, True) for r in shown))
            return "\n\n" + "\n".join(lines)
        if code == "F2":
            lessons = [r for r in board.records if r.get("lesson") and r["agent"] != a.id][-20:]
            lines.append(f"TEAM: best reward so far {team_best():.3f}.")
            if lessons:
                lines.append("Lessons from teammates (most recent last):\n" + "\n".join(f"- {r['agent']}: {r['lesson'][:200]}" for r in lessons))
            return "\n\n" + "\n".join(lines)
        if code == "F3":
            if a.env.solves_used < 0.7 * a.env.solve_budget:
                return ""
            top = board.best(k=3)
            if top:
                lines.append("TEAM'S THREE BEST PLANTS:\n" + "\n".join(record_line(r, True) for r in top))
            return "\n\n" + "\n".join(lines) if lines else ""
        if code == "F4" and rnd_no % 5:
            return ""
        team = a.team if code in ("F5", "G1", "G4") else None
        best = board.best(team=team)
        label = {"G1": "Your island's best plant", "G4": "Your strategy group's best plant", "F5": f"Team {a.team}'s best plant"}.get(code, "Team best plant")
        if best:
            lines.append(f"{label}: {record_line(best[0], True)}")
        else:
            lines.append("Team best plant: none with a positive reward yet.")
        if code in ("F1", "F5", "F6", "F7", "G1", "G4"):
            rec = board.recent(exclude=a.id, team=team)
            if rec:
                lines.append("Teammates' latest results:\n" + "\n".join("  " + record_line(r) for r in rec))
        if code == "F5" and rnd_no % 10 == 0:
            other = board.best(team="B" if a.team == "A" else "A")
            if other:
                lines.append(f"OTHER TEAM'S best plant: {record_line(other[0], True)}")
        if code == "G1" and rnd_no % 10 == 0:
            nxt = f"I{(int(a.team[1:]) + 1) % 5}"
            other = board.best(team=nxt)
            if other:
                lines.append(f"NEIGHBOURING ISLAND {nxt}'s best plant: {record_line(other[0], True)}")
        if code == "F7" and a.assignment:
            lines.append("SUPERVISOR'S INSTRUCTION FOR YOU THIS TURN: " + a.assignment)
        return "\n\n" + "\n".join(lines)

    def tools_for(a):
        sch = copy.deepcopy(edit_schema(a.env))
        sch["properties"].pop("evidence_ids", None)
        sch["properties"].pop("source_design", None)
        if code in COPY_CODES:
            sch["properties"]["copy_from"] = {"type": "string", "description": "Optional: a record id from the team board (e.g. 'R12'); that plant replaces your current design before your edits are applied."}
        if code == "F2":
            sch["properties"]["lesson"] = {"type": "string", "description": "One line your teammates can use: a finding from your results so far."}
        return [("submit_edits", "Edit the design (optionally copying a team record first), then re-simulate.", sch), ("finish", "Stop: nothing more worth trying.", FINISH_SCHEMA)]

    critic_tools = [("approve", "Approve the proposal as it is.", {"type": "object", "properties": {"note": {"type": "string"}}}),
                    ("amend", "Replace the proposal's edits with better ones.", {"type": "object", "properties": {"note": {"type": "string"}, "edits": copy.deepcopy(edit_schema(agents[0].env))["properties"]["edits"]}, "required": ["edits"]}),
                    ("veto", "Reject the proposal; it is not worth a simulation.", {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"]})]
    assign_tools = [("assign", "Give each worker one concrete experiment for this round.", {"type": "object", "properties": {
        "assignments": {"type": "array", "items": {"type": "object", "properties": {"worker": {"type": "string"}, "instruction": {"type": "string"}},
                                                   "required": ["worker", "instruction"]}}}, "required": ["assignments"]})]

    def save_prompt(who, rnd_no, system, user):
        d = os.path.join(out_dir, "agents", who)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "prompts.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"round": rnd_no, "system_chars": len(system), "user_chars": len(user), "system": system if rnd_no == 1 else None, "user": user}) + "\n")

    def ask(a, rnd_no):
        """One model request for a solving agent; returns (name, args) or raises."""
        system = system_prompt(task, a.env.solve_budget, a.env) + team_intro(a)
        user = _state_text(a.env, a.result, rnd_no, a.env.solve_budget, a.history, a.error, a.t_best) + packet(a, rnd_no)
        save_prompt(a.id, rnd_no, system, user)
        return a.client.call(system, user, tools_for(a))

    def supervise(sup, rnd_no, workers):
        recs = board.records[-24:]
        best = board.best(k=3)
        user = (f"Round {rnd_no}. Team best reward {team_best():.3f}. Team solves used {team_solves()} of {team_budget}.\n\n"
                + ("Best plants:\n" + "\n".join(record_line(r, True) for r in best) + "\n\n" if best else "No plant with a positive reward yet.\n\n")
                + ("Latest results:\n" + "\n".join("  " + record_line(r) for r in recs) + "\n\n" if recs else "")
                + "Workers and their remaining solves: " + ", ".join(f"{w.id} ({w.env.solves_left})" for w in workers)
                + "\n\nGive every listed worker one concrete, different experiment for this round (which plant to start from, what to change and why). "
                  "Avoid duplicate work. Workers see your instruction, their own plant and the team's best plant.")
        system = (system_prompt(task, team_budget, agents[1].env) + "\n\nYour role: SUPERVISOR of a team of worker agents. You do not edit plants or "
                  "use solves yourself. Each round you assign experiments; the team's score is the best plant any worker evaluates.")
        save_prompt(sup.id, rnd_no, system, user)
        name, args = sup.client.call(system, user, assign_tools)
        got = {x.get("worker"): x.get("instruction", "") for x in args.get("assignments", []) if isinstance(x, dict)}
        for w in workers:
            w.assignment = got.get(w.id) or "No instruction this round: improve your plant or the team's best plant as you judge best."
        ev(kind="assignments", round=rnd_no, assignments=got)

    manage_tools = [("manage", "Decide what to do with the workers after this review.", {"type": "object", "properties": {
        "actions": {"type": "array", "items": {"type": "object", "properties": {
            "type": {"type": "string", "enum": ["reassign", "branch"]},
            "stop_worker": {"type": "string", "description": "the worker to stop"},
            "give_to": {"type": "string", "description": "reassign: the worker who receives the stopped worker's unused solves"},
            "from_record": {"type": "string", "description": "branch: the record id of the plant the restarted worker starts from"},
            "strategy": {"type": "string", "description": "branch: the new strategy the restarted worker should explore from that plant"},
            "reason": {"type": "string"}}, "required": ["type", "stop_worker"]}},
        "note": {"type": "string"}}, "required": ["actions"]})]

    def manage(sup, rnd_no, workers_all):
        live = [w for w in workers_all if w.status == "active" and w.env.solves_left > 0]
        rows = []
        for w in workers_all:
            b = w.env.best[2] if w.env.best else None
            rows.append(f"{w.id}: status {w.status}, best reward {w.env.score() if w.env.score() is not None else 'none'}, solves used "
                        f"{w.env.solves_used}/{w.env.solve_budget}, best plant structure {structure_of(b, names) if b else '-'}"
                        + (f", strategy: {w.strategy}" if w.strategy else ""))
        best = board.best(k=6)
        user = (f"Review at round {rnd_no}. Team best {team_best():.3f}; team solves {team_solves()} of {team_budget}.\n\nWORKERS:\n" + "\n".join(rows)
                + ("\n\nBEST PLANTS ON THE BOARD:\n" + "\n".join(record_line(r, True) for r in best) if best else "")
                + "\n\nYou may stop up to 3 active workers. For each stopped worker either REASSIGN its unused solves to another active worker, or BRANCH: "
                  "restart it (same remaining solves) from an existing plant (from_record) with a new strategy to explore that is different from what "
                  "the team is already doing. Return an empty action list to change nothing. Workers do not see each other's plants.")
        system = (system_prompt(task, team_budget, workers_all[0].env) + "\n\nYour role: SUPERVISOR of a portfolio of worker agents. You use no solves. "
                  "Every 10 rounds you decide which workers to stop and how to use their remaining solves; the team's score is the best plant any "
                  "worker evaluates. Keep the portfolio diverse and put solves where they are most likely to improve the team's best plant.")
        save_prompt(sup.id, rnd_no, system, user)
        _, args = sup.client.call(system, user, manage_tools)
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
                w.env.solve_budget = w.env.solves_used
                g.env.solve_budget += left
                w.status = "stopped"
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
                w.history = [f"{rnd_no}: restarted by the supervisor from record {rec['id']} (reward {rec['reward']:.3f}) with a new strategy"]
                w.error, w.t_best = None, rnd_no
                family[w.id] = rec.get("family", rec["agent"])
                done.append({"action": act, "applied": True})
        ev(kind="portfolio", round=rnd_no, actions=done, note=args.get("note"))

    def cull(rnd_no, workers_all):
        live = [w for w in workers_all if w.status == "active" and w.env.solves_left > 0]
        if len(live) <= 2:
            return
        live.sort(key=lambda w: -(w.env.score() if w.env.score() is not None else -1e9))
        keep, stop = live[: (len(live) + 1) // 2], live[(len(live) + 1) // 2:]
        pool_ = sum(w.env.solves_left for w in stop)
        for w in stop:
            w.env.solve_budget = w.env.solves_used
            w.status = "culled"
        for k, w in enumerate(keep):
            extra = pool_ // len(keep) + (1 if k < pool_ % len(keep) else 0)
            w.env.solve_budget += extra
            w.history.append(f"{rnd_no}: you survived the cut and received {extra} more solves")
        ev(kind="cull", round=rnd_no, stopped=[w.id for w in stop], kept=[w.id for w in keep], solves_moved=pool_)

    def review(critic, proposer, args, rnd_no):
        user = (_state_text(proposer.env, proposer.result, rnd_no, proposer.env.solve_budget, proposer.history[-6:], None, proposer.t_best)
                + packet(proposer, rnd_no) + "\n\nPROPOSAL from " + proposer.id + ": " + json.dumps({k: args.get(k) for k in ("note", "copy_from", "edits")})[:4000]
                + "\n\nReview it before it is simulated (a simulation spends the proposer's budget). Approve it, amend its edits, or veto it.")
        system = (system_prompt(task, proposer.env.solve_budget, proposer.env) + "\n\nYour role: CRITIC for " + proposer.id + ". You use no solves. "
                  "Check each proposal for engineering sense and value for money before it is simulated.")
        save_prompt(critic.id, rnd_no, system, user)
        return critic.client.call(system, user, critic_tools)

    workers = [a for a in agents if a.role not in ("critic", "supervisor")]
    critic_of = {}
    if code == "F6":
        props = [a for a in agents if a.role == "proposer"]
        crits = [a for a in agents if a.role == "critic"]
        critic_of = {p.id: c for p, c in zip(props, crits)}
    status = "round_limit"
    if code == "C0":
        max_rounds = max(max_rounds, 2 * team_budget)          # one agent: one request per round, so it needs many more rounds
    try:
        with ThreadPoolExecutor(max_workers=max(4, n)) as pool:
            for rnd_no in range(1, max_rounds + 1):
                active = [a for a in workers if a.status == "active" and a.env.solves_left > 0]
                for a in workers:
                    if a.status == "active" and a.env.solves_left <= 0:
                        a.status = "budget_exhausted"
                if not active:
                    status = "all_done"
                    break
                if code == "F7":
                    try:
                        supervise(agents[0], rnd_no, active)
                    except (ToolResponseError, RuntimeError) as exc:
                        ev(kind="supervisor_error", round=rnd_no, error=str(getattr(exc, "category", exc)))
                        for w in active:
                            w.assignment = "The supervisor gave no instruction this round: improve your plant or the team's best plant."
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
                if code == "F6":                               # critics review proposers' submissions in parallel
                    rev = {}
                    for pid, (name, args) in list(proposals.items()):
                        if name == "submit_edits" and pid in critic_of:
                            rev[pool.submit(review, critic_of[pid], next(x for x in agents if x.id == pid), args, rnd_no)] = pid
                    for f, pid in rev.items():
                        try:
                            verdict, vargs = f.result()
                        except (ToolResponseError, RuntimeError) as exc:
                            ev(kind="critic_error", round=rnd_no, agent=pid, error=str(getattr(exc, "category", exc)))
                            continue
                        ev(kind="review", round=rnd_no, agent=pid, critic=critic_of[pid].id, verdict=verdict, note=vargs.get("note"))
                        if verdict == "veto":
                            p = next(x for x in agents if x.id == pid)
                            p.error = "Your critic vetoed the proposal (nothing simulated, no solves used): " + str(vargs.get("note", ""))[:300]
                            p.history.append(f"{rnd_no}: proposal vetoed by critic | {str(vargs.get('note', ''))[:120]}")
                            proposals.pop(pid)
                        elif verdict == "amend" and isinstance(vargs.get("edits"), list):
                            name, args = proposals[pid]
                            args = dict(args, edits=vargs["edits"], note=(args.get("note", "") + " [amended by critic: " + str(vargs.get("note", ""))[:120] + "]"))
                            proposals[pid] = (name, args)
                for a in active:                               # evaluate in a fixed order; the simulator serialises anyway
                    if a.id not in proposals:
                        continue
                    name, args = proposals[a.id]
                    if name == "finish":
                        a.status = "finished"
                        ev(kind="finish", round=rnd_no, agent=a.id, note=args.get("note"))
                        continue
                    before_design, before_best = copy.deepcopy(a.env.design), a.env.score()
                    copied = args.get("copy_from")
                    try:
                        if copied:
                            rec = board.get(str(copied))
                            if rec is None:
                                raise EditError(f"no record {copied!r} on the team board")
                            if code == "G2" and rec.get("family") == family[a.id]:
                                raise EditError(f"record {copied} is from your own family ({family[a.id]}); copy only from another family")
                            if code in ("G1", "G4") and rec.get("team") != a.team and not (code == "G1" and rnd_no % 10 == 0):
                                raise EditError(f"record {copied} is not from your {'island' if code == 'G1' else 'strategy group'}")
                            a.env.design = copy.deepcopy(rec["design"])
                            family[a.id] = rec.get("family", rec["agent"])
                        a.env.apply(args.get("edits") or [])
                    except (EditError, KeyError, TypeError, ValueError, AttributeError) as exc:
                        a.env.design = before_design
                        a.error = str(exc)
                        a.history.append(f"{rnd_no}: rejected edits ({str(exc)[:80]})")
                        a.turns.append({"turn": rnd_no, "action": "rejected", "error": str(exc), "edits": args.get("edits"), "copy_from": copied})
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
                                     + (f", copied {copied}" if copied else "") + f" | {note[:140]}")
                    rid = board.add(agent=a.id, team=a.team, round=rnd_no, reward=float(res["reward"]), valid=bool(res["valid"]),
                                    design=copy.deepcopy(a.env.design), columns=len(a.env.design), revenue=float(res["revenue"]), tac=float(res["tac"]),
                                    note=note, lesson=str(args.get("lesson", ""))[:240] if code == "F2" else "", copied=copied, solves=a.env.solves_used,
                                    family=family[a.id], structure=structure_of(res, names), niche=niche_of(res, names, len(a.env.design)))
                    a.turns.append({"turn": rnd_no, "action": "edit", "record": rid, "note": note, "edits": args.get("edits"), "copy_from": copied,
                                    "lesson": args.get("lesson"), "reward": res["reward"], "valid": res["valid"], "solves_used": a.env.solves_used,
                                    "usd_cum": a.client.ledger.usd})
                    team_curve.append((team_solves(), team_best(), round(time.time() - t0, 1)))
                if code == "G5" and rnd_no % 10 == 0:
                    cull(rnd_no, workers)
                if code == "G6" and rnd_no % 10 == 0:
                    try:
                        manage(agents[0], rnd_no, workers)
                    except (ToolResponseError, RuntimeError) as exc:
                        ev(kind="supervisor_error", round=rnd_no, error=str(getattr(exc, "category", exc)))
                ev(kind="round", round=rnd_no, team_best=team_best(), team_solves=team_solves(), active=len(active),
                   usd=sum(x.client.ledger.usd for x in agents))
                log(f"[{code}] round {rnd_no}: team best {team_best():.3f}, team solves {team_solves()}, active {len(active)}, "
                    f"${sum(x.client.ledger.usd for x in agents):.2f}")
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
        for a in agents:
            os.makedirs(os.path.join(out_dir, "agents", a.id), exist_ok=True)
            with open(os.path.join(out_dir, "agents", a.id, "turns.jsonl"), "w") as f:
                for t in a.turns:
                    f.write(json.dumps(t, default=str) + "\n")
            s = a.client.ledger.summary({"role": a.role, "team": a.team, "strategy": a.strategy, "status": a.status,
                                         "best_valid_reward": a.env.score() if a.role not in ("critic", "supervisor") else None,
                                         "solves_used": a.env.solves_used if a.role not in ("critic", "supervisor") else 0,
                                         "first_positive_at_solves": a.first_positive, "task": task["task_id"]})
            per[a.id] = {k: s[k] for k in ("role", "team", "status", "best_valid_reward", "solves_used", "first_positive_at_solves", "requests",
                                           "input_tokens", "output_tokens", "usd_estimated_total")}
        best_rec = board.best(k=1)

        def at(n_):
            b = 0.0
            for ts, tb, _ in team_curve:
                if ts <= n_:
                    b = tb
            return b
        first_pos_team = next((ts for ts, tb, _ in team_curve if tb > 0), None)
        summary = dict(run_id=run_id, code=code, name=cond["name"], task=task["task_id"], status=status, wall_s=round(time.time() - t0, 1),
                       team_best=team_best(), team_solves=team_solves(), team_budget=team_budget, best_at={k: at(k) for k in (50, 100, 250, 500)},
                       team_first_positive_at_team_solves=first_pos_team,
                       agents_off_zero=sum(1 for a in workers if a.first_positive is not None), solving_agents=len(workers),
                       best_record=best_rec[0]["id"] if best_rec else None, best_design=best_rec[0]["design"] if best_rec else None,
                       copies=sum(1 for r in board.records if r.get("copied")), records=len(board.records),
                       usd=sum(a.client.ledger.usd for a in agents), requests=sum(a.client.ledger.n for a in agents),
                       input_tokens=sum(a.client.ledger.tok_in for a in agents), output_tokens=sum(a.client.ledger.tok_out for a in agents),
                       backend_calls=len(getattr(service, "events", [])) and sum(1 for e in service.events if e.get("backend_call")),
                       agents=per)
        json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w"), indent=1, default=str)
    return summary
