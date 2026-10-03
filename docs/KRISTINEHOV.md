# Kristinehovs malmgård materials

`config/overrides/kristinehov-materials.json` restricts this art to the named
main house `way/88413905` and its two immediate wings, `way/88413902` and
`way/88413904`. All three frozen expanded OSM features describe yellow plaster,
one-level retail buildings with half-hipped roofs. Nearby apartments and the
small shed retain the normal material selection.

The supplied courtyard photograph guided original procedural pale yellow
stucco, muted gray-green surrounds, tall six-pane windows, a modest stone
plinth and weathered warm clay roof tiles. No photograph pixels are included.
The 4.2 m facade bay is an authored visual spacing estimate, not a survey.
No source tags, height estimates, roof shapes or footprint geometry are changed.
The current simple building mesh still limits the roof silhouette.

`manor_materials.material_for(building)` returns an explicit material profile or
`None`; `manor_materials.write(output_directory)` writes the native RGB PNGs into
`texture/`. The output includes `manor_plaster` for future plain-wall uses, but
the current profile uses `manor_facade` and `manor_tiles`.

Material tests check the frozen source IDs, exclusions, source immutability,
original window colors, PNG readability and reproducible output. These checks
are not in-engine visual evidence.

Actual rust-mm2 captures, exact user camera and reproduction command are saved
in `evidence/kristinehov/acceptance.json`. Engine revision is pinned there,
with the generated package checksum. The PNGs are unmodified engine output.
