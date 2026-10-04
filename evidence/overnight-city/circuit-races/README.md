# Circuit native evidence — 2026-10-04 UTC

Acceptance remains partial. Circuit0 has clean player completions on both levels and an inspected, actually played native finish image. Circuit1 exposes a real Torsgränd road step/gap. Circuit2 exposes a repeated-coordinate navigation defect plus physical recovery hotspots. The full 20-case matrix awaits the repaired coherent package.

## Immutable package before the road repair

Package: `/private/tmp/circuit-final/maps/stockholm`.
`checksums.json` SHA256: `4cdd3f0ec92f9ba04343410951c2b2506755ee4a75488f9aabfd35802e81e457`.
This contains 100 landmarks, 30 courses, corrected source-owner gate headings, 6–15 m gate radii, native HUD and corrected wheel MTX.

Initial matrix engine: `ab5ad9ad98e317aaebeb503305154bb980946bcb`, binary SHA256 `c0b731463dd2568ffd74e42fde54be102fdd6705450121290b254264f40bc1b8`.
Every run uses the real `sthlm_racer`, authored event parameters and AI roster, native guide, and no profile. Runs are serial. The frame budget continues after player finish, so impacts cover the whole run. Missing `p_rec` means zero reanchors/escapes. Finish time is native `sim`.

| Course/level | Frames | Speed ceiling | Native state/laps | Player resets/reanchors/escapes | Impacts | AI finish/escapes | Time | Assessment |
|---|---:|---:|---|---|---:|---|---:|---|
| Circuit0 amateur |16000|10 m/s|Complete 2/2; cp4/4|0/0/0|6|2/2 finish; 0,0 escapes|111.91 s|Clean player traversal|
| Circuit0 professional |18179|10 m/s|Complete 3/3; cp4/4|0/0/0|12|3/3 finish; 0,0,1 escapes|169.35 s|Clean player traversal; AI recovery disclosed|
| Circuit1 amateur |32681|12 m/s|Complete 2/2; cp8/8|0/0/1|33|2/2 finish; 6,0 escapes|285.12 s|Fails clean traversal|
| Circuit1 professional |47221|12 m/s|Complete 3/3; cp8/8|0/0/3|115|3/3 finish; 0,1,33 escapes|435.07 s|Fails clean traversal|
| Circuit2 amateur |63241|12 m/s|Running 1/2; cp7/12|24/24/107|238|3/3 finish; 18,6,7 escapes|1051.02 s elapsed|Fails traversal and finish|

All poses above are finite. Logs are included under `logs/`.

## Played native finish image

[Inspect the actual Circuit0 finish](circuit0-amateur-played-finish.png). Engine source: `f6551353cdc2819389242dd6c0bc8ead6d4a46b6`; binary SHA256: `40d0511a2ec93572bb5761070ec51f5f46bc103dd41c8d5cff5f79d6cbd46000`. Package hash is the unchanged `4cdd…` fixture above.

The exact argv, environment, working directory, image/log hashes and native result are in [metadata.json](metadata.json). The command uses `--bot --bot-speed 10 --frames 9000 --screenshot`, with the strict QA guide. Explicit bot capture drives the player and real opponents through ordinary physics and native gate/lap rules. Static captures without `--bot` retain their frozen-input policy.

The inspected image shows native Race results: player 3rd of 3 at 112.3 s; actual opponents finish at 59.1 s and 66.6 s. The authored amateur event requires two laps to finish. Wheels are attached correctly, the header says FINISHED and minimap gates are cleared. No bounded escape/reanchor INFO traces appear. Visual smoke reports pass, but does not print aggregate reset counters; separate clean headless traversal is recorded above. This image remains evidence before the road repair.

PNG SHA256: `d4f2ce1387487ea9e846a560f6073781306c3da83d34ff4162613a9848e7bab3`. Native log: [circuit0-a-played-finish.log](logs/circuit0-a-played-finish.log). Exact guide and visible gate CSV are in `fixtures/`.

## Located failures and controlled comparisons

