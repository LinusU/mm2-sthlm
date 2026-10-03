# Bridge structures

`src/bridges.py` authors original native PKG structures separately from the
PSDL carriageways. Every allowed bridge receives a 0.7 m slab below its
existing deck. The native triangle list includes downward facing underside
triangles, avoiding the floor-fan renderer's upward-normal assumption.

Västerbron additionally uses paired steel ribs in two consecutive arch spans,
vertical spandrel columns, transverse ties, low concrete footings, outer curbs,
picket rails and taller horizontal safety wires. Alignment follows the mean
of the two sourced opposite-direction carriageways. The north end starts the
fractional stations in `config/overrides/vasterbron-structure.json`.

All dimensions and colours are visual estimates from the user's photographs;
these are neither surveyed measurements nor copied photographic pixels. Deck
height remains the existing elevation generator's estimate. Adjust the override
when better surveyed structure data becomes available.

Each mesh has minimum local Y zero and is stamped at its minimum world Y. This
matches the native unbound-prop ground-lift convention without banger tuning.
Meshes are static triangle colliders, retaining the open spaces beneath arches
instead of filling them with a bounding box. The outer rails stay outside the
sourced carriageway envelope. Native geometry chunks remain below 65,536
vertices each. PSDL driveable road surfaces are not modified by this module.

Validation in `tests/test_bridges.py` checks outward winding and closed member
topology, underside area and downward normals, slab clearance, native world
mapping and chunk limits, opposite-direction alignment and rail clearance.
These geometry checks are not in-engine visual evidence.

Integration API: `instances = bridges.write(out, city, deck_field)`, where
`out` is the generated Stockholm package directory, `city` has elevation.apply
results (`bridge_ways`, `bridge_road_surface`, road widths and points), and
`deck_field(x, north)` evaluates the existing deck height. Merge returned
records into `props.write(out, all_instances)`; no separate pathset is written.
The API records provenance in `city['bridge_structure_rules']`. Invoke only
for the expanded full map, after elevation and before saving normalized.json.

The two authored arch spans run between north-oriented stations 0.08–0.41 and
0.41–0.74 of sourced alignment length. Ribs are 0.8 m wide and 1.15 m deep,
with 40 segments per span; crowns are estimated 2.6 m below the deck and feet
at Y=2 m. Spandrel spacing is approximately 18 m. Column tops stop 0.8 m below
the sampled deck; slab tops stop 0.04 m below the existing road and slab bottoms
0.74 m below. Rails are 1.15 m high; upper safety wires reach 2.5 m.

The existing engine loads these PKGs through static native prop stamping and
creates exact triangle colliders; no engine modification is required. Actual integration commands, screenshots and drive checks are recorded in
`evidence/bridges/results.json`. Geometry tests alone do not establish
visual appearance or successful driving in-engine.

Slab export captures bridge-only roadway triangles with the same
`ChunkedWriter.surface` used for PSDL export. Native slab tops reuse exactly
those triangles at a vertical offset of -0.04 m. This makes the gap constant
through each triangle, even at concave deck-profile bends, prepared approach
field transitions and the roadway writer's tile boundaries. Independently
triangulating a coarser slab polygon could bridge above the road between
vertices, so the slab no longer uses its own spatial tessellation. A profile
bend regression compares every emitted slab top to the native road triangle.

Final actual-engine captures show the paired arches, downward-facing underside,
piers and deck rails. Two 66.8 m entry/crown drives finish with zero impacts,
zero resets, finite state and four wheels. They verify these local transitions,
not a continuous drive over the whole bridge. Reports pin the exact engine
revision and package manifest checksum.
