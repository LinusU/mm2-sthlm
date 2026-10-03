# Terrain seams and bridge approaches

Roads, paving and land use the same five-metre boundary subdivisions before
chunk clipping. Interior terrain patches still use a coarser grid. Both sides
of a shared edge sample the same height field, including wide-road shoulders.
This avoids cracks where coarse paving previously skipped intermediate road
vertices. The denser boundaries increase triangle count; no frame-rate claim
is made from the geometry tests.

Only source-connected ordinary-road approaches are split into short raised
segments beside bridge decks. Their source topology and node elevations remain
unchanged. Shared ground/deck junctions use one height plane. Unrelated lower
roads retain their complete footprint and height field beneath the bridge;
removing every projected bridge overlap would erase valid underpasses.

Regression tests cover shared boundary tessellation, negative chunk seams,
wide-road shoulders, connector heights and independent underpass clearance.
Actual engine checks, commands, revision and unmodified screenshots are in
`evidence/surface-seams/acceptance.json`.

Bridge ends now use the connected approach road's sampled height rather than
letting a steep bank sample pull the deck down. The final 30 metres blend into
the shared junction plane. Raised approaches are removed from the parent land
surface while independent lower streets remain intact.

The final acceptance run passes all 16 probes on engine
`b3d9804489bdcd576dd4b85b3f40fec75c545071`. Five continuous drives cover 38 m
and 67 m at Västerbron, 72 m on the Sankt Eriksbron connector, 107 m beneath
Sankt Eriksbron, and 67 m at the Västerbron crown. Each has zero impacts or
resets, finite state and four wheels tracked. This supersedes the initial
failed Sankt Eriksbron connector probe retained in Git history.

The remaining blue wedge was an engine winding bug: steep upward paving fans
were classified as vertical walls. The generic fix is rust-mm2 PR #5, with
its exact revision and patch under `integration/rust-mm2/`. Matching actual
engine screenshots show both reported wedges closed. These local checks do
not establish that every city seam or complete bridge span has been driven.