Circuit1 trace source `5ce8a8a9a37cf278f1601a612f91f183810c5868` repeats the amateur baseline exactly. At tick 26684, escape 1 occurs at engine `(6.981359,17.222033,-1105.2058)`, speed 1.3056 m/s, heading -2.244136 rad, route index 217, gate `(44.48662,12.83,-1031.6311)`. Source road Torsgränd way 2407293 is 9 m wide; nearby nodes are 270680827 and 9663829953. Normalized north is positive 1105.2058. The inspected native hotspot image shows an abrupt step, walls and a gap under overlapping road surfaces. The course stays intact as a road regression.

Circuit2 cp7 gate `(1938.302494,23.344031,1821.242529)` occurs twice in the dense guide, at indices 62 and 480. The previous controller picks the earliest match, making the later visit aim straight across blocks. Generic source `02cbe4db5d6d7fc27d2c0b2410ffeb4d05876bb7` resolves equal matches by forward route progress. Same package/speed/frame-budget replay reaches cp11/12 instead of cp7/12, but remains Running on lap1/2 with 15 resets,15 reanchors,126 escapes and 302 impacts. All three AI finish; one uses 2 reanchors. This isolates progress beyond the coordinate alias, but is failed physical acceptance. First recoveries occur on Katarina Bangata near way57962308/node300289901; a later off-route recovery occurs near Folkungagatan way1243218624. A subsequent reanchor selects an early itinerary occurrence, compounding recovery failures. Log: [circuit2-a-occurrence.log](logs/circuit2-a-occurrence.log).

The latest engine `73303b00cccb20859b53de0acaa05f09e48abaaf` also includes guided-only spacing-bounded reach and adjacent segment projections, retaining an upcoming corner until the car turns. Native AI 14 m reach stays unchanged. On the same old package, unchanged Circuit1 amateur at 12 m/s/32681 frames finishes 2/2 laps with finite pose,0 resets,0 reanchors,3 escapes,32 impacts and 299.61 s. Both opponents finish; one uses 5 escapes/1 reanchor. All player escapes remain at the same Torsgränd defect, around engine `(7.4,16.9,-1107.1)`. This is the same-engine baseline for the repaired package, not accepted traversal. Log: [circuit1-a-density-old-road.log](logs/circuit1-a-density-old-road.log).

Earlier controller prototype: immutable package `/private/tmp/circuit-acceptance/maps/stockholm`, manifest SHA256 `72d00d00cc2457c6c2261af0c15591a1544a75b5c1831d99fb22a4cbc51adc0f`, had old gate headings/wheel MTX. Circuit0 amateur at 10 m/s/16000 frames with first guide revision 2cca18d stalled with 2 resets/2 reanchors/34 escapes. Projected-controller prototype SHA256 `938b7c924444d4c580d517d8821e03219f7e72c3d2d5172764c323110ff7066c` completed both laps with 0 resets/reanchors/escapes,6 impacts and both AI finished. That binary was dirty prototype evidence; clean ab5 repeats the clean player outcome on package4cdd above.

## Engine integration

Ready PR: https://github.com/LinusU/rust-mm2/pull/6. Separate commits cover strict explicit guides, racing-line reuse, recovery traces, repeated-coordinate targeting, explicit moving capture, and dense guided progress. No physics is copied into map code, opponents are not fabricated, and native checkpoint/lap/timer authority remains in place.

Latest binary SHA256: `bc89accaba0811c5085f9368bbaf05e687fb69431db8b9c48ea166faa30bdb65`. Cumulative patch SHA256: `815f2c280957bb11515cc0fba89b18c0af7c2c60aed2f62880a12a90a8adc03c`. Formatting, strict workspace clippy and all 1,862 workspace tests pass. Existing network tests need loopback sockets. Recovery trace environment is `RUST_LOG=warn,mm2_app::scripted=info`.

The complete city package remains at its recorded immutable path; its global manifest identifies the geometry/assets. Generator/source checks establish topology and export intent. Full physical and visual acceptance requires the repaired package and the complete 20-case native matrix.
