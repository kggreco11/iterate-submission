"""
Per-run usage ledger for language-model agents: one JSON line per request (including failed ones) plus a summary.

Each event records run id, agent id, request id, provider, model, time, input / output tokens, cached-input and reasoning tokens where the provider
reports them (these may be subsets of the input / output counts: they are recorded, never added again), and the cost. Cost is labelled:
"estimated" = tokens x the listed price (source and date kept in PRICES), "billed" = provider-reported. Unknown usage is recorded as None, never 0.
"""
import json
import os
import time

# USD per million tokens (input, output). Source: team model configuration, 2026-11-14. Estimates, not invoices.
PRICES = {"kimi-k3.1-pro": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.1, 0.5)}
PRICE_SOURCE = "team model config, USD per million tokens, 2026-11-14"


class Ledger:
    def __init__(self, run_dir, run_id, agent_id="agent-0", provider="", model=""):
        os.makedirs(run_dir, exist_ok=True)
        self.dir, self.run_id, self.agent_id, self.provider, self.model = run_dir, run_id, agent_id, provider, model
        self.path = os.path.join(run_dir, "usage.jsonl")
        self.n = 0
        self.tok_in = self.tok_out = 0
        self.usd = 0.0
        self.unknown = 0
        self.failed = 0
        self.t0 = time.time()

    def estimate(self, tin, tout):
        if tin is None or tout is None or self.model not in PRICES:
            return None
        pi, po = PRICES[self.model]
        return (tin * pi + tout * po) / 1e6

    def record(self, request_id, tin, tout, cached=None, reasoning=None, ok=True, error=None, usd_billed=None, note=""):
        usd = usd_billed if usd_billed is not None else self.estimate(tin, tout)
        label = "billed" if usd_billed is not None else ("estimated" if usd is not None else "unknown")
        self.n += 1
        self.tok_in += tin or 0
        self.tok_out += tout or 0
        self.usd += usd or 0.0
        self.unknown += int(usd is None)
        self.failed += int(not ok)
        ev = {"run_id": self.run_id, "agent_id": self.agent_id, "request_id": request_id, "provider": self.provider, "model": self.model,
              "t": time.time(), "elapsed_s": time.time() - self.t0, "input_tokens": tin, "output_tokens": tout, "cached_input_tokens": cached,
              "reasoning_tokens": reasoning, "usd": usd, "usd_label": label, "ok": ok, "error": error, "note": note,
              "cumulative_usd": self.usd, "cumulative_requests": self.n}
        with open(self.path, "a") as f:
            f.write(json.dumps(ev) + "\n")
        return ev

    def summary(self, extra=None):
        s = {"run_id": self.run_id, "agent_id": self.agent_id, "provider": self.provider, "model": self.model, "requests": self.n,
             "failed_requests": self.failed, "input_tokens": self.tok_in, "output_tokens": self.tok_out, "usd_estimated_total": self.usd,
             "requests_with_unknown_cost": self.unknown, "price_source": ("https://modal.com/docs/guide/supported-models; 2026-11-14; uncached estimate" if self.model == "kimi-k3.1-pro" else PRICE_SOURCE), "wall_s": time.time() - self.t0, **(extra or {})}
        json.dump(s, open(os.path.join(self.dir, "summary.json"), "w"), indent=1)
        return s
