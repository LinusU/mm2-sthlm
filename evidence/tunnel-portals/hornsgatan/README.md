# Hornsgatan / Söderledstunneln building openings

Reported camera: `1381.5,21.3,931.1,-165,-17`.

The imported office footprint `way/27738982` was exported as a solid building
across tunnel ramp `1244140460` and neighbouring ramp `17151920`.
The connecting roads and tunnel profiles already exist in the source package.
Their source connections are Hornsgatsavfarten (`88293606`) and Hornsgatspåfarten
(`88293603`), respectively. OSM tags distinguish the off-ramp and on-ramp.
The reported inward test uses the off-ramp in reverse as a diagnostic; traffic
one-way tags remain unchanged.

The `cutout` mode in `src/building_passages.py` partitions the lower office
footprint around authored road corridors while retaining the entire upper
footprint and original roof height. Opening widths follow each source road's
width plus a 0.6 m side margin. Clearance is 5.5 m above the highest sampled
road surface within the footprint. A concrete soffit is visible from below.
These are schematic gameplay dimensions, not surveyed architectural details.
The lower building remains outside the openings; the structure is not replaced
with a floating full-width beam. Road geometry, heights and vehicle physics
are unchanged.

Reusable authored rules live in `config/overrides/building-passages.json`.
For future road/building collisions, confirm the source connection and vertical
layer before adding a rule; a fully buried tunnel can safely pass below a
building without requiring a ground-floor doorway. Merely nearby roads do not
justify removing facades.

Location reference: [Trafiken.nu's Hornsgatan tunnel ramp report](https://trafiken.nu/stockholm/trafikinformation/11700738/hornsgatan-vid-pafart-soderledstunneln-fr-hornsg-mot-medb-platsen/).
This supports ramp location, not exact opening dimensions. No reference imagery
was copied. Source data: © OpenStreetMap contributors (ODbL), © Lantmäteriet
(CC BY 4.0).

## Reproduction

```sh
./scripts/sthlm build --offline
./scripts/sthlm validate
"$ENGINE" --mods dist --city stockholm --car sthlm_racer --headless \
  --spawn '1381.2,19.28,931.1,195' --frames 600 --no-profile
"$ENGINE" --mods dist --city stockholm --car sthlm_racer --headless \
  --spawn '1342.29596,20.61367,941.45676,194.38292' --frames 600 --no-profile
"$ENGINE" --mods dist --city stockholm --car sthlm_racer \
  --cam '1381.5,21.3,931.1,-165,-17' --no-hud --frames 24 \
  --screenshot /tmp/hornsgatan-portal.png --no-profile
.venv/bin/python evidence/tunnel-portals/hornsgatan/audit-native.py dist/stockholm
```

Set `ENGINE` to a separately built rust-mm2 executable. Exact tested engine and
package revisions are recorded in `manifest.json`. Native window screenshots
are rendered evidence. Headless logs test real vehicle physics with held
throttle, not a scripted race completion or a full tunnel-network acceptance.

## Results

- All 266 offline tests, formatting, lint, full build and validation pass.
- Before: reported approach stops at the office after 15.2 m, with two impacts;
  west on-ramp stops after 9.0 m, with one impact.
- After, identical 600-update held-throttle tests: 139.2 m and 139.8 m travelled,
  respectively. Both have zero impacts, zero resets, finite state and four
  wheels in contact at the end, inside the descending tunnel roads.
- The four building wall colliders crossing ramp centre-lines start at
  26.37325 m instead of 19.00113 m; their original top remains 38.20113 m.
  Lower solid walls remain outside the road corridors.
- `after-native.png` matches the reported camera. `upper-storeys-native.png`
  looks up from the same position (pitch 5°) to verify the retained building
  above the opening. These are native engine window captures.

This verifies these two mouths and bounded inward driving, not all Stockholm
road/building intersections or the entire tunnel network. It does not establish
vanilla MM2 compatibility. No new engine changes were needed.
