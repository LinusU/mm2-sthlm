# Playable slice status

2026-10-03: all kickoff acceptance gates A–H are met for this small slice.
No current integration blocker. The next action is interactive driving or a
review of the focused engine PR; expanding the geographic scope is deferred.
This is an independently generated custom map, tested against the **patched**
engine revision below, not a claim about upstream main or retail MM2.

## Reproduce

From a fresh checkout, bootstrap Python dependencies explicitly once:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./scripts/sthlm build --offline
./scripts/sthlm validate
.venv/bin/ruff format --check src tests scripts/check-integration.py
.venv/bin/ruff check src tests scripts/check-integration.py
.venv/bin/python -m unittest discover -s tests -v
```

Prepare the external engine explicitly, or supply an independently built binary:

```sh
./scripts/prepare-engine /absolute/new/external/engine-checkout
./scripts/sthlm play --engine /absolute/new/external/engine-checkout/target/debug/mm2
./scripts/sthlm smoke --engine /absolute/new/external/engine-checkout/target/debug/mm2
.venv/bin/python scripts/check-integration.py --engine /absolute/new/external/engine-checkout/target/debug/mm2
```

For this local checkout the tested binary is also retained at the ignored
`.cache/engine/mm2`: `./scripts/sthlm play --engine "$PWD/.cache/engine/mm2"`.
Generation, validation, tests and play require no network after bootstrap.
Output: `dist/stockholm/`; generated content is ignored by Git and regenerated
from the checked-in genuine OSM snapshot. Controls are in README.md.

Engine base `1a568de7996be6813d32ab4f50d2f3dc150f258c`; tested revision
`cf5d4741100f78fc372398d36e06b228a3c0e938`, branch
`codex/smoke-motion-evidence`, [PR #1](https://github.com/LinusU/rust-mm2/pull/1).
The two reusable engine commits only improve generic drive evidence and add
an optional bot input speed ceiling. Shared vehicle physics is unchanged.
The clean patch replay reproduced that exact revision. See INTEGRATION.md
and `integration/rust-mm2/compatibility.json` for the patch/base/checksum.
Map source commits and fresh-checkout proof are recorded in
`evidence/fresh-checkout.json` once committed; `git rev-parse HEAD` identifies
the checkout containing this report.

## Acceptance evidence

| Gate | Result and evidence |
| --- | --- |
| A: real location | 223 clipped OSM road ways, 407 actual building footprints, complete local water geometry, Stadshuset relation 29368 and preserved courtyard. Four named streets form a 1,527 m source route. `sources/manifest.json`, SOURCES.md, `evidence/build.log`. |
| B: actual game | External rust-mm2 loads the portable PSDL mod with its existing procedural car, chase camera and vehicle simulation. Actual GPU renders, grounded spawn, reset, restart/session cleanup, water recovery and physical edge barrier verified. No retail assets needed. |
| C: independence | Offline build needs no engine checkout. Second clean output has identical checksums (`evidence/rebuild.log`). Package copied alone into a temporary mod root with empty working directory completes the full drive; a second synthetic triangle city loads through the same generic mechanism (`evidence/portability.json`). Fresh source checkout also rebuilt independently; see the fresh-checkout report. |
| D: map tests | 12 offline tests pass: coordinates/scale, holes, heights, malformed geometry, shared junctions, separated crossings, surface union/seams, real fixture clearance/courtyard/route, binary texture references, package integrity/path containment and honest drive-evidence rejection. Ruff format/lint pass. |
| E: actual driving | `evidence/loop-drive.log`: 187.68 simulated seconds, 1,503.7 m measured solver travel, 8.2 m/s peak, all 102/102 gates, finished one lap; 0 impacts, 0 resets, 0 bot recoveries, finite state, throttle/brake/steer activity, grounded 4/4 wheels at finish. No direct chassis animation or teleport progress. |
| F: visuals | Inspected actual 2560×1440 engine captures: waterfront car, Stadshuset and aerial layout. Camera commands below; image hashes in `evidence/screenshots.json`. Initial landmark render retained to show iteration. |
| G: quality/regressions | Engine fmt/clippy/full workspace tests passed before both commits; final 1,771 tests across 92 suites, no ignored tests. Dev world passes, London/SF run 10-second physics regressions against the existing legitimate installation. CI only tests offline map generation, no engine/GPU/network data fetch. |
| H: upstream | Separate external engine branch, clean committed revision, ready PR and reproducible two-commit patch. Original engine checkout left unchanged; no engine checkout/submodule/physics inside this project. |

Separate control/environment probes (not counted toward the continuous loop):

```sh
./scripts/sthlm play --engine "$MM2_ENGINE" -- --headless --frames 400 --reset-at 650
./scripts/sthlm play --engine "$MM2_ENGINE" -- --headless --frames 400 --restart-at 650
./scripts/sthlm play --engine "$MM2_ENGINE" -- --headless --frames 1000 --spawn=0,3.5,138,180
./scripts/sthlm play --engine "$MM2_ENGINE" -- --headless --frames 600 --spawn=-840,3.5,-200,90
```

Reset: one reset, final 4/4 wheel contact beside the map spawn. Restart: one
world rebuild, finite state, final 4/4 contact. Water: one water recovery to
last dry location; final sample is airborne after the driver continues into
water again, so this is recovery evidence, not a stable cruising result.
Boundary: two impacts stop the car at the west wall after 9.6 m, no resets.
London/SF reports are short loader/physics regressions, not completed tours;
SF ends airborne. Logs with `-base`, `loop-long`, `water-recovery` and
`first-street` are earlier progress/baseline experiments, not final acceptance.

## Actual screenshots

Run with the tested engine and final built package; the wrapper sets noon:

```sh
./scripts/sthlm play --engine "$MM2_ENGINE" -- --frames 90 --screenshot "$PWD/evidence/waterfront.png" --no-hud
./scripts/sthlm play --engine "$MM2_ENGINE" -- --frames 90 --screenshot "$PWD/evidence/stadshuset.png" --no-hud --cam=320,45,240,-65,0
./scripts/sthlm play --engine "$MM2_ENGINE" -- --frames 90 --screenshot "$PWD/evidence/aerial.png" --no-hud --cam=0,620,500,-25,-55
```

Waterfront uses the default chase camera at the road spawn. Camera arguments
are local game X,Y,Z,yaw,pitch (metres/degrees), not geographic coordinates.
These are unedited engine PNGs, not concept art or standalone-viewer captures.
After inspection the tower was given an open belfry/copper spire/crown
silhouette, tiny utility buildings were reduced, the eastern boundary was
extended 40 m to retain the entire landmark, and daylight readability improved.
© OpenStreetMap contributors; geographic data/geometry ODbL 1.0. Original
procedural artwork/code MIT. See SOURCES.md and package ATTRIBUTION.txt.

## Limitations and deferred work

Roads and terrain share an approximate flat reference; grade-separated
bridges/tunnels are excluded and reported. Conservative road widening is an
explicit config rule. Most heights are deterministic estimates, facades are
simple shared textures, Stadshuset is an original schematic silhouette rather
than a survey model, and the car is the engine's procedural vehicle. No
traffic, pedestrians, accurate interiors, complete city, retail-executable
compatibility or municipal/Lantmäteriet terrain integration is claimed.
The race route is a test circuit through existing streets; this slice permits
free driving in both directions regardless of real traffic restrictions.
Future engine revisions require an explicit compatibility re-test.
