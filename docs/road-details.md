# Source-driven road details

**Historical implementation:** the current production export uses
[authored driveable asphalt textures](road-surfaces.md) and graph-inferred
movable static signals. The source-node placement and PTH ribbon helpers
described below remain only for old evidence and compatibility tests.
Production `road_details.write` emits a valid empty decal pathset.

The bounded source importer retains `highway=traffic_signals`,
`highway=crossing`, and crossing tags on nodes, including standalone nodes.
The snapshot is regenerated offline from the same cached regional PBF;
its new checksum describes the new bytes. Original PBF identity and acquisition
UTC are retained. Snapshot generation UTC is separate from retrieval UTC.

`road_details.normalized(source, cfg, city)` returns tagged nodes associated
with retained road ways. Assign this to `city["road_details"]` after clipping
roads. `placements(city, height)` returns original signal PKG prop instances
for the shared props pathset. Each `direction` is a world-space endpoint for
native Directed paths (kind 1). Native local +X faces approaching traffic.
`write(out, city, instances=None, height=...)` writes generated art, native
banger tuning, and `city/stockholm/decals.pathset`, then returns signal instances.
It never writes the shared props pathset.

Signal occurrence comes from source tags; road width never creates a signal.
Pole locations are inferred on the right verge because OSM traffic nodes usually
mark a stop line or centreline. A backward signal direction or reversed oneway
changes the inferred verge. These props are static visual signals with red
painted lenses; there is no AI traffic timing or active signal-control claim.
They use original simple geometry with native banger records, not retail art.
NumParts=0 makes them movable native props with no break fragments. Meshes
are centered at CG=(0,1.9,0); native placement restores their ground base.

Lane paint requires an explicit integer `lanes` count of 2–8. All traffic lane
divisions are dashed white rectangles; oneway roads have the same white lane
separation convention and a single lane has no divider. Source road width
sets lane separation distance. `lane_markings=no` suppresses lane paint.
The generator does not invent edge lines, turn arrows, intersection boxes,
stop lines, or lane counts from road width. Ends have an 8 metre unpainted
margin; paint is schematic and has not been surveyed.

Crossing paint requires `crossing=marked`, `crossing=zebra`, or
`crossing:markings=zebra`; an explicit `crossing:markings=no` suppresses it.
Source crossing/signal tags alone do not invent zebra paint. Crossing shape
uses the associated roadway tangent and width; physical stripe dimensions are
an authored visual convention.

All road paint uses native PTH1 kind-2 interleaved ribbon edges and an original
white PNG texture. Engine decals are render-only, with native depth bias and
surface lift. Paint adds no PSDL collision surfaces or driveable geometry.
Heights are evaluated at every decal corner through the caller's terrain/road
height sampler. Offline generator tests require no engine checkout or retail
content. Actual native loading, screenshots and drive commands are recorded under
`evidence/road-details/`; unit tests alone do not constitute visual evidence.

Paint rectangles are grouped with collapsed edge pairs that create zero-area
connecting quads. Files stay within native limits of 4096 paths and 65536
points per path. Tagged nodes farther than 3 metres from retained road
geometry are discarded, including source nodes beyond clipped roads.

The playable `city["bounds"]` polygon rejects outside tagged nodes and
inferred pole positions. Paint requires the complete quad footprint to lie
inside that polygon, so boundary-straddling stripes are omitted. Signal
poles include original yellow collars at 0.55–0.70 and 1.25–1.40 metres.

`surface_height(city, ground, deck)` selects the exported field by source way,
including short raised approaches. Signals and paint carry that source identity
through `road_height(road, x, n)`, so coincident upper/lower roads get their own
levels rather than all markings being lifted onto the bridge.

The final export contains 1,743 signal instances and 21,506 paint rectangles
in three native ribbon paths. Actual engine loading reports no missing,
capped or unresolved paths. A 15.3 m approach drive has zero impacts or resets
and four wheels; it is not a full intersection acceptance test. Native captures
show the source-driven signals and lane paint. One foreground dash is partly
clipped against the terrain/decal plane, recorded in `visual-inspection.json`;
paint rendering still needs local visual refinement.
