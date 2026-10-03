# Playable road profiles

The terrain source stays unchanged. Road beds are a separate derived surface:
DTM ground samples are not measurements of asphalt or elevated decks.

Ordinary roads use five metre centreline samples. A five sample longitudinal
median rejects isolated returns; graph diffusion has an approximately 25 m
footprint. The graph joins exact OSM node identities, including interior nodes,
never nearby XY crossings. This removes street-scale noise while retaining
broad Stockholm hills. A constant eight percent, 300 m hill with an eight metre
DTM spike is a focused regression: its 24 m rise survives and the spike does not.

Convex projections target at most 16 percent longitudinal grade and 0.003 per
metre vertical curvature. These are gameplay estimates, not surveyed street
limits. Twelve thousand deterministic iterations resolve almost all constraints;
short segments can retain small numerical residuals. Reports show actual values,
not just configured targets. Connected bridge ends stay fixed to the separately
estimated bridge anchors. Bridge components follow source connectivity rather
than names, so unnamed viaducts and separate parallel decks can be represented.

Cross sections project onto their own source road. An unrelated nearby upper or
lower street cannot attract a road edge. At genuine source-connected junctions,
the global fallback field uses one fitted local tangent plane; its gradient
preserves the hillside grade. The graph solver also reconciles the first connected
samples to a common tangent plane. A seven metre smoothstep transition joins the
fallback patch to the ordinary field. Forcing every hill junction level was rejected because closely spaced
junctions would flatten steep Stockholm streets. Junction plane membership is
restricted to the connected source ways. Source-aware asphalt samples stay flat across the road. Terrain shoulders still
blend to the independent ground source.

`RoadField.height_for_road(source_id, east, north)` samples the cached source
profile. Passing the road record instead samples its current profile, preserving
the post-elevation authored Kronoberg descending dead end. That explicit override
also bypasses fitted junction planes. `RoadField.height_at_station(road_record, metres)` gives both corners of one
native road cross section the same solved height. Native strips should use this
station API: an XY projection at a bend can reach an adjacent segment of the same
way and introduce cross-section twist. The global field remains available for
fallback junction fans, land and shoulders.

## Reproduce the inventory

```sh
./scripts/sthlm build --offline
.venv/bin/python scripts/check-road-profiles.py --output /tmp/road-profiles.json
./scripts/sthlm validate
```

The inventory reports centreline grade, vertical curvature, actual sampled source
surface grade/curvature, XY-projection crossfall, crossfall change, same-segment
quad warp and shared endpoint
mismatches. It includes all bridges, while ordinary profile constraint counts
exclude decks. A geometric crossing without a shared OSM node is tested separately
from a junction. Full unit regressions also cover shared planes, bridge approaches,
terrain/material boundaries and the existing authored descending driveway.

On the original 7,375 ordinary-way normalization at revision `3724732`, the old
terrain-conforming profiles had 287 ways above 16.01 percent grade and 2,367 above
0.0031 per metre curvature. Worst grade was 65.48 percent at Tomtebodavägen; worst
curvature was 0.31070 per metre. The final source profiles with junction tangent constraints have two ways above
16.01 percent (maximum 16.08 percent at Lästmakargatan) and 155 above 0.0031 per
metre. Worst residual curvature is 0.01983 per metre at a very short Krukmakargatan
interval with only 3.17 percent grade. The targets are not strict solved bounds;
remaining residuals must be checked against actual native geometry and driving.
The median absolute change from DTM is 0.079 m, p90 0.378 m, p95 0.550 m, p99
1.079 m, maximum 7.988 m. These exclude decks and the authored driveway.
Bastugatan retains a 9.06–41.76 m range (raw DTM 8.02–42.43 m), Fleminggatan
5.75–23.29 m (raw 5.75–23.31 m), and Hantverkargatan 3.33–28.38 m
(raw 1.59–28.67 m). Brännkyrkagatan retains its major hill at 33.33 m. These are
centreline numerical results; they do not constitute native visual or vehicle
proof. The expanded bridge import and clearance adjustments require their own
final integrated inventory.

## Native verification

Use the exact tested engine binary listed by the integration lock, with this
worktree's generated `dist` as its mod directory. A headless vehicle run proves
physics only. Screenshots must be captured by that engine's native renderer.
A diagnostic spawn is an isolated road probe; it does not replace the continuous
full benchmark loop and must never be reported as a zero-reset course completion.

Required project gates are Ruff format/check, the complete unittest suite, offline
build and validate. Initial isolated smoothing validation passed 93 tests; the final source-cache
regression adds one more. Native
probe results and final integrated build results belong alongside the complete
crossing clearance report; this document's numerical baseline remains explicitly
scoped to the original normalization.

### Isolated native evidence (4 October 2026)

Final isolated gates passed: Ruff format/check, all 94 unit tests, offline build,
and validate (55 parts, 1,088,159 vertices, 1,806,621 triangles). The existing 1,527 m
benchmark route remains present. This package still uses the original RoadFan
renderer; the final integrated native road primitives require separate acceptance.

Physics used the unchanged engine revision
`b3d9804489bdcd576dd4b85b3f40fec75c545071` with the isolated package:

| Diagnostic drive | Frames | Travel | Time | Impacts | Final contacts | Resets |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tomtebodavägen uphill | 200 | 5.6 m | 3.33 s | 0 | 4/4 | 0 |
| Brännkyrkagatan uphill | 300 | 21.9 m | 5.00 s | 0 | 4/4 | 0 |
| Pustegränd toward upper junction | 260 | 13.9 m | 4.33 s | 0 | 0/4 | 0 |

All three records are finite. **Pustegränd's final zero wheel contacts is an open
acceptance flag**, not a fully grounded pass; repeat on the final integrated
primitive package and distinguish crest airtime from a surface defect. These
isolated diagnostic spawns do not establish a complete benchmark drive.

Reproduce the physics with the engine's `--mods <isolated-worktree>/dist --city
stockholm --headless --no-profile`, plus the following arguments:

```sh
--spawn=-1057.383,14.058,-1745.033,-114.449 --frames 200
--spawn=1282.838,13.377,877.899,102.529 --frames 300
--spawn=1279.481,10.916,862.893,-167.393 --frames 260
```

The exact same engine's native GPU renderer captured these inspected views;
these are not standalone viewer images. Asphalt appears continuous and the
Brännkyrkagatan uphill profile remains visible. The image HUD shows four wheel
contacts in both parked captures.

- `/private/tmp/smoothing-native-tomteboda.png`
- `/private/tmp/smoothing-native-brannkyrka.png`

Both native image logs contain `smoke=visual ... status=pass`. Reproduce with
`--mods <isolated-worktree>/dist --city stockholm --no-profile --parked`, adding:

```sh
--spawn=-1057.383,14.058,-1745.033,-114.449 --cam=-1074,31,-1754,-114.449,-25 --frames 20 --screenshot tomteboda.png
--spawn=1282.838,13.377,877.899,102.529 --cam=1300,32,874,102.529,-20 --frames 20 --screenshot brannkyrka.png
```

Metal access required execution outside the filesystem sandbox. Scoped records
are `/private/tmp/smoothing-drive-{tomteboda,brannkyrka,pustegrand}-final.log`
and `/private/tmp/smoothing-native-{tomteboda,brannkyrka}.log`.
