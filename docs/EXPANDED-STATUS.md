# Expanded terrain acceptance

2026-10-03: the independently generated Stockholm terrain package is playable
in rust-mm2 revision `392cc9be55a624f9c8cf64272103f987631c204d`.
The reusable engine change is [PR #2](https://github.com/LinusU/rust-mm2/pull/2),
with its patch and SHA-256 under `integration/rust-mm2/`. No engine checkout or
vehicle simulation is part of this project. Original MM2 compatibility remains
unverified and requires a separate retail export milestone.

## Reproduce

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./scripts/sthlm build --offline
./scripts/sthlm validate
.venv/bin/ruff format --check src tests scripts/check-integration.py
.venv/bin/ruff check src tests scripts/check-integration.py
.venv/bin/python -m unittest discover -s tests -v
./scripts/prepare-engine /absolute/new/external/engine-checkout
./scripts/sthlm play --engine /absolute/new/external/engine-checkout/target/debug/mm2
.venv/bin/python scripts/check-integration.py --engine /absolute/new/external/engine-checkout/target/debug/mm2
.venv/bin/python scripts/check-expanded.py --engine /absolute/new/external/engine-checkout/target/debug/mm2
```

The ignored local binary is `.cache/engine/mm2`. Launch the finished package:
`./scripts/sthlm play --engine "$PWD/.cache/engine/mm2"`.
Generation and validation need no network, GPU, engine checkout or retail data.
CI rebuilds the package independently and compares every generated checksum.
Terrain source rebuilding has separate optional dependencies (TERRAIN.md).

## Measured results

| Check | Evidence |
| --- | --- |
| Real target scope | Real OSM shoreline components retain the complete included islands. The north uses 43 sourced E20 ways with a 100 m corridor margin. Excluded islands, external bridges, unmodeled ships and floating clipped building remnants are rejected. Eight shared-node routes connect the spawn to city coverage references; this is connectivity evidence, not a claim that every street has been driven. |
| Map content | 7,422 road ways, 10,741 building footprints, 1,585 native breakable tree props. Roads span 0.9–48.11 m RH2000-derived height, with a documented nominal minimum at low quays. Bridge decks are separate estimates. |
| Terrain | Six 1 m SWEREF99 TM / RH2000 tiles; all 1,131,599 cells in the resampled 10 m fixture are valid. Original tile checksums, metadata, survey provenance, licence PDF and delivery-footprint check are retained. |
| Portable export | 55 PSDL parts, 854,773 combined vertices, largest pool 40,584 vertices. No individual pool reaches the 16-bit limit. The `.chunks` extension is required for this expanded rust-mm2 export. |
| Offline quality | 23 map tests, format/lint, build and validation passed. Independent builds have byte-identical checksum manifests. Every bounded surface patch checks its triangulated area during export. |
| Actual driving | The unchanged 1.53 km benchmark completes 102/102 gates through real vehicle control: 1504.1 m travel, 187.78 simulated seconds, 8.2 m/s peak, 0 impacts, 0 resets, finite state, 4/4 wheel contact. See `evidence/expanded/portability.log`. |
| Elevation contact | Stationary actual-car probes on Södermalm, Djurgården and western Kungsholmen settle with 4/4 wheels. A short 17.1 m Västerbron drive has 0 impacts, 0 resets and 4/4 contact. This does not claim a complete bridge or full-city driving tour. |
| Reset/restart | The separate reset probe records one reset with 4/4 final contact; the restart probe imports the city twice and settles with 4/4 contact. Neither is counted toward the continuous loop. |
| Breakable props | A real car/tree collision breaks one native banger into two active pieces: `bng=1584d/2a/0s/1b`, `bng_ev=0a/0s/1b`. Tree meshes are independent PKG assets, not baked city geometry. |
| Portability failures | A relocated package drives from an empty working directory. A second independent two-part city drives 317.9 m through its seam. Deleting the second PSDL produces a fatal load error. |
| Engine quality | Formatting, full-feature Clippy and 1,774 workspace tests in 92 suites passed. Parallel networking process tests initially timed out starting children; the full suite passed with serial process tests. |

Machine-readable reports, raw engine records and unmodified in-engine captures
are in `evidence/expanded/`. The package checksum and generator/source hashes
identify the data actually tested. Legacy evidence at `evidence/` belongs to
the original flat slice and its earlier engine revision.

## Visual verification and limits

`map-overview.png`, `stadshuset-terrain.png`, `sodermalm-drive.png` and
`tanto-terrain.png` are captures of the real game, with normal city import and
physics active. They are not screenshots from a standalone viewer. The initial
waterfront and southern-shore captures are retained to document the church
silhouette correction and removal of an excluded-shore building fragment.
Capture logs show the engine revision and commands are retained in the report.

This is a first expanded terrain pass. Ground mesh spacing is up to 25 m;
road centerlines are sampled every 10 m, boundaries every 5 m. Terrain is real,
but bridge deck clearances, water reference levels, road-bed clearance and
most building heights/materials remain documented approximations. Detailed
retaining walls, road cuts, authored bridge silhouettes, tunnel routes,
forest density, traffic/navigation and retail compatibility remain future work.
Optional retail HUD/audio/sky assets are absent and reported; none were copied.
