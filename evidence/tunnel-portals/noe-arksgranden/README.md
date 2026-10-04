# Noe Arksgränden / Söderledstunneln entrance

Reported camera: `1526.3,26.9,1381.9,102,-18`.

The checked-in OSM source connects Noe Arksgränden (`1113147180`,
`1113147216`) to tunnel branch `27351663`. The branch turns sharply north
rather than running straight through the wall facing the reported camera.
The generic one-lane width estimate was 5 m: its generated walls trapped the
car at the bend. Göta Arkhuset (`way/37280553`) overlaps the subsequent bore
and was also exported as a solid building across it.

An authored 7.5 m corridor for this branch provides turning room. Other tunnel
widths retain their existing rules. The original source nodes, centreline,
connections and elevation profile are retained. The lower building footprint
is partitioned around that corridor with a 0.6 m side margin and 5.5 m opening
clearance; the original upper footprint and roof elevation remain. A downward
concrete soffit makes the passage visible from below. These are schematic
playable dimensions, not surveyed construction dimensions.

The nearby `way/1446030638` footprint does not overlap this road; its bounding
box alone was misleading. It is unchanged. Fully buried neighbouring buildings
are not given unnecessary openings.

Source attribution: © OpenStreetMap contributors (ODbL), © Lantmäteriet
(CC BY 4.0). No reference photographs are copied into the package.

## Reproduction

```sh
./scripts/sthlm build --offline
./scripts/sthlm validate
RUST_LOG=info "$ENGINE" --mods dist --city stockholm --event checkpoint:0 \
  --car sthlm_racer --headless --bot \
  --bot-route evidence/tunnel-portals/noe-arksgranden/source-guide.opp \
  --spawn '1534.91892,24.70179,1377.95718,104.99829' \
  --frames 1600 --bot-speed 6 --no-profile
"$ENGINE" --mods dist --city stockholm --car sthlm_racer \
  --cam '1526.3,26.9,1381.9,102,-18' --no-hud --frames 24 \
  --screenshot /tmp/noe-arksgranden.png --no-profile
.venv/bin/python evidence/tunnel-portals/noe-arksgranden/audit-native.py dist/stockholm
```

Set `ENGINE` to a separately built rust-mm2 executable. The guide follows the
source-connected branch and exercises real vehicle physics; it is not a race
completion test. Native window screenshots are visual evidence. Exact engine
and package checksums and bounded test results are recorded in `manifest.json`.

Baseline: 49.8 m travelled, eight impacts, four escape recoveries and one reset.
The car repeatedly stalled around native `(1494.3,24.2,1381.1)` at the tight
turn. The entire failed baseline log is retained.

## Results and limits

- All 268 offline tests, formatting, lint, full build and validation pass.
- Identical 1600-update 6 m/s test: 137.2 m travelled, zero resets, no bounded
  escape/re-anchor messages, finite state, four wheels in contact at the end
  at native `(1469,15.5,1291)`. Two impacts remain, so this is not a claim of
  collision-free driving. The initial 500-update approach travels 28.0 m with
  zero impacts; the contacts happen farther into the turn/bore test.
- A slower 4 m/s run travels 91.9 m, also with zero resets, two impacts and
  four wheels in contact. This confirms the opening is usable at both speeds,
  without establishing an exact cause for the remaining contacts.
- Decoded native facade collision crossing the branch centreline starts at
  29.61141 m instead of 17.95663 m; original top remains 77.95663 m.
- `after-native.png` repeats the reported camera. `entrance-native.png` looks
  around the turn; `bore-native.png` shows the clear descending corridor under
  the crossing street. All are native game-window captures, not a viewer.

The remaining concrete walls and opening are simplified geometry. This bounded
entrance test does not verify the entire Söderledstunneln network, architectural
accuracy, overhead street drivability, all vehicle sizes, or vanilla MM2.
No engine changes were required for this fix.
