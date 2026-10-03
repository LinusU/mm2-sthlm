# Sources and geographic assumptions

`sources/osm.json.gz` is a genuine bounded Overpass response retrieved on
2026-10-03. Its **reported source timestamp is 2026-06-01T08:52:28Z**; retrieval
is not a claim that it reflects today's edits. The complete response, query,
endpoint, bounds and checksums are in `sources/manifest.json` and
`sources/query.overpass`. The first endpoint returned HTTP 406; the second
request to overpass.kumi.systems succeeded. No paid data or account was used.

The query envelope is 18.0295,59.3235–18.0605,59.3345 (WGS84), with recursive
member geometry. Mälaren's relation reaches far outside this envelope; keeping
its full referenced data permits honest water clipping. The response contains
107078 nodes, 4264 ways and 14 relations. Gzip is deterministic (`mtime=0`).

Roads and buildings retain OSM IDs and tags in `normalized.json`. Relation
members and all referenced geometry remain in the source snapshot. Relation
29368 is Stadshuset, with its real inner courtyard. Relations 1433877 and
5776802 supply Mälaren/Riddarfjärden water. The lake's inner members include
two non-ring cut segments far outside the slice. They are retained in source;
polygonization rejects bad fragments intersecting the buffered local bounds.
No invented shoreline override is used. Incomplete local geometry fails build;
invalid way polygons are explicitly reported in `omitted`.

OSM data: © OpenStreetMap contributors,
[ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/),
[attribution requirements](https://www.openstreetmap.org/copyright).
The source and derived normalized geographic database remain ODbL. MIT covers
only generator code and original procedural artwork. Exported packages carry
ATTRIBUTION.txt; launching through the wrapper prints attribution. Displaying
or publishing screenshots should retain an accompanying OSM attribution.

Optional sources were checked without blocking the OSM version:
[Stockholm geodata](https://kartor.stockholm/kartor-geodata/) offers portals
and ordered products; [Lantmäteriet terrain](https://www.lantmateriet.se/sv/geodata/vara-produkter/produktlista/markhojdmodell-nedladdning/)
was not acquired. Neither contributes to this package.

Projection is a local WGS84 equirectangular tangent approximation at
18.045° E,59.328° N: X = R cos(lat0) delta_lon, N = R delta_lat, with
R=6378137 m and radians. Geographic processing uses Python double precision.
The maximum local extent is about 1.5 km; this approximation is appropriate
for this schematic slice, not survey work. Export uses X east, Y up, Z south;
PSDL vertices are rounded to 1e-5 m then stored as float32. Current tested
rust-mm2 preserves these axes. Older architecture prose about a Z mirror is
outdated; this was verified against code and actual wheel contacts.

Vertical reference is authored and approximate: road/land 2 m, water 0 m,
building heights relative to land. It is **not RH2000**. `height` wins over
`building:levels × 3.2 m`. Finite heights from 0.5 to 150 m are accepted.
Missing heights use 3.2 m for sheds/garages/service or footprints below 40 m²,
6.4 m below 150 m², otherwise 15–24.6 m using a stable feature-ID hash. Each
rule is retained beside its result. Clipped building fragments can be narrow
at the outer boundary; accurate interiors and terrain are deferred.

Driveable classes exclude foot/cycle paths, bridges, tunnels and nonzero
layers. Exclusions are listed; crossing coordinates never invent graph edges.
The benchmark uses shared OSM nodes along Norr Mälarstrand → Ragnar Östbergs
Plan → Hantverkargatan → Kungsholmstorg → Norr Mälarstrand. Free driving has
no traffic or enforcement of OSM oneway restrictions. Width tags are used
when valid, with 9 m default and 5–14 m conservative bounds. Road ends are
rounded and unioned before triangulation; this is deliberate junction
smoothing, not overlapping ribbon collision. No difficult peripheral bridge
is flattened into the network. Source bend vertices remain in the geometry
route; benchmark gates sample at 15 m intervals.

Stadshuset artwork is original schematic primitive modelling. Its sourced
footprint/courtyard and southeastern tower placement are retained. The
[municipality's tower reference](https://stadshuset.stockholm/en/visit-stockholm-city-hall/city-hall-tower/)
reports a 106 m tower; its
[architecture page](https://stadshuset.stockholm/en/explore-the-city-hall/architecture/)
describes the three-crown symbol. `assets/landmarks/stadshuset.json` records
references and proportions. The copper roof, open belfry and simplified gold
crowns are authored approximations, not measured architectural reconstruction.
