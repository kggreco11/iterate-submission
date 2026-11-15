"""
Stop a running language-model agent job once EVERY run in a folder has used at least N solves (a job started with a larger budget cannot be changed
while it runs). Only processes whose command line contains the given pattern, and their child processes, are stopped; nothing else is touched.

    python scripts/stop_at_solves.py runs/v2_opus --solves 200 --pattern "run_llm_agent.py" --also v2_opus

Runs that go past N solves before the last run gets there are read at N afterwards (scripts/curve_check.py --upto N). The killed runs do not write
their final run file; their turn logs (turns.jsonl) and usage logs (usage.jsonl) are complete up to the last finished turn.
"""
import argparse
import glob
import json
import os
import subprocess
import time


def solves_used(run_dir):
    tp = os.path.join(run_dir, "turns.jsonl")
    if not os.path.exists(tp):
        return 0
    used = 0
    for line in open(tp):
        try:
            used = max(used, json.loads(line).get("solves_used", 0))
        except ValueError:
            pass
    return used


def processes():
    ps = ("Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    data = json.loads(out) if out.strip() else []
    return data if isinstance(data, list) else [data]


def kill_tree(pattern, also):
    procs = processes()
    roots = [p["ProcessId"] for p in procs if p.get("CommandLine") and pattern in p["CommandLine"] and also in p["CommandLine"] and p["ProcessId"] != os.getpid()]
    victims, frontier = set(roots), list(roots)
    while frontier:
        pid = frontier.pop()
        for p in procs:
            if p["ParentProcessId"] == pid and p["ProcessId"] not in victims:
                victims.add(p["ProcessId"])
                frontier.append(p["ProcessId"])
    for pid in sorted(victims, reverse=True):
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"], capture_output=True)
    return sorted(victims)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--solves", type=int, default=200)
    ap.add_argument("--pattern", default="run_llm_agent.py")
    ap.add_argument("--also", default="", help="a second string the command line must contain (for example the output folder name)")
    ap.add_argument("--poll", type=float, default=20.0)
    a = ap.parse_args()
    while True:
        dirs = sorted(glob.glob(os.path.join(a.dir, "*/")))
        used = {os.path.basename(d.rstrip("/\\"))[:14]: solves_used(d) for d in dirs}
        done = {os.path.exists(os.path.join(d, "summary.json")) for d in dirs}
        if dirs and (all(v >= a.solves for v in used.values()) or done == {True}):
            break
        time.sleep(a.poll)
    stopped = kill_tree(a.pattern, a.also) if not (done == {True}) else []
    print("solves used per run:", used)
    print("stopped processes:", stopped if stopped else "none (the job had already finished)")


if __name__ == "__main__":
    main()
