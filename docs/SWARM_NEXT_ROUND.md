# Swarm study: what the literature says, and the next round (draft)

> Historical study document. For the current interpretation and ongoing experiments, read the [research report](../RESEARCH_REPORT.md) and [report guide](REPORT_GUIDE.md). Original observations below retain their study-specific limitations.

## Plain-language summary
The first screening showed that teams which share their best plant collapse onto one small plant within 7-10 rounds, and teams which never share
explore widely but rarely succeed. Both effects are well known: in human groups, in evolutionary algorithms and in groups of language models. The
standard remedy is to keep sub-populations apart and let them exchange good designs only occasionally ("islands with migration"), and to keep the
best design of each *kind* of solution rather than one overall best ("quality-diversity"). The next round tests those ideas, with more solves per agent
so plants can grow larger. Critics and the lessons board are dropped or redesigned.

## What the literature says (and how it matches our data)
| source | finding | our data |
|---|---|---|
| Lazer and Friedman, *The network structure of exploration and exploitation*, Administrative Science Quarterly 52(4), 2007 | in agent-based simulations, well-connected groups converge on existing solutions too fast; less connected groups explore more and eventually find better solutions | F1, F4, F5, F7 (everyone sees the best plant) collapsed to one plant; C1 and F3 kept variety |
| Mason and Watts, *Collaborative learning in networks*, PNAS 2012 (256 human-group experiments) | collective search beat solo search because good solutions spread; but networks also suppress individual exploration; efficient networks did better in their task | sharing got every agent off zero (10/10 vs 4/10 alone); it also cut new ideas from 44% to 19-24% of tries |
| Island-model evolutionary algorithms, e.g. Lässig and Sudholt (Soft Computing, 2014) and the migration-parameter study at GECCO 2005 | the migration interval is the dominant setting: migrate too often and the islands behave like one population and lose diversity; too rarely and islands get stuck; sparse topologies (ring) slow the spread of one dominant solution; "multikulti" migration sends the migrant most different from the receiver | F1 is migration every round to everyone; F3 is one migration late; nothing in between was tested |
| FunSearch (Romera-Paredes et al., Nature 2024) and AlphaEvolve (DeepMind, 2025) | LLM-driven evolutionary search keeps a database of solutions split into islands for diversity; FunSearch periodically resets weak islands from the best of others; AlphaEvolve's database combines islands with MAP-Elites (keep the best per niche) | our board keeps one "best"; there is no niche structure |
| MAP-Elites / quality-diversity (Mouret and Clune, 2015) and novelty search (Lehman and Stanley, 2011) | keep the best solution in each region of a "behaviour" space instead of a single best; reward novelty to avoid deception | our structure labels give a natural behaviour space (first cut, plant size) |
| Qian et al., *Scaling LLM-based multi-agent collaboration* (MacNet), ICLR 2025 | irregular, small-world interaction topologies beat regular ones; performance grows logistically with agent count | our topologies were "all-to-all" or "none" |
| Cemri et al., *Why do multi-agent LLM systems fail?* (MAST), NeurIPS 2025 | multi-agent gains over a single agent are often minimal; most failures come from system design (roles, coordination, verification), not the model | matches: no team beat the solo agent yet |
| LLM debate and conformity studies (e.g. Wynn et al. 2025; Bertalanic and Fortuna 2026; *Diversity collapse in multi-agent LLM systems*, 2026) | homogeneous LLM teams conform to the majority and lose diversity; unguided peer exchange can lower accuracy; collapse is driven by the interaction topology; opposing or structured roles help | F4's ten strategies collapsed to one plant; F6's critics approved 83% of proposals |

Caveat: these were found and checked at abstract level; numbers and exact mechanisms should be confirmed in the papers before we quote them.

## What our own data adds
- **Critics (F6) were mostly a rubber stamp:** 66 of 80 reviews approved, 12 vetoed (well reasoned), 2 amended (both worse); critics cost 27% of the team's
  model spend. A cheap rule-based check (reject a proposal whose structure the team already tried) would get most of the benefit for no tokens.
- **Strategies (F4) need protection to survive:** copying the team's best every 5 rounds erased the strategies. Copying should stay within a strategy.
- **Lessons (F2) were too loose:** free-text tips did not let Kimi rebuild good plants. If revived, lessons should be measured claims tied to a record
  ("in R44, raising reflux on the C4 split from 4 to 8 raised its purity from 93% to 96% for $9M/yr"), not advice.
