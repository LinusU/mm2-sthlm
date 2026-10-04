# Stockholm underground roads

The generator keeps underground driving corridors separate from surface ground.
Terrain is a ground measurement, not a measured tunnel floor. The profile rules
in `config/overrides/tunnel-profiles.json` are authored estimates: 5 m samples,
8 m maximum depression from an interpolated portal datum, a 140 m cosine entry
ramp, and 5.2 m nominal internal height. Roofs begin only under at least 5.7 m of cover;
exposed ramps have retaining walls capped at surface ground. Otherwise a roof
would form a canopy above the entrance street. Short tunnels retain their shallow
profiles instead of being forced down eight metres.

## Sources and scope

- [Stockholm city's Klaratunneln renovation description](https://vaxer.stockholm/projekt/norrmalm/renovering-av-klaratunneln/)
  describes two tubes with branches from Tegelbacken toward Sveavägen and
  Mäster Samuelsgatan. Its linked ramp/interior photograph was inspected locally and informed the
  restrained concrete shell and original pale ceiling fixture bands; no photograph
  or source texture was redistributed.
- [Stockholm technical handbook](https://tillstand.stockholm/globalassets/foretag-och-organisationer/tillstand-och-regler/tillstand-regler-och-tillsyn/mark--och-gatuarbeten/teknisk-handbok-for-byggande-drift-och-underhall-pa-offentlig-mark/teknisk-handbok-samlingsdokument-2010-11-01.pdf)
  inventories Blekholmstunneln, Klaratunneln and Söderledstunneln separately.
- [Stockholmskällan's Centralbron construction photograph](https://stockholmskallan.stockholm.se/post/21938)
  documents the continuation of the Söderleden corridor into Centralbron.
- [Trafikverket's Norra Länken tunnel sections](https://bransch.trafikverket.se/contentassets/02d72a606fa844198963315a20af1446/2024/kalendarium-planerade-avstangningar-q1-q4-2024-1.1.pdf)
  identifies Gärdestunneln, Kosmostunneln and Norrtullstunneln. Source geometry
  is selected only inside the existing approved northern corridor.

Geometry and topology come from the checked-in OSM snapshot. The authored
inventory records 97 selected source ways, including all nine Klaratunneln
ways, all five Blekholmstunneln ways and all eight Söderledstunneln ways.
It also covers their named ramps, Hundra Knutars Backe, Karlbergstunneln,
Tomtebodatunneln and eligible local street underpasses. The inventory's
height diagnostics describe the development profile run; surface smoothing
can change those estimates on a later build.

Selection validates whole source-connected networks, not merely names or
individual bounding boxes. Each network needs at least two real public surface
connections. A terminal with no surface connection is accepted only where its
OSM tunnel continuation leaves the mask. These four Norra Länken termini
receive explicit closed end walls: nodes 415311702, 415313276, 3199866450,
3199972195. XY crossings without a shared OSM node never create a junction.

Fredhällstunneln is excluded because it leads into the explicitly excluded
Essingeleden connection. Excluded islands and outward bridges remain excluded.
Parking/access/service tunnels are omitted. `tunnel=building_passage` is omitted
until building walls can receive proper ground-floor openings; otherwise a
nominally included street would run into a solid facade. Lundagatan has no named
tunnel way in this snapshot; its street/viaduct crossings stay with the sourced
surface/bridge geometry rather than receiving a fictitious bore.

## Coordinator hooks

`internal_tunnel_ways(ways,nodes,cfg,playable_mask,BLOCKED)` returns selected IDs.
Pass them into source normalization as `allowed_tunnel_ways`, retain the four
motorway/trunk classes, and save `city['tunnel_ways']`. Mask-bounded open-cut
roads with a nonzero layer but neither bridge nor tunnel tags must also remain
as surface road connections. Continue rejecting blocked outward names.

Build surface/bridge fields with tunnel IDs excluded from the ordinary road
list. After those profiles exist, call `tunnels.prepare(city,terrain)`, then
`tunnels.write_roads(writer,city,terrain)`. Underground floors use independent
per-source-way fields, retaining coincident roads at different levels. The
optional `road_surfaces.render` API gives these floors the same native textured
asphalt treatment without underground signal props.

Subtract `shape(city['tunnel_terrain_cutout'])` from the **land** mesh only.
That polygon contains only exposed entrance/ramp segments where the ground
would intersect the aperture. Covered tunnel buffers do not erase the land
above. Never add tunnel samples to `RoadField.ground`, grass, buildings, or
surface-road texture union.

Append `tunnels.write(out,city)` instances to the normal native prop pathset.
Original concrete walls/roof are static unbound PKG triangle meshes. Connected
branch walls are opened where the actual adjacent source corridor joins. Shell
ends stay open at real portals and source-way splits; mask exits are closed.
Native assets use local minimum Y zero and map-native XYZ coordinates.
Explicit source widths are retained; otherwise sourced lane counts set the bore
width to 3.4 m per lane plus 1.6 m total verge. This keeps closely spaced paired
one-lane tubes from inheriting the ordinary nine-metre street default and placing
a wall in their neighbour's driving lane. Branch aperture tests open every panel
that intersects the real adjoining roadway, including near panel ends.

## Validation status

Nine focused regressions pass: source-node topology, complete public geometry
selection, independent buried profiles, portal-only terrain cuts, roof cover,
native shell aperture, source lane width, branch openings and explicit boundary
closures. Ruff passes. The development full suite has 97 passing tests after consuming the
coordinator's updated elevation expectation. Development real-source profiles
contain 97 ways, finite heights, exact shared-node split heights and a worst
grade of 12.92% (Hundra Knutars Backe).

The offline development integration build and package validator pass. Actual
native engine source courses cover 160.7 m inside Klaratunneln (432147270),
160.7 m inside Blekholmstunneln (20278071), 160.7 m inside Söderledstunneln
(151884980), and 137.3 m from surface approach 4700199 into Klara portal 4700200.
All four have zero impacts, zero resets and four grounded wheels. Klara and Blek
courses exercise real curved alignments and actual steering. Parked probes in
all three corridors settle on four wheels, including Blekholm's below-datum
floor. The original over-wide shells failed the portal test; source lane width
inference fixes that failure. No engine or physics code was copied or changed.

Inspected native captures in the worker's `evidence/tunnels/` show the Klara
interior, corrected cut-in entrance and intact city surface above its bore.
Those captures have actual engine vehicle physics active. They predate the
final source lane width/fixture art and final root native road strip export;
repeat final integrated visual acceptance before claiming the whole map done.

The optional explicit probe helper is reusable for bridge layers as well:

```sh
.venv/bin/python scripts/check-tunnels.py --engine /absolute/path/to/mm2
.venv/bin/python scripts/check-tunnels.py --engine /absolute/path/to/mm2 --way 233761058 --frames 1800
.venv/bin/python scripts/check-tunnels.py --engine /absolute/path/to/mm2 --portal-way 4700200
```

It uses each retained source roadway's own profile, writes a temporary source
course into the existing native race CSV, restores that CSV in a `finally`
block, and rejects impacts, resets, inadequate travel or lost wheel contact.
Do not run it concurrently with a package build or another race probe on the
same package. It is not invoked by normal offline CI.

Temporary coordinator hooks in the isolated development worktree are not part
of this worker's patch. The coordinator owns final source/export integration,
per-station native textured floor verification and final full-map acceptance.

The integrated native portal regression (2026-10-04) exposed ordinary road
caps and paving above the descending Klara floor. At 10 metres inside
way/4700200 the native floor was 9.4668 m while paving crossed it at
10.8593 m. Removing tunnel shells alone still produced eight impacts.
Clipping four ordinary native asphalt, road-strip and paving rooms by the
existing exposed-ramp cutout preserved every triangle's original height
plane and every tunnel floor, then the identical 40 m source approach
4700199→4700200 passed 138.0 m with zero impacts/resets and four supported
wheels. This copied-package diagnosis is not a substitute for accepting the
fresh generator output.

After `prepare(city, terrain)`, the coordinator must apply
`base_roads = tunnels.clip_surface(base_roads, city)` and update
`city["ground_road_surface"] = mapping(base_roads)`. Apply the same helper to
derived paving before writing it. Continue cutting land by the same cutout.
Do not apply it to bridge decks: an exposed tunnel approach can pass beneath
a real overpass. Covered tunnel sections are absent from the cutout, so their
overlying ordinary roads and land remain. Shell wall bottoms now meet the
floor half-width exactly; the previous extra 0.15 m left a visible slit.
