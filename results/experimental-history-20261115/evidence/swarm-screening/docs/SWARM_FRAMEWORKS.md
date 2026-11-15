# Swarm study plan (draft for discussion)

Status: plan, nothing built yet. It builds on the team’s runner (`sepdesign/swarm.py`, PR #11's bounded prompts, own-history and exact incumbent
packet, and its four V3 controls); it does not change or replace it. A visual version with diagrams of each organisation is the "Swarm Study Plan"
artifact (shared by the team).

## Plain-language summary
Question: which way of organising a team of cheap Kimi agents designs the best V3 plant, and does any team beat one Kimi agent, or even one Opus?
We vary when agents communicate, what they share, whether they get strategies, how teams are structured and sized, and whether they have roles.
Nine conditions (two controls, seven team designs) are screened at 10 agents, the best four confirmed on a second task, the winner scaled to 3 and
30 agents, and the final demo runs the winner with 50 agents. Planned spend is about $226 of the $274 credit, with $48 left as contingency.

## What we already know
- Kimi K3.1 Pro alone on V3 at 200 solves: 8-38% of the best known plant; Opus 81-98%.
- Kimi alone at 40 solves scores 0 on three of four V3 tasks, so per-agent budgets must be at least about 50 solves.
- First swarm (5 Kimi, shared memory, V2 dev_000): 3.36 vs 3.42 for one Kimi, at $19.73 vs $1.26; the team traced this to memory delivery and
  prompt size (fixed in PR #11).
- Different Opus runs on V3 found layouts 8-16% apart: layout diversity is where a team can win.

## Factors and levels
| factor | levels | conditions |
|---|---|---|
| when agents communicate | never / every round / every few rounds / only at the end | C1 / F1 / F4, F5 / F3 |
| what they share | nothing / best design plus recent results / written lessons only | C1 / F1 / F2 |
| strategies | free / one assigned strategy per agent | F1 / F4 |
| team structure and size | one flat team / competing small teams / 3, 10, 30, 50 agents | F1 / F5 / scaling stage |
| roles | all equal / proposer, experimenter, critic / supervisor plus workers | F1 / F6 / F7 |
| who picks the answer | best agent / supervisor / final merge | all / F7 / F3 |

## The nine conditions (10 agents unless stated; 50 solves per solving agent)
| code | name | how it works | at 50 agents |
|---|---|---|---|
| C0 | Solo | one agent with the whole team budget (500 solves) | unchanged |
| C1 | Independent crowd | 10 agents, no communication; team answer = best agent | any size |
| F1 | Broadcast the best | every round each agent sees the team's best design and the last few results and may copy and edit it (the team’s exact packet) | any size |
| F2 | Lessons board | every round agents post one-line lessons; they see the team's best score and the top lessons but cannot copy designs | board keeps top 20 lessons |
| F3 | Islands, then merge | alone for 70% of the budget; then the top 3 designs are shown to all; last 30% refines them | any size |
| F4 | Strategy portfolio | a planner writes 10 distinct strategies (direct sequence, blend-heavy, premium-heavy, double effects on close splits, side draws for mid-cuts, ...), one per agent; best design shared every 5 rounds | 5 agents per strategy |
| F5 | Competing teams | 2 teams of 5; within a team share every round, between teams only the best design every 10 rounds | 10 teams of 5 |
| F6 | Proposers, experimenters, critics | 3 proposers (structure), 4 experimenters (settings on the best design), 3 critics review proposals before any solve and may veto or amend | keep the 3:4:3 mix |
| F7 | Supervisor and workers | a supervisor (no solves) reads the board and gives each of 9 workers one concrete experiment per round | lead + 4 supervisors + 45 workers |

## What each comparison teaches (priors are guesses to be tested)
| question | compare | prior |
|---|---|---|
| does parallel search alone help? | C1 vs C0 | barely; most agents end near zero at 50 solves |
| does sharing the best design help? | F1 vs C1 | yes, strongly for weak agents |
| designs or knowledge? | F2 vs F1 | designs; lessons are too lossy |
| does early sharing cause everyone to copy one plant? | F3 vs F1 | possible; islands start weak |
| does assigned diversity find better layouts? | F4 vs F1 | likely best on V3 |
| do small teams balance exploring and copying? | F5 vs F1 | moderate; main test is scaling to 50 |
| do critics save solves; do specialists help? | F6 vs F1 | fewer wasted solves, more tokens |
| does a supervisor avoid duplicate work? | F7 vs F1 | helps at 10, bottleneck at 50 |
| can cheap agents match one expensive one? | best team vs Opus (V3: 2.77 dev_000, 5.13 dev_002) | the headline for the demo |

## Common rules
- Model: Kimi K3.1 Pro for every agent and role.
- Budget: 50 distinct solves per solving agent (10-agent team = 500); C0 also gets 500. Critics, supervisors and planners spend no solves but
  their tokens are counted. Team charging as in the team’s runner.
- Tasks: V3 dev_002 to screen (Kimi's best task), dev_000 to confirm. Test tasks sealed.
- Scored: team's best valid plant at 100, 250 and 500 team solves as a share of the best known plant; model dollars, tokens, wall time, number of
  distinct layouts tried, duplicated solves, copy events, use of side draws and double effects.
- Same task brief and tool for all; conditions differ only in role text and board contents, within the team’s size caps.

## Budget ($274 credit)
Measured on V3 Kimi runs: $0.014 per request, 0.75 requests per solve. Assumed about $0.70 per agent per 50 solves with board context: about
$7 per 10-agent run, $35 per 50-agent run. Re-scaled after the pilot measures the real figure.
| stage | what | estimate |
|---|---|---|
| 0 | C0 on both tasks; one 10-agent F1 pilot to measure cost and time | $17 |
| 1 | all nine conditions on dev_002 | $70 |
| 2 | top four on dev_000 | $32 |
| 3 | winner at 3 and 30 agents; second seed of the top two | $37 |
| 4 | final demo: winner with 50 agents on two tasks | $70 |
| | contingency | $48 |

## Decisions needed
1. The nine conditions, or fewer with more seeds.
2. 50 solves per agent.
3. Build on PR #11 after it is merged with V3 (the branches conflict in `sepdesign/env.py` and `agents/llm_agent.py`).
4. Who builds the framework runner (the team or the team’s side).
5. Modal endpoint concurrency for 50 simultaneous requests.
