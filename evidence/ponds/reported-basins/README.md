# Reported elevated paddling pools

Reported screenshot: `screenshots/1791069201465_cam_498.0,27.1,-1095.3,-70,-14.png`.

The reported holes are OSM basins `way/338452356` and `way/697302459`.
The current package already contains the shallow-water implementation, integrated
in `df06587`; this report needed verification rather than another mesh change.
The reported image is consistent with an earlier package lacking these floors.
The exact package used in the user's running game is unknown.

`current-native.png` is an actual rust-mm2 capture at the reported camera on
package 8dc0d56c. Both water surfaces are visible. `native-floor-query.json`
decodes the exported PSDL, proving submerged floors at 24.66019 m and
26.04701 m, 20 cm below each local water level. Neither room is a deadly-water
reference. These are authored gameplay depths, not surveyed bathymetry.

A direct straight-ahead physics test starts south of the pools at x=510 and
crosses both. At 450 updates it is entering the northern basin; at 600 updates
it has passed both and is on the northern bank:

- 45.9 m travelled, zero impacts, zero resets, finite simulation.
- Final native position `(510,27.4,-1125)`, four wheels in contact.
- No water recovery or escape manoeuvre.

The initial event-bot attempt did **not** test the pools. Its gate was behind
the diagnostic guide, so the evidence driver aimed southwest toward the race
checkpoint and made two escape manoeuvres. Those failed probe logs are retained,
with `northbound-rejected-guide.opp`; they are not presented as pond acceptance.
The accepted direct test uses the engine's normal headless held-throttle driver,
no event, custom vehicle handling, teleports, or scripted route.

## Reproduce

Build this independent package, then point a separately built engine at `dist`:

```sh
./scripts/sthlm build --offline
./scripts/sthlm validate
"$ENGINE" --mods dist --city stockholm --car sthlm_racer --headless \
  --spawn '510,23.77224,-1081,0' --frames 600 --no-profile
"$ENGINE" --mods dist --city stockholm --car sthlm_racer \
  --cam '498.0,27.1,-1095.3,-70,-14' --frames 24 --no-hud \
  --screenshot /tmp/stockholm-paddling-pools.png --no-profile
.venv/bin/python evidence/ponds/reported-basins/probe-native.py dist/stockholm
```

Restart the game after replacing/rebuilding its loaded package. All 265 offline
tests and the required build/validation gates passed for this unchanged package
in `evidence/road-passages/herkuleskopplet/`. No map code or engine code changed
for this verification. This is rust-mm2 evidence, not vanilla MM2 evidence.
