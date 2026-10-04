# Stockholm Blitz courses

Ten original Stockholm time trials use the native MM2 AnyOrder rule: cross every middle checkpoint in any order, then cross the finish before the countdown expires. START is not an extra required gate. There are no opponents. Native CSV Difficulty remains 1 in both parameter sets; authored rank, traffic, course workload and shrinking clock margins supply the progression. Late courses stay within about six kilometres rather than expanding into endurance races.

| Rank | Course | Suggested km | Gates | Amateur / Professional seconds |
| --- | --- | ---: | ---: | ---: |
| 1 | Quayside Quickstep | 1.10 | 1 | 115 / 85 |
| 2 | Courthouse Courier | 1.98 | 2 | 185 / 140 |
| 3 | Vasastan Coffee Run | 3.00 | 3 | 270 / 205 |
| 4 | Kungsholmen Pocket | 3.38 | 3 | 290 / 220 |
| 5 | Old Town Dispatch | 4.44 | 3 | 365 / 275 |
| 6 | Royal Waterfront | 5.52 | 3 | 445 / 335 |
| 7 | Västerbron Dash | 5.63 | 4 | 450 / 340 |
| 8 | Söder Clockwork | 5.21 | 2 | 410 / 310 |
| 9 | Bridge Landing Express | 5.86 | 2 | 460 / 345 |
| 10 | Stockholm Grand Blitz | 6.05 | 4 | 475 / 360 |

The course descriptions in `config/races/blitz.json` explain the driving rhythm and route choices. Sparse gates define objectives; `route_via` is a complete suggested itinerary through consecutive nodes of retained OSM ways. It is guidance for validation and smoke driving, not an ordered checkpoint restriction. Source owner IDs determine the road elevation at bridges and tunnels. No XY intersection is treated as a junction, no immediate A-B-A spur remains, and no course requires a jump through water or a park.

Clocks currently use the actual source-connected route lengths, target average speeds of 14–15.6 m/s Amateur and 17–19 m/s Professional, eight seconds for the launch, two seconds per gate for braking, then a rank-dependent margin (Amateur 24% falling to 16.8%; Professional 12% falling to 6.6%) rounded up to five seconds. These are transparent initial engineering budgets, **not measured native driving calibration**. Driving acceptance must replace this status with per-event measured completion times, remaining clock, native gate counts and a timeout loss. Traffic settings remain native metadata; their presence is not evidence that traffic was instantiated.

## Primary provenance

Microsoft's 2000 [Midtown Madness 2 manual](https://oldgamesdownload.com/manual/midtown-madness-2-windows-manual-english/) names the classic modes and says the compass points to the nearest checkpoint in Blitz and Checkpoint. Native AnyOrder semantics and separate start/middle/finish rows follow [rust-mm2 race_def.rs at 069768a](https://github.com/LinusU/rust-mm2/blob/069768a/crates/mm2_content/src/race_def.rs), inspected locally. That primary implementation explicitly marks the original retail row conventions as inferred from geometry (WPT-2) and seconds as strongly inferred (BLZ-3); these provenance limits are retained. The same revision's primary [original-rules ledger](https://github.com/LinusU/rust-mm2/blob/069768a/docs/original-rules.md), inspected locally, records ten Blitz rows per original city (RACE-9), no opponents or police (BLZ-2), any-order countdown play from original Help (BLZ-1), and original authored clocks of 25–120/18–103 (BLZ-3). Stockholm clocks are longer map-specific engineering budgets, not copied original clocks. This project relies on that provenance ledger and does not claim a fresh retail-installation audit. No original race layouts or retail assets are redistributed here.

## Acceptance

Offline tests check catalog progression, every suggested graph edge against `sources/expanded/osm.json.gz`, source ownership of gates, absence of immediate reversals and explicit timing allowances. Native wins, alternate gate order, early finish rejection, timeout, marker positions and actual frame captures remain pending external engine integration. A geometry test or physics-only probe does not establish a native race win or in-game visual evidence.
