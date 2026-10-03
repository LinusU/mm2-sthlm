# Kronoberg source overrides

`config/overrides/kronoberg-details.json` targets only source ways 99763084,
390454703, and 127586369 from the offline expanded OSM snapshot.

The private driveway keeps its original two nodes, including its existing dead
end. Its authored 4 m descent over approximately 47 m matches the user photo's
lower access lane. This is a visual estimate, not a surveyed height or inferred
underground tunnel. The entrance uses the ordinary elevation system's shared
source-node height. Its local shoulders blend the lowered surface into the DTM.
A low cap makes the source termination visible and physically closed.

The control hut keeps its source footprint and becomes a 3 m glazed single-storey
structure: white lower panels, dark frame, overhanging dark roof fascia. Dimensions
are authored from the supplied photograph.

The exact urinal source footprint and tags remain in normalized street-detail
metadata, while the fixed building is removed. An original octagonal PKG mesh
uses a narrow 1.7 m footprint, light-grey panels, dark uprights, an open entrance,
shallow roof and vent. Thin panels and roof carry both windings so native
backface culling keeps them visible inside and outside; one entrance remains
open. Original procedural grey aggregate speckle textures the panels. Its native banger has NumParts 0, no BREAK chunks, mass
160 kg and ImpulseLimit2 0. The existing engine activation path therefore moves
the intact prop on contact instead of replacing it with fragments. No engine or
vehicle physics are implemented here. Placement coordinates use ground height;
the native record supplies the centre of gravity at half the body height.

Integration order: `apply(city)` before `elevation.apply`, then
`wrap_field(road_field, city)` after elevation. The wrapper preserves the prepared
base field, including bridge separation and shared-junction metadata. Skip buildings annotated with
`street_detail` in the normal building loop; call `render(writer, city, ground)`
for custom hut/cap surfaces. Call `write(out, city, ground)` to generate original
textures/PKG/tuning and append returned instances to the shared native pathset.
Tests check exact source targeting, retained source metadata, unchanged graph,
shared entrance height, descending ramp profile, ground cut, and intact prop art.

Actual engine commands and captures are in `evidence/street-details/`.
The ramp drive covers 41.8 m, reaches the intentional dead-end cap, records
four contacts and finishes finite with four wheels and no resets. The urinal
impact probe activates one intact movable body, passes its original position,
and finishes finite with four wheels and no resets. The parked screenshots
verify its appearance; the physics log establishes activation, not a captured
knock-over animation.

Open thin-panel native props require the generic convex intact-body fix in
rust-mm2 PR #4. Engine `b3d9804489bdcd576dd4b85b3f40fec75c545071` includes it.
The convex collider fills the open entrance for collision; the rendered mesh
retains that opening. No photographic pixels or retail assets are included.
