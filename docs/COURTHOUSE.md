# Stockholm Court House landmark

`src/courthouse.py` replaces the generic building renderer for OpenStreetMap
`way/24488933` only. The source snapshot and normalized source geometry stay
unchanged. The exporter returns rendering metadata and creates original
procedural PNG textures in the generated package's texture directory.

The reference is the two photographs supplied by Linus on 2026-10-03. They
show sand-coloured rough plaster, a low rough stone base, red tiled pitched
roofs, arched blue-glass windows with dark brown frames, roof dormers, brick
chimneys and a square tower with a tall, stepped patinated copper roof.
The photographs are visual references only; their pixels are not copied into
assets or redistributed.

All dimensions, heights and roof details in `assets/landmarks/courthouse.json`
are authored estimates, not surveyed measurements. The source polygon contains
no courtyard rings. Two estimated courtyard voids are explicitly recorded
in rendering metadata; the original exterior bounds every authored component.
This keeps courtyard interiors open rather than filling them with a tall solid
pink block. Civic facade bays use two vertical repeats rather than generic
apartment floors. The tower is placed in the west central wing facing the park.

The main eaves are 14.5 m above the normalized local building base, with 6 m
roof rise. The tower shaft reaches 28 m; stepped copper hips and a lantern-like
upper stage rise to 50 m, with a thin 3 m finial. The compact tower footprint,
roof dormers and brick chimneys all remain inside the source exterior and
outside the authored courtyard voids. Terrain elevation is applied to every
component through the normalized `base_y` value.

Tests read the checked-in source feature without network access. They check
source anchoring, open courtyards, tower proportions, elevation, material
availability and both single and chunked PSDL export. These checks verify
geometry and package generation; they are not in-engine visual evidence.
Vertical copper-stage and gable fans carry their enclosing footprints as room
perimeters, allowing the existing engine to resolve their visible exterior
faces without its upward-ground fallback reversing vertical walls.

## In-game verification

`evidence/courthouse/acceptance.json` records exact commands, package checksum,
engine revision `74c60897ef8472aceafea0bb871f2e46615a095c` and original game
screenshots. The reported camera checks the facade; the elevated park camera
shows the full roof and tower. Visual iteration exposed a culled vertical copper
stage; full room footprints now let the engine select its outward face correctly.
The final images were inspected after that correction. All 44 offline map tests,
Ruff, offline build and package validation pass.
