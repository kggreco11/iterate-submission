# Original completed experiment inventory

**Update:** this table covers the original 20 runs. Another 12 completed runs are documented in [the team’s work](SCREENING.md); the [combined CSV](completed-runs.csv) contains all 32.

Compiled 2026-11-15T11:21:22-08:00. 20 completed plant-design model runs; per-agent budgets are announced ceilings, not necessarily consumed. Paid infrastructure checks and failed/interrupted attempts are excluded. Empty CSV values mean unknown or not independently extracted, never zero.

| Run / evidence | Task | Model | Agents / sharing | Budget each / total | Used / backend | Best reward | Model $ | Wall min |
|---|---|---|---|---:|---:|---:|---:|---:|
| [hc16v2_dev_000_anthropic_claude-opus-5-5_s0_ab9fe8](evidence/hc16v2_dev_000_anthropic_claude-opus-5-5_s0_ab9fe8-summary.json) | hc16v2_dev_000 | claude-opus-5-5 | 1 / own history; no external shared memory | 400 / 400 | 106 / unknown | 3.6292 | 2.86 | 14.9 |
| [v2-kimi-20261114-r3-single](evidence/v2-kimi-20261114-r3-single-summary.json) | hc16v2_dev_000 | kimi-k3.1-pro | 1 / own history; no external shared memory | 200 / 200 | 200 / unknown | 3.4219 | 1.26 | 9.3 |
| [hc16v2_dev_001_anthropic_claude-opus-5-5_s0_78f86c](evidence/hc16v2_dev_001_anthropic_claude-opus-5-5_s0_78f86c-summary.json) | hc16v2_dev_001 | claude-opus-5-5 | 1 / own history; no external shared memory | 400 / 400 | 113 / unknown | 4.6312 | 2.88 | 15.3 |
| [hc16v2_dev_002_anthropic_claude-opus-5-5_s0_cc9fc9](evidence/hc16v2_dev_002_anthropic_claude-opus-5-5_s0_cc9fc9-summary.json) | hc16v2_dev_002 | claude-opus-5-5 | 1 / own history; no external shared memory | 400 / 400 | 204 / unknown | 7.3802 | 4.98 | 26.6 |
| [hc16v2_dev_003_anthropic_claude-opus-5-5_s0_19f2a3](evidence/hc16v2_dev_003_anthropic_claude-opus-5-5_s0_19f2a3-summary.json) | hc16v2_dev_003 | claude-opus-5-5 | 1 / own history; no external shared memory | 400 / 400 | 153 / unknown | 5.1934 | 3.69 | 19.5 |
| [hc16v3_dev_000_anthropic_claude-opus-5-5_s0_ea02f9](evidence/hc16v3_dev_000_anthropic_claude-opus-5-5_s0_ea02f9-summary.json) | hc16v3_dev_000 | claude-opus-5-5 | 1 / own history; no external shared memory | 400 / 400 | 233 / unknown | 2.7669 | 4.18 | 20.8 |
| [hc16v3_dev_001_anthropic_claude-opus-5-5_s0_3413a2](evidence/hc16v3_dev_001_anthropic_claude-opus-5-5_s0_3413a2-summary.json) | hc16v3_dev_001 | claude-opus-5-5 | 1 / own history; no external shared memory | 400 / 400 | 153 / unknown | 2.8531 | 4.45 | 22.9 |
| [hc16v3_dev_002_anthropic_claude-opus-5-5_s0_49f7ac](evidence/hc16v3_dev_002_anthropic_claude-opus-5-5_s0_49f7ac-summary.json) | hc16v3_dev_002 | claude-opus-5-5 | 1 / own history; no external shared memory | 400 / 400 | 110 / unknown | 5.1323 | 2.58 | 15.0 |
| [hc16v3_dev_003_anthropic_claude-opus-5-5_s0_2f665d](evidence/hc16v3_dev_003_anthropic_claude-opus-5-5_s0_2f665d-summary.json) | hc16v3_dev_003 | claude-opus-5-5 | 1 / own history; no external shared memory | 400 / 400 | 284 / unknown | 4.4425 | 4.14 | 21.0 |
| [luna-pilot-20261114T211810Z](evidence/luna-pilot-20261114T211810Z-summary.json) | hc12_dev_000 | gpt-6-luna | 1 / own history; no external shared memory | 50 / 50 | 50 / unknown | 0.7750 | unknown | 20.1 |
| [gpt-6.1-sol-pilot-20261114T220604Z](evidence/gpt-6.1-sol-pilot-20261114T220604Z-summary.json) | hc12_dev_000 | gpt-6.1-sol | 1 / own history; no external shared memory | 50 / 50 | 50 / unknown | 3.3784 | unknown | 33.8 |
| [sol-200-20261114](evidence/sol-200-20261114-summary.json) | hc12_dev_000 | gpt-6.1-sol | 1 / own history; no external shared memory | 200 / 200 | 200 / unknown | 3.1705 | unknown | 19.7 |
| [swarm-a1b45716fe3444679f33125db48b89b7](evidence/swarm-a1b45716fe3444679f33125db48b89b7-summary.json) | hc16v2_dev_000 | kimi-k3.1-pro | 5 / Past retrieval; historical V2 feedback/context defects | 100 / 500 | 454 / 409 | 3.3566 | 19.73 | 54.8 |
| [swarm-5495ec4fea6c47a19b99c3e0cf21d42f](evidence/v3-100-campaign-snapshot.json) | hc16v3_dev_000 | kimi-k3.1-pro | 1 / exact; local feedback/incumbent protocol V3 | 100 / 100 | 100 / 100 | 0.4255 | 1.33 | 8.5 |
| [swarm-66df0079cddd45de96f67a6ed20fe47d](evidence/v3-100-campaign-snapshot.json) | hc16v3_dev_000 | kimi-k3.1-pro | 1 / past; local feedback/incumbent protocol V3 | 100 / 100 | 100 / 100 | 0.6060 | 1.82 | 8.5 |
| [swarm-543232b4170f4d8b9496a6824c30f029](evidence/v3-100-campaign-snapshot.json) | hc16v3_dev_000 | kimi-k3.1-pro | 5 / exact; local feedback/incumbent protocol V3 | 100 / 500 | 488 / 309 | 2.0698 | 5.78 | 15.8 |
| [swarm-5006f87b620d4f0da586b996e2358009](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/report-data.json) | hc16v3_dev_000 | kimi-k3.1-pro | 1 / single_without_past | 400 / 400 | 395 / 395 | 2.4383 | 6.83 | 39.4 |
| [swarm-ee547757b06143bbbd3cab016ebc93f5](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/report-data.json) | hc16v3_dev_000 | kimi-k3.1-pro | 1 / single_with_past | 400 / 400 | 400 / 400 | 1.3800 | 5.96 | 33.4 |
| [swarm-99005c2897f049e8bf38ddfb0eefd900](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/report-data.json) | hc16v3_dev_000 | kimi-k3.1-pro | 5 / swarm_without_past | 400 / 2000 | 1978 / 1212 | 2.6249 | 19.81 | 48.0 |
| [swarm-72cb1e123ba9413e9c715b38544c0067](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/report-data.json) | hc16v3_dev_000 | kimi-k3.1-pro | 5 / swarm_with_past | 400 / 2000 | 1963 / 1148 | 2.4553 | 15.59 | 39.2 |
