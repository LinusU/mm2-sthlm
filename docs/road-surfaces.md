# Authored driveable asphalt surfaces

This workstream replaces production `PTH1` road-paint ribbons with markings
inside original deterministic asphalt textures on native driveable PSDL strips.
`road_details.write` keeps a valid empty decal pathset for package compatibility;
legacy ribbon functions remain for historical evidence/tests, not production.

## Native UV evidence

Inspected separate rust-mm2 checkout `/private/tmp/mm2-sthlm-fan-engine`:
`crates/mm2_app/src/city.rs` defines `PLANAR_UV_SCALE=8` and
`ROAD_TILE_LENGTH=10`. `RoadFan` invokes `fan`, using world XZ/8 UVs;
`RoadNoSidewalks` (attribute kind 2) invokes `strip_uv` with `chain_u`,
length/10 along u, v=0..1 across the full roadway. Thus painted lane textures
must use native strips. The generator never paints directional lane stripes
onto world-mapped RoadFans. Native strip code `0x92` holds two cross-sections
and four vertex references. It creates native road collision and road spawn
candidates in the loader.

`road_surfaces.render(writer, city, geom, height, road_height=None, station_height=None, bridge=False, triangle_sink=None)`
reserves disjoint 10 m strip quads fully contained in the exported road union.
Road IDs resolve overlap deterministically. Junction interiors and sharp curves
remain plain asphalt fans. The generator subtracts every strip footprint from
the fan remainder, so roads have no stacked coincident collision planes.
The union of strips and fan remainder preserves the source road footprint.
Chunked writers receive strip rooms through `writer.part`. Fan boundary heights
are constrained to the exact native quad edge planes, including inserted 5 m
fan vertices, closing vertical T-junction seams. An optional `triangle_sink`
list captures exact rounded native XYZ-south faces for bridge underside construction;
quad diagonals follow native `(0,1,2),(2,1,3)` rather than guessed fan triangles.

The optional `road_height(road,x,n)` samples source-specific corner heights;
base roads should use `RoadField.height_for_road(road,x,n)`. Bridges use the
same exported deck/ramp selector as their driveable surfaces. Root integration
owns the shared `sthlm.py` hooks and validator support for kind-2 strips.

## Classification and authored designs

Lane count uses valid explicit tags, otherwise road width and one-way status;
major wide roads can receive four lanes. Narrow local/service/living streets
remain unmarked; `lane_markings=no` always wins. Paint is off-white, asphalt
is neutral grey aggregate. Asphalt uses an original built-in ImageGen raster saved at
`assets/materials/roads/asphalt-original.png`; its exact prompt and provenance
are in `assets/materials/roads/provenance.json`. Source pixels are preserved,
resized offline to 512px, then painted using original seeded Pillow masks.
No Google, retail, or stock-photo source art is used.
Textures are regenerated offline, deterministic, and have no network dependency.
The texture material list includes `tunnel_roads`; underground geometry must
call `render` with a separate component-only city and height field, so it never
merges into overlying roads by XY position.
Fullwidth physical stripe width is 0.12m with an authored 3m dash/7m gap.
Widths quantize to 0.5 m for a bounded material set.

The shared-node graph identifies unique neighboring edges rather than crossing
coordinates. Four-way major junctions and primary/secondary T junctions receive
static signal approaches, local T junctions use a priority design, local
intersections remain unmarked, and roundabouts do not infer signals. A few
accepted approach cells receive zebra stripes and an incoming-half stop line.
These are visual urban design conventions, not a claim to reproduce surveyed
lane allocations or legally complete signage.

Signals no longer depend on exact OSM traffic-signal node locations. Pole
footprints must clear the road union and building footprints; bounded setback
adjustments preserve the verge, and obstructed poles are omitted. Each
incoming arm has an inferred pole on the arriving driver's right verge, facing
approaching traffic; outbound one-way arms are suppressed. Signal poles remain
native movable `dgBangerData` props. The red lens is static visual artwork;
no unsupported generic signal cycling or AI obedience is claimed.

Primary visual-convention references (read 2026-10-03):
[Transportstyrelsen road markings](https://www.transportstyrelsen.se/sv/vagtrafik/trafikregler-och-vagmarken/vagmarken/vagmarkeringar/),
[M13 stop line](https://www.transportstyrelsen.se/sv/vagtrafik/trafikregler-och-vagmarken/vagmarken/vagmarkeringar/stopplinje/),
[M15 zebra crossing](https://www.transportstyrelsen.se/sv/vagtrafik/trafikregler-och-vagmarken/vagmarken/vagmarkeringar/overgangsstalle/).
The references identify design classes; dimensions and classifications are
original authored approximations.

## Recoverable workstream state

Isolated worktree: `/Users/linus/.codex/worktrees/overnight-road-surfaces/mm2-sthlm`.
Own code: `src/road_surfaces.py`, `src/road_details.py`, road tests, this document.
Local `src/sthlm.py` changes are temporary hook validation, owned/integrated by
root separately. Final isolated gates passed:97 unit tests, Ruff format/check, full offline build,
and validation of 55 PSDL parts / 55,288 rooms / 1,227,110 vertices / 1,987,857 triangles.
Base roads include 16,372 marked native strips; bridges 328. There are 1,419 native
movable static red signals after clearance checks omit obstructed verges.
All 55 native import reports have 0 rejected attributes and 0 missing textures.
Production imports 0 render-only paint ribbons.

Actual Stockholm capture `evidence/road-surfaces/stockholm-road-surfaces.png`
shows oriented aggregate asphalt, center/lane markings, zebra and stop line,
with the inspected fan/strip edge gaps closed. The former pole in the crossing
road is moved/omitted by clearance checks. Native synthetic crossroads capture
`native-crossroads-asphalt.png` proves the UV convention on controlled geometry;
it is separate from Stockholm geographic evidence. Both are normal in-engine
renders, not standalone viewers. The pinned engine revision is
`b3d9804489bdcd576dd4b85b3f40fec75c545071`.

A native actual-car approach drive travels 15.1 m in 4 seconds, has 0 impacts,
0 resets and 4/4 wheel contact. This is a short local approach, not a full
intersection crossing or whole-city driving acceptance. Exact commands, loader
reports, checks and hashes are in `evidence/road-surfaces/acceptance.json`.
The combined smoothing/bridge/tunnel integration still needs root's full gates
and final native acceptance; these workstream captures use the isolated baseline.

## Integrated source layers

The coordinator's exporter calls `render_bridge_layers` to retain stacked bridge
roads as separate surfaces. Each source layer has its own union, height field and
captured native facets. Raised approach pieces inherit the connected bridge
layer. The underside uses those exact facets, so its top remains four centimetres
below asphalt rather than cutting across curved roadway triangles.

Source-station heights give both corners of each cross section one solved level.
Approach seam tangent planes belong to their source road; a nearby lower road
cannot inherit an upper ramp's height. A synthetic stacked crossing and an
unrelated lower-road seam are explicit regressions. Numerical clearance alone
is not acceptance: upper/lower native driving probes are required too.
