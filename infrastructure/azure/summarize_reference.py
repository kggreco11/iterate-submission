"""Produce a compact reference report from downloaded live replay artifacts."""
import json
from pathlib import Path
import math

root = Path(__file__).resolve().parents[2]
folder = root / 'results/reference-20261114'
r = json.loads((folder/'report.json').read_text())
summary = r['summary']
lines = ['# Live 12-column reference replay', '',
    'Executed 2026-11-14 on chemsep-01. This is a simulator reference check, not an agent experiment.', '',
    f"- **Execution:** {r['actual_simulator_calls']} fresh column calls, zero cache hits, {r['wall_s']:.1f} seconds including worker description and accounting; Azure command delivery adds overhead.",
    f"- **Economics:** annual revenue ${summary['revenue']/1e6:,.3f}M; annualized cost ${summary['tac']/1e6:,.3f}M; net ${summary['profit']/1e6:,.3f}M under the upstream benchmark assumptions.",
    '- **Reference agreement:** 12 successful columns, no unresolved streams; annualized cost matches exactly and revenue differs by less than $0.000001/year.',
    '- **Specification:** two terminal streams remain below the existing 95% purity cutoff; upstream spec_success is false.',
    '- **Physics:** all columns converged. Eleven of twelve pass the initial component balance check (absolute 1e-6 mol/s + relative 1e-7 of component inlet). The column fed by stream 6 fails; do not label this an unconditional physics pass.',
    f"- **Overall closure:** maximum absolute component residual {max(map(abs,r['overall_component_residual_mol_s'])):.3g} mol/s, using the upstream six-decimal stream rounding.",
    '- **Limit:** energy balance is not independently verified; heat duties alone do not provide inlet/outlet enthalpy closure.', '',
    'The flagged residuals are isopentane (2.56e-5 mol/s; 0.31 ppm of its inlet) and n-pentane (1.38e-6 mol/s; 0.50 ppm), both in the column fed by stream 6. All raw outlet flows are finite and nonnegative. These small residuals need an explicit numerical-tolerance decision; they do not demonstrate a gross conservation failure.', '', '## Product outcomes', '',
    'Recovery below counts a component only in on-spec terminal streams where it is the dominant component. Purity range describes those individual product streams, not a blended product.', '',
    '| Component | On-spec product purity | Component recovery |', '| --- | --- | --- |']
for comp, recovery in zip(r['task']['components'],r['component_recovery_to_own_on_spec_product']):
    ss=[s for s in r['outlets'] if s['dominant_component']==comp and s['disposition']=='product_on_spec']
    purity='No dedicated product' if not ss else f"{min(s['purity'] for s in ss)*100:.3f}–{max(s['purity'] for s in ss)*100:.3f}%"
    lines.append(f'| {comp} | {purity} | {recovery*100:.2f}% |')
lines += ['', 'Ethane remains in other streams; 0% dedicated-product recovery does not mean its mass disappeared.', '',
    '## Off-spec outlets', '', '| Stream | Main component | Purity | Flow (mol/s) |', '| --- | --- | --- | --- |']
for s in r['outlets']:
    if s['disposition']!='product_on_spec':
        lines.append(f"| {s['stream']} | {s['dominant_component']} | {s['purity']*100:.3f}% | {s['total_mol_s']:.3f} |")
lines += ['', 'The upstream stream-limit rule terminates these outlets. Treating them as residual streams versus requiring further separation is an explicit design-brief decision.', '',
    '## Implications for the experiment', '',
    '- Keep this as a reproducible economic reference, not a feasible example of recovering all six components as pure products.',
    '- A five-product brief with ethane allowed as an impurity/residual is a candidate, not yet an agreed requirement.',
    '- Freeze recovery thresholds and residual-stream rules before evaluation; reference isopentane recovery is about 75.9%.',
    '- Investigate and justify numerical tolerances before freezing the checker. Do not silently relax them to make the reference pass.', '',
    '## Flowsheet', '', '```mermaid', 'flowchart TD']
ref=json.loads((root/'infrastructure/azure/authors_design_reference.json').read_text())
for i,(sid,n,rr,rb,dp) in enumerate(ref['actions']):
    lines.append(f'  S{sid}["Stream {sid}"] --> C{i+1}["Column {i+1}: {n} stages; RR {rr}; RB {rb}; dP {dp}"]')
    lines.append(f'  C{i+1} -->|tops| S{2*i+2}')
    lines.append(f'  C{i+1} -->|bottoms| S{2*i+3}')
for s in r['outlets']:
    lines.append(f'  S{s["stream"]}["Stream {s["stream"]}: {s["dominant_component"]}, {100*s["purity"]:.2f}%"]')
lines += ['```', '', 'Machine-readable data: report.json; raw column trace: reference.calls.jsonl; independent check results: validation.json. Scripts: infrastructure/azure/replay_reference.py and summarize_reference.py. Simulator service and accounting library are still dependencies of the existing Windows installation; their fingerprints are recorded in report.json.']
(folder/'README.md').write_text('\n'.join(lines)+'\n')
print(folder/'README.md')
