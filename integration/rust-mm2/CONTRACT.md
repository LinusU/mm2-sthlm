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
conversion. PSDL uses a shared uint16-index vertex pool. Oversized spatial
chunks spill whole rooms into additional native pools, remapping all vertex
references and local water IDs. No index wraps; a single oversized room or
more than 129 total parts fails before export. Room 0 is the reserved sentinel.
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

## Expanded terrain profile

Expanded packages require generic multi-part city support at the revision in
`compatibility.json`. `city/stockholm.chunks` lists independent PSD0 parts in
one metre coordinate frame. Each PSDL vertex pool stays below 65,535 vertices;
room IDs are namespaced by the loader. CPVS is intentionally unsupported for
multi-part cities. Missing listed parts are fatal. This companion format is a
rust-mm2 extension and is not consumable by original MM2.

Roads use shared source-node elevations and subdivided, terrain-conforming
surfaces. Internal bridge decks are emitted separately above underlying land
or roads. Ground meshes sample the real 10 m RH2000 fixture in cells up to25 m,
with continuous road shoulders. Source water height and estimated deck rules
are retained in normalized metadata. Ground-model licence/provenance and
modifications are included in package attribution.

Tree meshes are original PKG3 geometry, native pathset points and banger records
with separate native BREAK parts. The existing engine prop physics handles
their breakage; no vehicle or breakaway simulation lives in this repository.

## Native HUD map

Each package includes `tune/stockholm.mmhudmap`, a world-space XZ tile in
`geometry/hudmap_stockholm.pkg`, a north-up PNG texture, and original
`hudmap_tri.pkg` / `hudmap_square.pkg` marker meshes with the native paint slots.
The tile's metre coordinates align directly with city/player coordinates;
`minimap.json` records bounds, scale, palette and source park omissions.
Package checksums include every HUD resource. No new engine support or retail
map artwork is needed. The existing Tab/E/F/Q controls use the generated tune.
The native resource names do not establish vanilla compatibility for the
expanded city; its multi-part geometry still requires the separate loader.

## Current upstream integration

Latest upstream is `2dd688171553dd747339cc75e8ff40f6d455c3a7`.
The separate ready [PR #6](https://github.com/LinusU/rust-mm2/pull/6) revision
`c4156b780969666f420375d9f5647f51913646a0` adds explicit QA guides through
the existing native driving controls, occurrence-aware dense guide progress,
normal moving captures when explicitly requested, and a stricter distinction
between vertical walls and steep upward terrain. Its complete patch is
`bot-route-guide.patch`; checksum and base are in `compatibility.json`.
All 1,869 engine workspace tests, strict Clippy and formatting pass. Final
coherent city race acceptance is still being measured separately.

Build the exact revision outside the map repository:

```sh
git clone git@github.com:LinusU/rust-mm2.git /tmp/rust-mm2-races
cd /tmp/rust-mm2-races
git checkout c4156b780969666f420375d9f5647f51913646a0
RUSTC_WRAPPER= cargo build --locked -p mm2_app --bin mm2
```

The following prop/slope reports describe earlier tested revisions. Their
patches remain historical, even though their PRs are now merged upstream.

Upstream main was fetched over SSH and built at
`46f351b9186ad2d4d955e9d0d0a1ef1240d2332f`; the previous multipart and
HUD-map PRs are merged there. Historical evidence keeps its original revisions.

The intact-prop engine fix is `039edc98bab91a36aede5e4a5d8eae729d47deab`,
based on that main revision. [PR #4](https://github.com/LinusU/rust-mm2/pull/4)
and `intact-banger-collision.patch` provide a focused native movable-prop fix.
Open, two-sided meshes now use convex collision when bound as bangers, avoiding
invalid dynamic inertia. This fills concavities of bound props; unbound static
INST/PKG structures retain exact triangle collision. Full engine formatting,
strict clippy and workspace tests pass. Stockholm ramp and intact toilet impact
probes pass with finite physics, four tracked wheels and no resets.

Reproduce the engine build in a separate checkout:

```sh
git clone git@github.com:LinusU/rust-mm2.git /tmp/rust-mm2-stockholm
cd /tmp/rust-mm2-stockholm
git fetch origin codex/sloped-city-fans
git checkout b3d9804489bdcd576dd4b85b3f40fec75c545071
RUSTC_WRAPPER= cargo build -p mm2_app --bin mm2
```

Keep each checkout’s Cargo target directory separate. The generated package
contains no engine checkout, collision simulation or vehicle physics.

The current tested engine is `b3d9804489bdcd576dd4b85b3f40fec75c545071`.
[PR #5](https://github.com/LinusU/rust-mm2/pull/5) stacks on PR #4 and
`sloped-city-fans.patch` applies after the intact-prop patch. It restricts
the native perimeter-facing heuristic to effectively vertical surfaces; steep
upward paving/terrain no longer gets flipped downward and culled. True vertical
walls keep their outward-facing behavior. The meaningful slope regression
fails with the old cutoff; full engine formatting, strict clippy and workspace
tests pass. The actual Västerbron camera comparison closes the blue wedge
without changing its map polygons.
