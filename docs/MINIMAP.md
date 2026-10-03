# Stockholm minimap

The exporter generates original MM2-inspired map art: cyan water, beige
land, light green parks and thin ivory streets. The supplied San Francisco
and London screenshots are visual references; no retail textures or geometry
are copied. Land and streets follow the same normalized geometry as the
playable map. Green areas come from complete OSM park/garden/nature-reserve,
forest/grass/meadow/recreation and wood/grassland/scrub/heath polygons, clipped
to included land. Building outlines, labels and footpaths are deliberately
omitted from this driving instrument.

`src/minimap.py` supersamples a deterministic 2048×2048 RGB texture. Bounds
are square with identical metres per pixel on both axes. The raster is north
up, normalized coordinates are east/north, and the native map plane is
world east/south. Native PKG V runs bottom up: northern corners have V=1,
which rust-mm2 complements when resolving the PNG. OSM attribution travels
with the map package.

The portable package contains:

- `tune/stockholm.mmhudmap`, including matching ocean color and zoom ranges;
- `geometry/hudmap_stockholm.pkg`, a world-coordinate textured quad;
- `texture/hudmap_stockholm.png`, original generated map art;
- `geometry/hudmap_tri.pkg`, original heading triangle with ten paint jobs;
- `geometry/hudmap_square.pkg`, original twelve-sided dot with nine paint jobs;
- `minimap.json`, bounds, orientation, palette, source coverage and resources.

These use the engine's existing native HUD-map resources. Marker colors are
selected by the engine for the local player, opponents and checkpoint state;
the exporter only supplies the original palettes. In rust-mm2, Tab cycles
inset sizes/off, E switches zoom, F switches north/heading orientation, and
Q opens the pause map. Retail MM2 compatibility remains unverified.

Tests check source park holes/excluded land, north/east orientation, color
classes, equal scale, deterministic minimal-profile fallback, native resource
palettes, world-plane UV correspondence and corrupt geometry rejection.
Actual engine captures are a separate integration check, not replaced by the
raster preview.

## Reproduce the native HUD checks

```sh
./scripts/sthlm build --offline
./scripts/sthlm validate
.venv/bin/python scripts/check-minimap.py --engine "$PWD/.cache/engine/mm2" --capture
```

The script checks a cruise player marker, the circuit checkpoint markers, and
map reloading after a session restart. Captures come from the actual game;
headless records establish resource binding only. They are retained under
`evidence/minimap/` with the package checksum and exact engine revision.

The focused engine presentation fix is
[rust-mm2 PR #3](https://github.com/LinusU/rust-mm2/pull/3), revision
`74c60897ef8472aceafea0bb871f2e46615a095c`. Native map cameras bypass the world's
tone curve and MSAA writeback so the authored palette stays exact and Ocean
Color clears the map viewport. The inset still preserves the world around it.
The patch and checksum are retained under `integration/rust-mm2/`.
Earlier expanded terrain acceptance remains historical for its recorded
package and engine revision; the new HUD evidence identifies this package.
