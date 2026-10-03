# Brick church materials

`assets/materials/church-brick.json` selects Högalidskyrkan by the frozen source
features `relation/1257127` and `relation/17957127`. The snapshot contains
two overlapping Högalid footprint representations; both need the same material
so a second schematic tower does not retain apartment windows. Other churches
retain their existing material
selection. An explicit `sthlm:material=brick_church` tag permits reuse of the
profile on another source feature.

The supplied Högalid photographs guide original procedural red-brown running
bond brick, muted mortar, tall narrow arched dark-glass bays, tower slots and
weathered green copper. No photograph pixels are included. Facade repeats span
6 m horizontally and 12 m vertically to avoid apartment-sized window rows.
Those dimensions are authored visual estimates, not a survey.

`church_materials.material_for(building)` returns the profile or `None`;
`church_materials.write(output_directory)` writes four deterministic RGB PNGs
to `texture/`. Body walls use `church_facade`, tower walls use `church_tower`,
and church roofs use `church_copper`. `church_brick` supplies plain masonry for
reuse. Existing footprint, height and schematic tower geometry remain in use.

Tests check source selection, explicit reuse, exclusion of other churches,
staggered brick courses, rounded tall window art and reproducible readable PNGs.
Texture previews and these checks are not in-engine visual evidence.

Actual rust-mm2 captures, exact user camera and reproduction command are saved
in `evidence/church/acceptance.json`. Engine revision is pinned there,
with the generated package checksum. The PNGs are unmodified engine output.
