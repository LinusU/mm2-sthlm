# Stockholm Checkpoint catalog

Ten original Stockholm events graduate from the City Hall neighbourhood to a full-city tour. The native family is `race`, distinct from ordered Circuit. These are races against four to seven opponents with an elapsed clock, not timed Blitz events.

| Native index | Race | Any-order gates | Suggested km | Opponents |
|---|---|---:|---:|---:|
| 0 | City Hall Shuffle | 2 | 2.29 | 4 |
| 1 | Kungsholmen Calling | 3 | 2.55 | 4 |
| 2 | City Lights | 3 | 3.28 | 4 |
| 3 | Royal Appointment | 4 | 5.62 | 5 |
| 4 | Museum Mile | 5 | 6.35 | 5 |
| 5 | South Side Story | 4 | 8.18 | 5 |
| 6 | Northern Exposure | 6 | 9.33 | 6 |
| 7 | Two Banks | 5 | 10.30 | 6 |
| 8 | Island Hopping | 7 | 15.58 | 6 |
| 9 | Stockholm Grand Tour | 9 | 22.39 | 7 |

Distances are source-edge lengths for the authored through-driving itineraries; players remain free to find shorter legal gate permutations, measured on the stable combined expanded graph (8,025 retained roads; normalized JSON SHA-256 `2e553fa930338aa8e78e3f89d97fd136da995a39727f6e979157e9841adb9466`). They are advisory metadata, not a promise of lap time. The shared final generator must recompute route geometry against the retained, boundary-safe graph. Increasing distance is deliberate; gate count can fall when hill/bridge strategy replaces collection complexity.

## Rules and provenance

Original MM2 Checkpoint permits clearing gates in any order; the finish arms only after the complete set. The original game starts with the first three events, unlocking subsequent sets of three for qualifying results. Ten requested Stockholm events retain that structure as 3+3+3+1 rather than inventing two extra events. Amateur requires top three; Professional requires first. Four to seven opponents, fixed event conditions and increased Professional traffic follow original conventions.

Primary rule evidence: the legitimate supplied engine research ledger `docs/original-rules.md`, CHK-1..3, RACE-7..9, WPT-2 and DSN-7, tracing recovered original Help and table observations. Native implementation inspected in `crates/mm2_content/src/race_def.rs`, `mm2_formats/src/racedata.rs`, `mm2_formats/src/opp.rs` and `mm2_game/src/race.rs`; authoring reference revision `b3d9804489bdcd576dd4b85b3f40fec75c545071`. The [Microsoft MM2 manual](https://oldgamesdownload.com/manual/midtown-madness-2-windows-manual-english/) describes using the city map for route planning and the compass pointing to the nearest checkpoint. No original race coordinate data, artwork or opponent files are copied.

Waypoint row roles are inferred from original authored files, rather than explicitly specified in the original manual. The fan engine implements row zero as start, intermediate rows as unordered gates, last row as separately armed finish. `TimeLimit=0` is a neutral, unbound value: this engine binds a countdown deadline only for Blitz. `NumLaps=3`/`4` retains the original Amateur/Professional table template values and is ignored for AnyOrder. Raw `Difficulty=1` retains the original constant; selecting Amateur/Professional chooses the corresponding parameter block rather than reading that column.

## Authoring and export contract

`config/races/checkpoint.json` stores exact OSM node/way ownership for every anchor. The east/north coordinates document the authoring choice; they must never be used to snap across roads, waterways, bridges or tunnels. Resolve the node in the retained owning way, obtaining height from that road profile. Validate every traversed source edge against the full playable boundary and preserve bridge/tunnel ownership. There are no forced tunnel gates.

`races_checkpoint.load(roads=city["roads"])` validates the catalog and retained anchor ownership. `anchors(event)` gives native waypoint row roles; `itinerary(event)` gives the suggested opponent gate order. Player order stays free. Shared routing and export belong to the common race generator; this module does not duplicate them. Export `mmracedata.csv`, `raceNwaypoints.csv`, `raceN.aimap{,_p}` and distinct `raceN-a-M.opp`/`raceN-p-M.opp` opponent lines. The legacy waterfront benchmark is isolated by the root integration fixture so native menu rows remain free.

Each event has a route-choice explanation in its `design` object. Suggested itineraries group same-island gates, reducing repeated water crossings. `opponent_orders` authors up to three competitive source-safe gate permutations; shared export should cycle AI lines through them. Alternate opening plans are capped at 125% of the shortest distance, with extra plans capped at 112%; do not encode the suggested order as a player constraint. Checkpoint columns should have road-width-aware radii, remain separated from the start/finish, and be inspected at the correct elevation in the native engine. Stage opponents on a connected approach without placing cars across a narrow street or on water. Professional target speed is an initial tuning goal, not a measured original-game unit.

## Validation status

Offline source-ownership/schema tests (121 complete repository tests passed at authoring) are independent of engine, GPU, retail installation and network. Runtime acceptance still requires integrated generated race files, native opponent roster loading, finite vehicle movement, elapsed timer and physical gate progress, any-order clearance, armed-finish crossing and marker screenshots. A scripted finish or physics-only run cannot prove playable driving or visuals. Current authored distances are planning evidence; native drive/tuning evidence will be recorded after the common exporter and stable combined package are available.

Opponent plans now use exact-node `route_via` and `opponent_route_via` itineraries with at least 45 m of approach/departure corridor around each gate and no immediate source-edge reversal. Four gates move 23.6–59.5 m along their same named street to gain through access. These guides do not constrain player order. Native AI advances route points within 14 m, so a gate must not sit at a mandatory turnaround or the driving endpoint. A separate 60 m source-connected runout carries each non-circuit guide beyond the visible finish; it is excluded from the gameplay distance.

AI/main QA itineraries exclude unnamed service driveways and non-car path classes; named waterfront service roads remain available where their retained width is at least five metres. The shortest public-street City Hall alternative is the primary guide; native AI traversed that alternative without recovery in the recorded pre-adaptive-surface fixture. Full source heights and coherent-package physical acceptance remain separate requirements.
