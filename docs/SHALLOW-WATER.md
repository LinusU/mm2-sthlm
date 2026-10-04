# Shallow ponds and fountain basins

`src/ponds.py` inventories complete source water/fountain polygons within the
approved playable mask. Native pond collision stays independent of rust-mm2:
no vehicle/engine implementation belongs in this module.

Municipal sources identify Kungsträdgården's northern fountain basin as
Forumdammen (source way/219139744); Molins fontän is way/440218402. Both use
the complete sourced outlines. Source overrides live in
`config/overrides/shallow-water.json`; no guessed duplicate basin is emitted.
Local water levels and the 0.2 m gameplay depth are estimates, not surveyed
water measurements. Original procedural blue-green translucent ripple artwork
is generated offline; no retail photographs/textures are copied.

References:
- https://parker.stockholm/parker/kungstradgarden/
- https://start.stockholm/globalassets/start/om-stockholms-stad/sa-arbetar-staden/natur-parker-och-gronomraden/parkplan-norrmalm---beskrivning-av-parker.pdf
- https://commons.wikimedia.org/wiki/File:Kungsträdgården_-_fontän_-_körsbärsträd_-_20240504_-_26.jpg

Small complete inland water, pond/basin/reflecting-pool and fountain polygons
up to 5,000 m² are classified as authored shallow gameplay water. Canals,
rivers, streams, locks, reservoirs, marinas, dry docks and larger water remain
deep. Any source polygon overlapping the marine coastline fill by more than
10% remains deep. Explicit Slussen channels way/1291160189 and way/1291160190
remain deep even without a water subtype. Tiny OSM `water=lake` shapes in
Skansen are shallow gameplay ponds; this classification does not assert their
real depth. Pond multipolygon relations retain holes, without duplicating
tagged outer-member ways. Ankdamm is relation/6995886.

Each basin's visible water level is the median of sixteen final local ground
samples along its sourced boundary, minus 0.04 m. The floor sits 0.2 m below
that water, with up to 1.5 m internal bank ramps (narrow basins use a shorter ramp) and a 4 m external transition to the
local ground field. Ground, shoulder and pond collision geometries are
partitioned. Existing roadway collision takes priority where source outlines
intersect roads. The exported inventory retains IDs and derived levels.

Native semantics matter: `.water` room references are always deadly in tested
engine `b3d9804489bdcd576dd4b85b3f40fec75c545071`. Shallow rooms are never added
there. The submerged floor is a normal native PSDL fan using an authored SDL
material with drag 0.119; the surface is an original translucent native PTH
decal, which the generic engine renders without collision. The triangles use
supported four-point strips with one degenerate triangle; the native strip's
0.02 m lift is accounted for in the authored water Y. Existing decal paths and
other material-table records are preserved.

Read-only comparison used the engine's retail-data research
`docs/research/materials.md` and `crates/mm2_app/src/water.rs`: the shared retail
water class has drag 0.119 and deepwater has 0.5. London PSDL's measured table
has deepwater, while SF has the measured shallow `water` pond entry. No direct
London shallow pond driving comparison was available in this worktree, so
this work does not claim one. No engine change is needed for the supported
PSDL-floor plus render-only PTH surface implementation.

Coordinator hooks are recorded in
`evidence/shallow-water/integration-hooks.patch`: normalization subtracts shallow
water from deadly water and restores its land footprint; export prepares with
the final ground field, partitions its collision area, emits the floor/banks,
and appends water decals after road-details output. `write(out,city)` also emits
`shallow-water.json` before package checksums. Shared hooks are coordinator-owned.

Optional external native check (normal CI needs no engine/GPU/retail content):

```sh
.venv/bin/python scripts/probe-shallow-water.py \
  --engine /Users/linus/coding/mm2-sthlm/.cache/engine/mm2 \
  --output .cache/shallow-water-probe
```

The original 24 m-high probe includes a distinct deadly water room at sea
level. Intermediate and final native drives establish actual entry onto the
submerged floor and exit across the far bank. Acceptance requires finite
physics, four grounded wheels, zero resets and no recovery counter. It is
physics evidence, not an in-engine screenshot.

Generated probe packages belong under `.cache` or `dist`; only logs, compact
source/height inventory, exact checksums and genuine native captures are kept
as evidence. Full offline format/lint/unit/build/validate gates are required
before the map commit. See `evidence/shallow-water` for actual results and any
blocked approaches; a blocked route is not counted as a successful crossing.

## Native evidence and limits

These runs used the separate external engine revision
`b3d9804489bdcd576dd4b85b3f40fec75c545071`; its binary SHA256 is recorded in
`evidence/shallow-water/engine-sha256.txt`. Capture-package checksums distinguish
native screenshots and initial city drives from the final corrected export.
The native images show source Forumdammen and Grubbensdammen, with the car
standing on the shallow floor. They are genuine engine output, not viewer art.

| Native check | Result |
| --- | --- |
| Synthetic basin at 24 m ground | Interior final `(7,24.5,-10)` at 260 frames; exit `(65,24.8,-10)` at 600; 74.9 m travel, 4/4 wheels, 0 impacts/resets/recovery. |
| Grubbensdammen source way/28165044 | Interior `(-163,2.6,-847)` at 360 frames; far side `(-119,2.6,-848)` at 800; 69.1 m travel, 4/4 wheels, 0 impacts/resets/recovery. |
| Forumdammen source way/219139744 | Close-bank start `(1460.26,4.046,-449.089)`, yaw 270; final `(1492,3.4,-450)` at 410 frames; 31.9 m travel, 4/4 wheels, 0 impacts/resets/recovery. Water east edge at north 450 is 1484.49 m. |

Two rejected approaches are retained transparently: a guessed northern
rectangle was placed too far north among buildings, then removed once the
municipal source identified Forumdammen. Its `kungstradgarden-*` logs are
rejected-location evidence and must never count as accepted crossings.
An initial source-Forumdammen start 8 m west struck planted tree-row props;
it crossed without water recovery but is not the zero-impact acceptance.
The closer bank start avoids that row and crosses cleanly. Successful
physics runs do not themselves establish native visual quality; the two
separate native screenshots provide that visual evidence.

The final export adds relation/6995886, removes the rejected rectangle,
retains navigable Slussen channels and omits pond/bank areas from tree-placement
land. Root integration must retest these basins against its final combined
height field and package; source coordinates stay the same, derived water
levels can change when road smoothing changes nearby ground.

Final isolated acceptance passed all 94 offline tests, formatting, lint,
`build --offline` and package validation: 57 shallow features, 765 native
water triangles and 55 PSDL parts. The corrected package also passed the
relocated full circuit (102/102 gates, 1,503.8 m travel, zero impacts/resets,
four grounded wheels), independent second city and missing-chunk rejection.
The final package manifest SHA256 is
`e858a4d207575ff6b4082698f067711a6c93f0f8bb67679c66a465d5a9d19f64`.
These are isolated-worker results; the coordinator's combined export requires
its own acceptance after applying the provided hooks.
