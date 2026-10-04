# Preserved Blitz baseline: 0c69 / c415

This is diagnostic evidence, not final acceptance. The frozen native package
manifest is `0c69b55937d4f44ee400220f68a94728338aed55e35409f37f3d1f081f5cf04e`.
Engine revision `c4156b780969666f420375d9f5647f51913646a0` has binary SHA-256
`b2f82e39f58ab16032c4fbf59c6a2dc0851a4bbb871ebe32d984e6af788d8742`.
The product parameters, gates, actors and vehicle assets stayed unchanged
through all runs. QA guides are record-ineligible physical driver inputs.

The portable invocation was:

```sh
RUST_LOG=warn,mm2_app::scripted=info .venv/bin/python scripts/check-races.py \
  --family blitz --engine "$ENGINE" --mods "$MODS" --out "$EVIDENCE" \
  --require-finish --workers 1
```

All 20 variants completed their process. Ten passed strict native finish,
all checkpoints, zero resets, zero reanchors, zero escapes and finite vehicle
checks. A native Complete state also occurs after a clock loss; it is not
sufficient evidence of a win.

| Index | Event | Amateur seconds | Professional seconds | Native result / strict acceptance |
|---|---|---:|---:|---|
| 0 | Quayside Quickstep | 41.36 | 41.36 | Both clean finishes |
| 1 | Courthouse Courier | 77.57 | 77.57 | Both clean finishes |
| 2 | Vasastan Coffee Run | 113.79 | 113.79 | Both clean finishes |
| 3 | Kungsholmen Pocket | 139.82 | 139.82 | Both clean finishes |
| 4 | Old Town Dispatch | 200.86 | 200.86 | Finish, 3/3; reanchor/recovery failure |
| 5 | Royal Waterfront | 216.47 | 216.47 | Both clean finishes |
| 6 | Västerbron Dash | 450.00 | 340.00 | Clock loss, 1/4 |
| 7 | Söder Clockwork | 205.94 | 205.94 | Finish, 2/2; one escape |
| 8 | Bridge Landing Express | 460.00 | 345.00 | Clock loss, 0/2 |
| 9 | Stockholm Grand Blitz | 475.00 | 360.00 | Clock loss, 3/4 |

The opening race also passed cleanly with its authored target speed ceilings:
Amateur 14 m/s finished in 81.57 s against 115 s; Professional 17 m/s finished
in 67.97 s against 85 s. These are engineering fairness clues, not human
validation. No clock was tightened around the optimal driver.

Courthouse Courier accepted a true-source alternative guide with the two
checkpoints in reverse order, finishing cleanly in 88.78 s with both banked.
A parked opening-race player lost exactly at 115.00 s with its gate missing,
zero control input, zero reset and no recovery. Gravity rolled the car 8.3 m.

The premature-finish diagnostic drove Hantverkargatan through the finish
before either checkpoint. Native physical snapshots at 32.00 and 35.33 s
were (367,4.1,8) and (321,4.6,0); both remained Running, 0/2 checkpoints,
no result. Their chord intersects the finite finish plane 0.338 m laterally
from its centre and 0.052 m vertically from its height, within its 8.5 m
radius. Console positions are rounded, so this intersection is an inference
from the two deterministic same-input physical runs. One bounded physical
escape occurred earlier at Scheelegatan; there was no reset or reanchor.
This establishes bounded semantic evidence, not clean full-course acceptance.
The first southern-approach diagnostic clipped outside the finite gate and
is retained without a crossing claim.

The preserved failures exposed source geometry defects: Slottskajen's
nearest-road ground field jumped 76 cm over 1 cm, and strip-boundary pins
created abrupt adjacent fan heights on Lilla Västerbron and Hornsgatan.
The Söder Clockwork turn follows legal one-way source edges but the guided
controller held an earlier waypoint after cutting the 116° corner. Slowing
to its 15.6 m/s target still finished in 341.74 s with the same escape.
Generator and controller repairs require fresh native tests before later
clocks can be accepted. No course reroute or clock relaxation substitutes
for those repairs.

## Corrected legal sharp-corner driver isolation

Engine9513edf3d52cd0c2d308eef9ea9f77518fcfacf7 SHA95ef318bef95aa2a2186cb63bdfd15058c1ffccd81e6df9742c9676c49893495, unchanged0c69 package/native clocks/gates/QA guides. Default Blitz7 A/P finish215.23s, both2/2,reset0/no recovery traces,9 contacts each. Source-cap15.6A347.62s leaves62.4s;19P294.56s leaves15.4s; both strict clean with8/4 contacts. All four runs retain finite4/4 wheels and nativeResults. Before/after native product hashes verified. This isolates the controller repair on the original geometry; source terrain repairs remain separately pending. The Professional ceiling has ~5% clock margin, a late difficulty clue requiring human validation, not proof of broad novice fairness.

Reports: native-blitz7-sharp-corners-default/report.json and native-blitz7-sharp-corners-source-cap/report.json beneath /private/tmp/stockholm-blitz-cohort-0c69. Exact physical commands and immutable source hashes included; QA evidence is not player-record eligible.
