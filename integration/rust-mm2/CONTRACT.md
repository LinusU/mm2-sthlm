# Package schema 1

The export boundary uses the engine's existing mod/PSD0 formats, not a new
Stockholm engine branch. `mod.toml` is the existing [mod] manifest; assets
resolve through the generic VFS at `city/stockholm.psdl`, `texture/*.png`,
`race/stockholm/*`. `map.json` is **wrapper metadata**, not an invented native
engine manifest: it supplies schema, identity, spawn, world conditions,
compatible revisions and route length. CLI options bridge these values to the
unmodified generic loader. A direct engine launch should pass the metadata's
spawn explicitly; the PSDL bounds center is also placed by that spawn.

Units: metres. Export X east, Y up, Z south. Processing X east/N north; the
writer converts north to negative Z exactly once. Surface triangles are
counterclockwise in processing XY, which yields upward normals after that
conversion. PSDL uses a shared uint16-index vertex pool; the exporter fails
rather than wrapping at 65535 vertices. Room 0 is the reserved sentinel.
Names are byte-length-prefixed, NUL-terminated PSDL texture stems.

Road and junction polygons are unioned then constrained-triangulated with
holes. Shared tile vertices are deduplicated. Land and paving subtract roads,
so a second ground collider does not compete under the driving surface.
Buildings retain holes; Facade gives batched visual walls, FacadeBound gives
static collision, Fan gives roofs. Water Fan rooms are flagged Water and
referenced by the standard `.water` file: they are water contact surfaces,
not roads. Engine recovery checks water wheel contacts and restores the last
dry grounded pose. Slice exits have 1.2 m static barriers over land; water
has no lake-wide invisible road platform.

Lighting files are original clear-morning/noon tune records. Missing optional
sky, HUD map, fonts, retail particle effects and audio are reported by the
engine; no retail asset is packaged. Normal chase camera and reset use engine
session ownership. Restart goes through normal teardown, never a second map
simulation. The procedural vehicle is engine-owned.

Every package contains `normalized.json`, original textures, ATTRIBUTION.txt,
all referenced city/event files, `map.json` and `checksums.json`. Manifest paths
must be relative, stay within the package (including symlinks), and match SHA256.
Unknown schema, source corruption, missing referenced package assets or an
unlocked engine revision fail with diagnostics. Build and play perform no
implicit network acquisition. The tiny independent triangle integration map
uses the same existing mod loader and a different city identity.

Retail MM2 compatibility is not claimed. This version is tested in rust-mm2.
