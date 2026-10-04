# Pond integration on the textured-road base

Requested base: `bd7566bda9b1e5853df76e56c19b94d1f37816c7`.
The original pond implementation/evidence commit is
`3de43e4d7c43a4b03f6319d3cbd3daed18f9fcef`; its equivalent rebased owned commit
is recorded in `owned-files.json`. Original committed evidence is unchanged.

`integration-hooks.patch` contains only the current-base changes to
`src/expanded.py` and `src/sthlm.py`. It preserves the native road rendering
calls, per-layer/color grouping and source-owned seam methods. The exact
unchanged blob hashes for `road_surfaces.py`, `road_profiles.py`, `elevation.py`
and `bridges.py` are recorded in `road-module-preservation.json`.

Two owned-module safeguards were added while integrating:

- Skansen source ponds way/141431783, way/141431787 and way/141431791 had bank
  collars overlapping neighboring basin floors by approximately 4.5–6 m².
  All basin footprints are now excluded from banks, which are emitted as one
  union surface. Local water-level weights fade continuously to zero at 4 m;
  each basin's own exact rim level is retained. The native triangle-area
  regression detects duplicate collision coverage.
- Basin clipping prefers the emitted `ground_road_surface`, with legacy
  `road_surface` fallback. An upper deck or buried tunnel therefore does not
  cut a hole in a surface fountain. Actual ground-road collision retains
  priority. This relies on the coordinator keeping underground corridors out
  of `ground_road_surface` when integrating tunnels.

The module API remains `normalized`, `footprint`, `prepare`,
`partition_geometry`, `write_mesh` and `write`. No engine changes or physics
implementation are introduced. Apply the shared patch after integrating owned
files; the precise original owned-file list is in `owned-files.json`.

New check logs and native probe commands/results live only in this directory.
The earlier native screenshots remain historical evidence for their recorded
package. Future combined tunnel/landmark exports require their own acceptance.

Final checks pass: formatting, lint, all 122 offline tests, offline build and
package validation (55 parts, 57,657 rooms, 935 textures, 1,272,930 vertices).
The current export retains 57 shallow features and 772 native water
triangles. Both actual Forumdammen and Grubbensdammen drives pass with four
grounded wheels, zero impacts/resets and no water recovery. Full commands and
records are in `native-drives.json`. Package manifest SHA256:
`db8c451679e848ea334626e39bd7479cbecbb19195e17089dda147518a9d918d`.
