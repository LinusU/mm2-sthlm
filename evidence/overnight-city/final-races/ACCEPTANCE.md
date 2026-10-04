# Native race acceptance remains in progress

The baseline Blitz matrix uses immutable package `0c69b55937d4f44ee400220f68a94728338aed55e35409f37f3d1f081f5cf04e` and engine c4156b7. Ten of twenty variants satisfy strict clean full-course acceptance. Recovered finishes and timeouts are failures, retained in `baseline-blitz-0c69/report.json`. The Checkpoint baseline is explicitly partial: nine cases ran, recorded in `baseline-checkpoint-0c69-partial/partial-report.json`.

`blitz-native-semantics` contains separate native rules diagnostics: alternate checkpoint order, an early finish crossing that does not complete the event, and a stationary timeout. The early-finish guide has a steering escape before the crossing and is not clean driving evidence. `blitz-early-clock-probes` retains two clean opening-event pilots with explicit input speed ceilings; these do not establish that every clock is suitable for human players.

`continuous-surface-build` records 232 passing offline unit tests, the full export and native-format validation. Its package manifest is `25e13e8d2e56a15b8b3e817c6e96ea27d14a86ac63cbd2907a670e467011918f`. It includes road field blending, strip seam continuity, same-level bridge overlap handling, internal slab wall cancellation and the Circuit 2 source-flow repair. It does **not** yet include the Barnhusbron cross-layer cap repair. These are map-generation checks, not a clean full-city driving claim.

`source-diagnostics/barnhus-*` retains the exact source-connected layer transition and native floor queries behind the user-reported rounded lip. At the cap the continuous-surface baseline still has overlapping asphalt floors at 16.92213 m and 17.34138 m. This baseline did not pass Barnhusbron acceptance; the later verified repair is documented below.

## Barnhusbron repair verified

`barnhusbron` preserves both reported cameras before the fix, intermediate repairs, and final in-engine captures. The final immutable package checksum is `261fc0b60a272afc7dbff62650956252f2271472b749c5efc78153bf556f185a`; engine revision is `1a822c1cc472f6c04a25a6832e346b162bbb0ff5`. The generator now shares source-connected cross-layer junction fits, blends adjacent tangent fits continuously, and joins railing components across exact source connections. Rails retain clear external approach openings.

The bounded native physics probe traverses the complete 222.13 m source-connected bridge, then departs forwards: 495.1 m total travel, zero resets, no player escapes or reanchors, finite vehicle state and four grounded wheels at the final sample. Two contacts occurred over the whole probe. Four original AI actors remain in the diagnostic. This is bridge traversal evidence, not a completed race or a full-city clean-driving claim. The 241-test offline build and validation also passed. Broader race acceptance remains in progress.

The same verified Barnhusbron package also passes the portable 102-gate waterfront integration check with engine1a822, loads a separately generated second city, and rejects a missing required chunk. Exact commands and identities are under `junction-portability-261fc0b6`. This benchmark does not replace the individual race matrix.
