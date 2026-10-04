# Herkuleskopplet highway entrance

Reported camera: `918.3,10.2,-154.8,125,-18`.

OSM building `way/424972071` has only `building=yes`. Its estimated 6.4 m
body was founded at 3.39 m, intersecting nearly 10 m of road `4695823`
(Herkuleskopplet). The source road's sloping deck is approximately 8–9 m here.

`config/overrides/building-passages.json` explicitly replaces that inferred
solid body with a thin overhead volume. Its underside clears the highest
sampled road surface in the crossing by 5.5 m; the body is 1.5 m thick.
These are schematic gameplay dimensions, not surveyed architectural heights.
The original footprint, road geometry and neighbouring buildings are retained.
The volume includes downward-facing underside triangles for visibility below.

The archive reference in the override provides historical context only.
No archive photograph or licensed image was copied into the package.
Source fixture attribution: © OpenStreetMap contributors (ODbL),
© Lantmäteriet (CC BY 4.0).

## Reproduction

Generate and validate the independently built map:

```sh
./scripts/sthlm build --offline
./scripts/sthlm validate
```

Set `ENGINE` to a separately built rust-mm2 executable. The exact tested engine
revision and package checksums are recorded in `manifest.json`.

```sh
"$ENGINE" --mods dist --city stockholm --event checkpoint:0 --car sthlm_racer \
  --headless --bot --bot-route evidence/road-passages/herkuleskopplet/source-guide.opp \
  --spawn '935.49440,7.93547,-162.45373,124.10985' \
  --frames 900 --bot-speed 8 --no-profile
"$ENGINE" --mods dist --city stockholm --car sthlm_racer \
  --cam '918.3,10.2,-154.8,125,-18' --no-hud --frames 24 \
  --screenshot /tmp/herkuleskopplet.png --no-profile
```

This is a bounded real-physics approach test with an 8 m/s diagnostic speed
ceiling, following connected source road centre-lines. An event is required by
the engine's evidence-driver CLI, but this guide is outside the event's gates:
it does not claim a race finish, full highway acceptance or vanilla MM2 testing.
The native screenshots are actual rust-mm2 window captures; the headless logs
are driving evidence, not rendered visual evidence. The before/after runs use
identical driving arguments and frozen packages.

## Results and limits

- All 265 offline tests pass; formatting, lint, full offline build and native
  package validation pass (92 parts).
- Identical 900-update entrance runs: before travels 51.7 m but remains at
  `(909,8,-149)` near the blocker with two impacts and one escape; after travels
  88.7 m to `(867,12.6,-109)` on the ascending ramp with four wheels in contact,
  zero impacts, zero resets and zero escapes.
- Full decoded native collision walls crossing the road now start at
  14.4274 m and end at 15.9274 m, replacing ground-founded walls at
  3.3915–9.7915 m. Clearance is measured against the unchanged ramp profile.
- The longer 1500-update after run travels 138.7 m with no reset, but includes
  one escape. Its info trace locates this farther along the curved ramp at
  `(857.51,14.01,-76.28)`, tick 2160; this remains a separate follow-up. The
  before run has a recovery reset and two escapes. Both logs are retained.
- The additional 1800-update before diagnostic is also retained. A `status=pass`
  engine smoke field means simulation completed, not that the drive was clean.

`after-native.png` is the matching reported camera. `underside-native.png`
looks up from the same position to check the overhead volume's lower face.