- **Plants stayed small** (2-4 columns) with 50 solves per agent; a 10 x 100 run of F3 is in progress to test whether more solves fix this.

## Next run (round 2): the plan

### Changes since the screening run, and why
| change | why |
|---|---|
| Replies whose edits are not objects are rejected instead of stopping the run | the solo agent C0 crashed at 256 of 500 solves on one such reply |
| 100 solves per agent instead of 50 (team 1,000) | plants stayed at 2-4 columns while good V3 plants have 9-18; F3 with 100 each reached 2.55 vs 2.44 with 50, so budget alone helps only a little: the organisation has to change too |
| The board records each plant's structure (what every column separates), its lineage (family) and its niche, live | needed by G2 (copy only from another family) and G3 (niche board), and lets diversity be tracked during the run |
| Dropped: lessons board (F2), critics (F6), assigning supervisor (F7) | F2 scored 0.72 (free-text tips too lossy); critics approved 83% of proposals, cost 27% of spend and their amendments made plants worse; F7 explored the fewest plants (31) and stalled at 1.31 |
| Strategy portfolio (F4) replaced by protected strategies (G4) | in F4 the strategies were erased by copying the team's best plant every 5 rounds; all ten agents ended on one plant |
| Broadcast (F1), competing teams (F5) not re-run | their result is clear: the team collapses onto one plant within 7-23 rounds |
| Cost reporting: real cost is about 30% below the logged estimate | Modal reported 58% of input tokens as cached, billed at $0.20 instead of $2.00 per million; the shared Ledger is unchanged, both figures are reported |

### Conditions (V3 dev_002, Kimi K3.1 Pro, 10 agents x 100 solves, synchronous rounds, up to 250 rounds)
| code | mechanism | why (data, literature) | what a good result would mean |
|---|---|---|---|
| F3-100 (done) | alone until 70% of budget, then the top 3 plants every round | reference: kept 5 different final plants in the screening | baseline for this round: 2.55 at about 876 team solves |
| G1 ring islands | 5 islands of 2; share inside the island every round; every 10 rounds each island sees the next island's best plant | island-model theory: the exchange interval is the key setting; F1 (every round, to all) collapsed, F3 (once, late) did not | occasional sparse exchange beats both extremes |
| G2 other-family copying | see good plants from other lineages (including the one most different from yours); copying your own family is refused | "multikulti" migration; F1 collapsed onto one family | sharing without collapse |
| G3 niche board | the board keeps the best plant of each niche (first column's cut x plant size); agents see elites of other niches | MAP-Elites / AlphaEvolve's program database | keeping several kinds of plant alive finds a better one |
| G4 protected strategies | 5 strategies x 2 agents; see and copy only within your strategy group | conformity studies; F4's strategies were erased by copying | assigned diversity survives and pays off |
| G5 cull the weaker half | independent agents; every 10 rounds the weaker half stops and its unused solves go to the stronger half | successive halving, population-based training; in C1, 6 of 10 agents spent their whole budget without a profitable plant | the same exploration as C1 with less waste |
| G6 managed portfolio | 9 independent workers; every 10 rounds a supervisor may stop up to 3 workers and give their solves to another worker or restart them from an existing plant with a new strategy | the user's proposal; combines culling with deliberate branching | a supervisor can steer a portfolio better than a fixed rule (G5) |
| C0-1000 (recommended) | one agent with 1,000 solves | the screening has no clean solo result (C0 stopped at 256 with 2.66) | the bar every team has to clear at the same total budget |

### Measures and decision rule
- Team best at 250, 500 and 1,000 team solves; real and logged dollars; wall time.
- Diversity (scripts/plant_diversity.py): distinct structures, share of tries new to the team, distinct final plants, lineages and herd share at the end.
- Plant size: columns in the team's best plant and in the median plant.
- A condition goes forward if it beats F3-100 (2.55) by more than about 0.2 (the run-to-run noise we expect with one seed) or matches it with clearly more
  diversity. Winners are confirmed on dev_000, then scaled to 30 and 50 agents.

### Cost and time
About $8-10 logged ($6-7 real) per team run, $35-45 real for G1-G6, about $5 for C0-1000. Up to 70 simultaneous Kimi requests; about 1-1.5 hours.

