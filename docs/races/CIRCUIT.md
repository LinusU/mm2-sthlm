# Stockholm Circuit progression

Ten original courses use native Ordered Circuit events (`circuit:0` through
`circuit:9`). They begin with a 567 m daylight block and grow into a 33.65 km
single-lap finale. All positions are exact nodes from the licensed source
snapshot, joined by real road edges. Shared XY coordinates never create a
junction. These designs contain no copied retail race coordinates or artwork.

| Index | Course | Lap km | Amateur / professional laps | Visible gates |
| --- | --- | ---: | ---: | ---: |
| 0 | Kungsholmen Warmup | 0.57 | 2 / 3 | 3 |
| 1 | Vasaparken Lap | 1.70 | 2 / 3 | 7 |
| 2 | SoFo Squares | 3.48 | 2 / 3 | 11 |
| 3 | Royal Rectangle | 3.55 | 2 / 3 | 10 |
| 4 | City Crown | 5.79 | 2 / 2 | 14 |
| 5 | Djurgården Sweep | 6.40 | 2 / 2 | 14 |
| 6 | Söder Summit | 11.49 | 1 / 2 | 22 |
| 7 | Four Districts | 14.40 | 1 / 1 | 25 |
| 8 | Archipelago Grand Tour | 25.98 | 1 / 1 | 41 |
| 9 | Stockholm Marathon — Adapted | 33.65 | 1 / 1 | 51 |

Distances are measured along source-road centerlines, including the final leg
back to the starting node. Gate counts exclude the start line; the native
engine closes each ordered lap at that line. The config separates visible
`start` / `checkpoints` from the dense `route_via` navigation itinerary. The
latter contains the start once, with closure supplied by the exporter. Removing
source-anchor spurs during design prevents forced reversing into a dead end.

The early daylight races teach corners, longer straights, then district-scale
navigation. Later races introduce waterfront approaches, Södermalm elevation
changes, bridge transitions and longer endurance laps. Professional parameters
add rivals or laps where useful. The two longest courses stay at one lap on both
difficulties. Traffic, cops and pedestrians are zero, following the original
Circuit mode convention. A gate must be crossed in order; alternate drivable
lines between gates are allowed, but mandatory water jumps and fabricated
connections are absent.

The design takes its progression cue from the original game's compact opening
courses and longer later loops. The [MM2 Circuit reference](https://racingmadness.fandom.com/wiki/Circuit_Race)
identifies ten events per city, fixed ordered checkpoints and laps, closed traffic
and increasingly difficult courses. The [first-hand MM2 strategy guide](https://gamefaqs.gamespot.com/pc/314069-midtown-madness-2/faqs/36081)
provides period gameplay context. These are design references, not a claim of
retail coordinate equivalence. Native Ordered/start-line/lap behavior is also
explicit in the independent engine's `mm2_content/src/race_def.rs` contract.

## Marathon adaptation

The finale uses the [official 2026 course](https://stockholmmarathon.se/start/banan/)
and [official street itinerary](https://stockholmmarathon.se/start/trafikinformation-2026/)
as its geographic inspiration. It follows central avenues, surrounds the old
town, reaches Djurgården, travels through SoFo, climbs onto Västerbron and
returns through Kungsholmen. The driving loop reconnects these areas on sourced
roads within the approved map boundary. The sequence is adapted for a closed
motor race: it omits outward excursions and the running finish inside Stadion.
It is **33.65 km**, not the certified **42.195 km** running course. No lap count
or coordinate was adjusted to manufacture the official marathon distance.

The full source itinerary and actual native distances are authoritative; the
landmark/street lists in `design` are thematic references, not additional gates.
The northern city content is bounded by the map's E20 policy. The excluded
Essingen islands, Hammarby sjöstad, Lidingö and outward bridges are not required.

## Verification

`tests/test_circuit_races.py` checks the ten native IDs, exact source anchors,
closure on real edges, no immediate reversals, ordered sparse gates, measured
length progression and native lap/traffic parameters. It runs offline without
retail content, an engine checkout or a GPU.

Source graph and config checks alone establish topology and export intent.
They do not demonstrate engine driving, collision clearance, opponent behavior
or visual gate placement. Native completion logs and inspected game screenshots
must be recorded separately against a specific package hash and engine revision.
