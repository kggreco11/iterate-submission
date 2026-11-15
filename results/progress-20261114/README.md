# Progress evidence and demo source — November 14, 2026

Curated from local saved artifacts; no model or simulator calls were made to package these files.

- `sol-200-demo.json`: saved HC12 Sol 200-call report payload (summary, improvements and turn history), sufficient to rebuild both demo pages. Unknown model pricing remains unknown.
- `sol-three-agent.json`: completed five-round live infrastructure test. 17 agent-charged queries, 13 actual backend calls; not an equal-budget performance comparison.
- `memory-isolation.json`: separate clean-slate probe; no accepted memories or reference-source overlap.
- `kimi-pair-snapshot.json`: cached HC16 V2 pair observation, including completed single-agent summary and in-progress swarm counters. Do not present it as a final swarm result. The packaged observation includes round 10 submissions; final comparison delivery belongs to the experiment chat.
- `manifest.json`: SHA-256 hashes of this curated bundle. Historical source provenance remains in the original run artifacts; the packaging base is not substituted for it.

Rebuild without network access or paid calls:

```sh
python3 demo/build_plant_3d.py results/progress-20261114/sol-200-demo.json
python3 demo/build_plant_v2.py results/progress-20261114/sol-200-demo.json
```

The site arrangement is illustrative. Only recorded column settings, products and economics are simulation evidence. The viewer replays accepted improvements rather than every submission.
