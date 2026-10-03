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

The first acceptance run closes the reported ground crack and restores the
lower Sankt Eriksbron street: its 107 m drive has no impacts or resets. The
Västerbron connector drive covers 45 m with four wheels tracked. It also
exposes a remaining steep Sankt Eriksbron approach: the full-throttle probe
hits once and finishes airborne. That probe is not accepted as a smooth
bridge transition; the source deck-end estimate still needs correction.
