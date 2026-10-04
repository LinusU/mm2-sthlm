# Original race HUD resources

`src/race_hud.py` exports original transparent numeral sprites and navigation-arrow packages with the native names that the external engine consumes. `write_race_hud(output_directory)` returns metadata and writes `race_hud.json`; `validate_race_hud(output_directory)` checks the resources. The root generator calls the writer before package checksums are recorded.

The 22 PNG sprites comprise `texture/digitac_0..9.png`, matching `_half.png` sprites, and `digi_colon.png` plus `digi_colon_half.png`. Full glyphs are 41×56; half glyphs are 21×28. Bevel-ended seven-segment polygons supply ivory digits and yellow colon dots on transparent pixels. Pillow rasterizes independently authored shapes, with fourfold supersampling. There is no font dependency or retail artwork.

The three small PKG3 arrows use `geometry/hudarrow01.pkg`, `hudarrow_blitz01.pkg` and `hudarrow_cc01.pkg`. Each has a centred flat XZ arrow pointing toward negative Z, a family paint (green/red/violet) and a yellow second paint for a target behind the car. The package exporter reuses this project's native PKG3 writer; it does not copy an engine or UI implementation. Existing HUD-map marker resources remain owned by the minimap generator.

The exact stem and binding contracts were read in the pinned engine's [racetime.rs](https://github.com/LinusU/rust-mm2/blob/069768a/crates/mm2_app/src/racetime.rs), [racestat.rs](https://github.com/LinusU/rust-mm2/blob/069768a/crates/mm2_app/src/racestat.rs) and [navarrow.rs](https://github.com/LinusU/rust-mm2/blob/069768a/crates/mm2_app/src/navarrow.rs). Artwork belongs to mm2-sthlm under its project licence. Layout, state, clock authority and 3D presentation remain external engine behavior.

Offline tests check alpha readability, distinct zero/eight middle segments, the native geometry layout, arrow orientation, two paint jobs, repeatable byte output and missing-resource rejection. Actual native GPU capture `/private/tmp/stockholm-blitz-race-hud.png` at engine 069768a on the isolated 55-part baseline showed a readable `1:55:00` clock, checkpoint `1` / `FIN`, the yellow navigation arrow and the existing minimap. Its log reported `smoke=visual status=pass`. That capture establishes native HUD rendering on the baseline package; it does not claim a full driving traversal or verification of later rebuilt packages. Root integration captures and measured race logs supersede this baseline evidence.

The later corrected native capture `/private/tmp/stockholm-blitz-acceptance/blitz0-hud-mtx-native.png` on engine `2cca18d595d711b47d82bde531e5706a67b47ea2` shows `1:49:54`, checkpoint `1` / `FIN`, navigation arrow, minimap and the original Stockholm Compact with its wheels attached. The cloned package began at checksums hash `72d00d00cc2457c6c2261af0c15591a1544a75b5c1831d99fb22a4cbc51adc0f`; applying the root's unchanged-physics original wheel-transform fix produced `cdeeb79edc0a08fa49663eb47f7b3908555d65fbf71bc80ae519828040a95743`. Its log reports actual `smoke=visual status=pass`; the earlier detached-wheel frame is preserved separately as a failed visual diagnostic.

A preserved copy of that corrected native frame and log is in
[evidence/races/blitz/hud](../../evidence/races/blitz/hud/). Root inspected the
frame: wheels are attached, the stopwatch is readable and the minimap and
navigation arrow render. This is visual evidence only, not a race finish.

The source-oriented native checkpoint banner, corrected car frame and parked
timeout proof are retained in [the UI evidence manifest](../../evidence/races/blitz-native-ui-evidence.json).
Root inspected the waterfront frame: the CHECKPOINT arch crosses the street,
its label is readable below the stopwatch and the minimap/navigation arrow
remain visible. These captures retain their isolated fixture hashes.
