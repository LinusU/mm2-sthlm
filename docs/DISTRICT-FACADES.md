# District facades

Generic buildings use six approximate artistic district polygons in
`config/overrides/district-facades.json`. These are palette selection regions,
not administrative boundaries. Source geometry/heights remain authoritative.
Twenty-four deterministic source-ID color variants provide ochre, warm cream,
muted pink, stone gray and selected brick bays. Narrow six-pane historic windows
contrast with broader Norrmalm bays; iron, copper and clay roof colors keep the
classic MM2 palette quiet. The exporter never imports engine/vehicle code.

## References and original artwork

Authored 2026-10-04. The City Museum's
[Sten och stil i Stockholms fasader](https://stockholmskallan.stockholm.se/postfiles/SMF/SD/SSMB_0001065_01.pdf)
supports the restrained stone trim and varied inner-city facades. Official
Visit Stockholm district photo pages provide contextual visual references:
[Kungsholmen](https://www.visitstockholm.com/stockholms-districts/kungsholmen/),
[Norrmalm](https://www.visitstockholm.com/stockholms-districts/norrmalm/),
[Östermalm](https://www.visitstockholm.com/see-do/attractions/district-guide-ostermalm/),
[Södermalm](https://www.visitstockholm.com/stockholms-districts/sodermalm/),
[Gamla stan](https://www.visitstockholm.com/stockholms-districts/gamla-stan/),
[Djurgården](https://www.visitstockholm.com/stockholms-districts/djurgarden/).
District color assignments are an artistic approximation; they do not assert
that each source building has a surveyed facade color or doorway.

All 76 PNGs are generated from original Python drawing instructions and RGB
palettes. No photograph, Google image, retail texture/model or AI image pixels
are copied. Build is deterministic, offline, and does not require an image tool.
Procedural source and palette JSON are the original material assets.

## Native export API

`material_for(building, origin)` returns a fresh district profile or None for
churches, small utility buildings and street detail features.
`StreetFrontages(city, road_height)` indexes ordinary source road centerlines.
`export(writer, polygon, building, frontages, material)` supports both native
PsdlWriter and ChunkedWriter. `write(out)` creates package texture assets.

The root exporter chooses this only after existing church/manor/Stadshuset and
new landmark exclusions. Native Facade type 11 is `[bottomHeight, topHeight,
uRepeat, vRepeat, leftVertex, rightVertex]`; the external engine renders v=0 at
the top. Every footprint edge retains its original full-height FacadeBound
collision attribute. Vertical rendering bands partition the same wall without
coplanar overlays. Roof triangulation remains unchanged.

Exactly one 1.6m-wide exterior entrance segment is emitted per eligible polygon,
with uRepeat=vRepeat=1. There are no upper-floor doors or window geometry.
Door candidates must be within 35m of an ordinary street, with an unobstructed
line outside the footprint; courtyards, tunnels and elevated bridges do not
attract entrances. Ground-band bottom is max(building base, nearest street
height + 0.06m, ground height at the doorway + 0.06m), with a quiet stone foundation below it. A roof too low for a
3m entrance suppresses the door. This handles raised uphill foundations without
claiming surveyed door positions or physically traversable interiors.

## Evidence

`evidence/district-facades/native-door-probe.png` and
`native-district-palette.png` are actual external native-engine captures of a
small independently authored probe city, using engine revision
`b3d9804489bdcd576dd4b85b3f40fec75c545071`. They demonstrate native facade UVs,
a single ground door, and the district palette. They are not captures of the
full Stockholm map. Six actual Stockholm native street views are also included as
`stockholm-{district}.png`; the commands and source building IDs are in
`captures.json`. Final corrected native screenshots were visually inspected.
The earlier partially buried Old Town entrance is retained under
`before-hillside-fix`, separate from accepted results.

Ruff, all 93 unit tests, offline build and validation pass on baseline map
`0ccde35a9ddf4c41836b71c249d6bc306f7186e2` with the local root-export hook.
The corrected relocated package completed all 102 gates with zero impacts or
resets and four wheel contacts; a second independent city passed and a removed
chunk failed loudly. Exact package/engine hashes and full results are recorded
in `acceptance.json` and `portable/portability.json`. The coordinator must
repeat integrated acceptance after combining this with its newer main changes.
