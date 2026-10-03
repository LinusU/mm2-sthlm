# Target extent

Linus's 2026-10-03 description and annotated drawing define the eventual map.
The current playable Stadshuset slice remains unchanged in `config/slice.json`.
`config/target-scope.json` records the inclusion/exclusion policy;
`config/target-boundary.geojson` is an approximate WGS84 acquisition envelope.
It is **not** a surveyed shoreline, generated full-city map or collision wall.
Explicit exclusions take precedence over this coarse polygon. Its control
points are authored approximations of the request, not fabricated OSM data.

- North: Värtahamnen west along E20 to Karlbergs slott.
- West: all of Kungsholmen, stopping in the water beneath Tranebergsbron;
  Tranebergsbron is impassable. “Eastern” in the request is interpreted as
  western from the drawing and geographic context.
- Southwest: no content or driving on Lilla Essingen or Stora Essingen.
- South: include the entire Södermalm island, stop in the water to its south;
  exclude Hammarby sjöstad and block external bridge exits.
- East: include Djurgården and stop in the surrounding water. Lidingö has no
  playable content; a distant green silhouette is an optional later asset.
- Central islands are included. Långholmen and Reimersholme are interpreted as
  included from the drawing; keep this explicit for later refinement.

The polygon's role is to bound terrain/source acquisition with a 1 km buffer.
The normalizer refines the clip using actual acquired shorelines and the
shared-node E20 alignment, with a 100 m corridor margin. Preserve open water, exclude
island roads/assets explicitly and cap external bridges at sensible locations.
The expanded profile now uses real OSM coastlines and complete source terrain
coverage. See EXPANDED.md and TERRAIN.md for the interpretation and evidence.

## Implementation order

1. Record the target extent (this document/config).
2. Acquire a real **ground** model for that area with a buffer, retain its
   horizontal/vertical CRS, licence, timestamp and checksums.
3. Validate the elevation pipeline on the existing Stadshuset driving loop.
   Share intersection heights, smooth road grades, keep water level, seat
   buildings and trees, adjust spawn/reset and test actual vehicle motion.
4. Expand in connected increments inside the refined boundary. Internal
   bridges need genuine deck elevations and proper grade separation.

## Terrain access

Lantmäteriet's [Markhöjdmodell Nedladdning](https://geotorget.lantmateriet.se/geodataprodukter/markhojdmodell-nedladdning-api)
is a 1 m ground model distributed as COG through STAC. The product is free,
but access must be enabled on a Geotorget account. The
[official documentation](https://geotorget.lantmateriet.se/dokument/projects/markhoejdmodell-nedladdning/released/1/)
describes Basic/OAuth authentication. Credentials belong in a local secure
configuration or environment, never the repository or chat.

[Stockholm's municipal 1 m 3D grid](https://kartor.stockholm/kartor-geodata/)
is an ordered product with a tariff. It is not a silently available source.
A coarse public surface DEM is an alternative only if explicitly chosen: it
may contain buildings/vegetation and cannot be described as measured street
heights. Supplied Lantmäteriet ground tiles are now integrated (TERRAIN.md). No
invented hills or synthetic terrain is presented as Stockholm elevation.
