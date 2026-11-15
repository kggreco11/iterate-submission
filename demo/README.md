# 3D plant replay

Open `plant_3d.html` for the generated Sol 200-call demo. It is self-contained and works offline, without libraries or simulator calls.

Rebuild from another exported run:

```bash
python3 demo/build_plant_3d.py path/to/report-data.json --output demo/plant_3d.html
```

Play or scrub through saved best-design improvements, orbit with a drag, zoom with the wheel or buttons, and inspect equipment using a click or the selector. Canvas arrow keys rotate and zoom. Reduced-motion preferences disable growth and moving stream markers.

The source of truth is `replay.trace`. Column height maps to stage count. Topology uses a stable layout across the union of snapshots. Amber marks changed column settings relative to the previous saved improvement. Product colors follow recorded positive value; displayed economic values are revenue minus annual column cost. The intent text comes from a valid turn with the same simulator-call count, when available.

This is a replay of accepted improvements, not every attempted candidate or an active simulator connection. Plant footprint, tank shape and pipe routing are illustrative. Stream markers show connectivity, not physical velocities. Future live integration can feed the same snapshot shape into the viewer as a run is saved.

## V2: site assembly

`plant_v2.html` is a separate, self-contained WebGL version; V1 is preserved. It uses four compact equipment rows, a common overhead rack, local column assemblies, feed reception, product storage, access roads, a service building and daylight shadows. Site / Process / Tank farm / Plan presets and equipment focus support exploration. The connection overlay highlights a selected column's recorded child streams when the destination is represented.

```bash
python3 demo/build_plant_v2.py path/to/report-data.json
```

The builder embeds `plant_v2.js`, run data and the vendored Three.js 0.160.1 modules into a standalone page. No CDN or external network is required at viewing time. The library's MIT license is in `vendor/three/LICENSE`; vendored files come from the versioned `three@0.160.1` npm package via jsDelivr.

V2 starts at the final plant; **Replay assembly** returns to the feed-only snapshot. Equipment positions remain fixed across snapshots. Column shells change height with stage count (illustrative scaling); positive-value terminal products are grouped by component into storage. Light fractions use illustrative horizontal pressure vessels. Tanks have no implied measured inventory. Auxiliary vessels, skids, racks and buildings are visual context and are not included as additional simulated assets or costs. The site arrangement is conceptual, not a validated engineering plot plan. The stored run still supplies all displayed input settings and economics.

## Included reproducible source

The checked-in pages use [Sol 200 demo data](../results/progress-20261114/sol-200-demo.json). Rebuild both from a fresh checkout:

```sh
python3 demo/build_plant_3d.py results/progress-20261114/sol-200-demo.json
python3 demo/build_plant_v2.py results/progress-20261114/sol-200-demo.json
```
