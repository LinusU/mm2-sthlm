# Lower-street mesh repair

The road profile was smooth, but its exported collision triangles interpolated
the height of an adjacent upper street across Torsgränd (source way2407293).
One centreline sample was 1.21 metres above its intended profile. Adaptive
height-field tessellation reduces the three reproduced errors below 4 mm.
The offline regression reads the actual emitted road triangles; it does not
merely retest the height sampler. Shared nonlinear material/chunk boundaries
are also covered.

More detailed roads exceed the native 16-bit vertex pool in five chunks.
Whole-room spills preserve native attribute references, water room IDs and
coordinates. The portable city now has 95 parts, within the existing 129-part
limit. Binary round-trip tests cover road quads, fans, facades and collisions.

`comparison.json` records exact package, engine, guide and raw-log hashes. On
the same engine revision, unchanged Circuit 1 Amateur completes two laps and
8/8 gates in 280.07 seconds with zero player resets, escapes or reanchors.
Before the mesh repair it took 299.61 seconds with three escapes at Torsgränd.
Both opponents finish both versions. The repaired run still has 14 whole-run
contacts and one opponent escape; these are disclosed separately from clean
player completion. This comparison does not accept the entire race catalog.

To reproduce the repaired physical test after an offline build, use the
separately built engine revision recorded in `comparison.json`:

```sh
./scripts/sthlm build --offline
./scripts/sthlm validate
ENGINE=/path/to/separately-built/mm2
"$ENGINE" --mods dist --city stockholm --no-profile --car sthlm_racer \
  --event circuit:1 --bot --bot-route dist/stockholm/qa/races/circuit1-a-guide.opp \
  --bot-speed 12 --headless --frames 32681
.venv/bin/python scripts/check-integration.py --engine "$ENGINE" \
  --output /private/tmp/stockholm-portability
```

The viewed native screenshot is explicitly a diagnostic: the lower road core
is improved, but a blue slit remains on the steep paving beside it. The local
road/paving shared vertices agree exactly. A separate engine importer winding
fix is being prepared; do not present this image as complete visual repair.

The 218-test offline suite, complete offline build and package validation are
retained here. The fixture preserves OSM/Lantmäteriet source attribution.
