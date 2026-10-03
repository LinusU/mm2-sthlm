# Waterfront bar pavilion

`src/pavilion.py` replaces only `way/1049742528`, the one-storey retail
footprint nearest camera `-1035.7,5.3,-17.4,-30,-14`. Its recorded east/north
centroid is approximately `-1005.8,67.4`; the source has no recorded venue name.

The user's photograph guides a simple dark-green glass pavilion with a central
gable, low wings and yellow/cream awning bands. Dimensions in
`assets/landmarks/waterfront-bar.json` are authored estimates, not surveyed facts.
The footprint stays exactly the recorded source polygon; the source terrain
`base_y` supplies the elevation. No terrace, furniture or photograph pixels are
added. Original opaque textures avoid transparency dependence in native PSDL.

Wall attributes explicitly use one vertical repeat. Roof slopes are split at
the ridge before triangulation; vertical gable fans use the full central polygon
as their room perimeter so native face orientation remains valid. Both single
and chunked PSDL writers are supported. The generator emits its own textures
into the native package. Ordinary offline tests require no engine checkout or
GPU. Unit/package checks do not constitute in-engine visual evidence.

Actual rust-mm2 captures, exact user camera and reproduction command are saved
in `evidence/pavilion/acceptance.json`. Engine revision is pinned there,
with the generated package checksum. The PNGs are unmodified engine output.
