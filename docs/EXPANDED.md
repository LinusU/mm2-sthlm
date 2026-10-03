# Expanded Stockholm generation

The default profile uses the agreed `config/target-boundary.geojson` plus real
OSM coastlines. Complete Kungsholmen, Södermalm, Djurgården and central islands
are retained. The northern mainland is clipped to the authored boundary along
the real OSM E20 shared-node path from Karlberg to Värtahamnen, including its
underground geographic alignment, with a 100 m corridor margin. The remaining
outer water envelope interprets the agreed sketch, not a cadastral survey. Lilla Essingen, Stora Essingen, Lidingö
and Hammarby sjöstad are excluded. External bridges are not exported as roads.

`./scripts/sthlm build --offline` builds the expanded profile. Use
`--profile stadshuset` for the original small, flat comparison fixture.
The expanded source is a bounded Stockholm BBBike regional OSM extract,
September 26, 2026, with the original complete Mälaren relation retained.
`.venv/bin/python scripts/acquire-expanded.py` requires the optional pinned acquisition
packages in `requirements-acquisition.txt`; normal builds do not require them.
The provider MD5 matched the cached PBF. The snapshot and exact provenance are
in `sources/expanded/`; failed Overpass queries are labelled as such. Incomplete
source relations and malformed building rings are reported, not guessed.

The road network uses source OSM shared nodes. Geometric crossings do not
invent junctions. Eight routes from the spawn check coverage across the city.
Disconnected local service roads may remain; this is not a claim that every
OSM road or tunnel is accessible. Supported internal bridges have continuous
estimated decks; DTM does not measure deck elevation. Tunnels and unsupported
grade-separated roads are recorded as omissions.

Terrain is described in [TERRAIN.md](TERRAIN.md). Ground mesh cells are at most
25 m across, roads have boundaries subdivided at 5 m, and road heights sample
10 m centerline intervals. Road shoulders blend into terrain. Low quay road beds have a nominal 0.9 m
minimum to keep them above the chosen water reference; that clearance is a
generation rule, not a correction to surveyed ground values. Buildings retain
level roofs and start at their lowest sampled footprint edge. This is a first
terrain pass: retaining walls, road cuts, detailed embankments and surveyed
bridge decks remain refinement work. Mälaren uses its OSM `ele=0.7` tag; other
water surfaces use a nominal zero reference. Neither is a tide measurement.

Source tree nodes become original PKG meshes with native `props.pathset` and
`dgbangerdata` records. Trees are independent breakable props, with two native
BREAK parts. They do not increase the static PSDL city mesh or duplicate engine
breakaway physics. Trees overlapping roads or buildings are filtered out.

Large maps use bounded independent PSDL vertex pools and an optional `.chunks`
manifest. This is a generic rust-mm2 extension. Retail MM2 cannot read that
companion manifest. Native prop formats help a future retail export, but retail
textures, city registration/navigation, static map constraints and testing in
the original executable still need a separate compatibility milestone.

Church heights include steeples. The generic church renderer therefore uses
an estimated low nave and a narrow schematic tower/spire up to the source
height, instead of extruding the entire footprint into an office-like block.
Tower placement is explicitly approximate; authored landmark detail is future
work. The first waterfront capture is retained for comparison.

Buildings require contact with included land, which removes tiny clipped
fragments of excluded shores that would otherwise look like floating towers.
OSM `building=ship` records are retained as explicit omissions until they have
suitable authored prop art; they are not rendered as apartment facades.
