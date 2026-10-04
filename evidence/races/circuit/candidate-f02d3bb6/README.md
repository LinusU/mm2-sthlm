# Targeted Circuit bridge candidate tests

Immutable package manifest `f02d3bb6f52236bedf7633e91e8a420ead0568c8eca73f849c2eaf80196e8004`, engine `1a822c1cc472f6c04a25a6832e346b162bbb0ff5` / binary `144389d3eae590932dffc6cf55667c093bd4a6a67e905b0bc11e8c91728bec19`. QA ceiling12m/s; unchanged native laps, gates, clocks, rosters and physical vehicle. Source-distance budgets were not truncated. No profile records saved.

Three complete cases, one strict pass:

|Case|Player/native field|Player resets/reanchors/escapes|Result|
|---|---|---|---|
|Circuit4 Amateur|Finished,15/15gates,2laps; all4AI finish|0/0/6|Fail: first fault at Strömbron, before pending parallel-profile repair|
|Circuit5 Amateur|Finished,15/15gates,2laps; all4AI finish|0/0/0|Pass; AI2e/0/1e/1e1r disclosed|
|Circuit5 Professional|Finished,15/15gates,2laps; all5AI finish|0/0/1|Fail: one Dag Hammarskjölds Väg bounded escape; static audit finds continuous floor and no nearby collision wall/PKG|

Circuit4 Professional was cancelled shortly after automatic scheduling and is excluded. The original focused Circuit5 runner prints a hardcoded twenty-case denominator; its JSON contains only two runs. `summary.json` identifies all three completed cases and opponent recoveries. The global impact counter includes the whole scene, not only the player. A player Results screen and full-field RacePhase Complete are recorded separately.

Inspected native played screenshots and exact commands/hashes are in `screenshots/metadata.json`: Circuit0 Amateur native active lap1/2 and checkpoint1/4 with opponent markers, plus actual98.3s third-place finish with both native AI results. Windowed visual logs do not provide aggregate reset counters. These captures establish native game presentation, not twenty-course physical acceptance.
