# Mission: build mm2-sthlm as an independent, playable Stockholm map project

Your primary working repository is `mm2-sthlm` (expected GitHub repository:
`LinusU/mm2-sthlm`). Inspect the actual local checkout; do not assume it is
empty. This is a standalone map/content and map-generation project, NOT a
subdirectory, fork, or workspace member of `LinusU/rust-mm2`.

`rust-mm2` is the separate Rust/Bevy/Avian game engine that will consume and
playtest this map. You may reuse its tools and make focused, reusable
improvements there when needed. Keep the two projects separate.

Implement this task, do not merely propose a plan. This brief replaces the
earlier instructions that placed Stockholm's source and generator inside
rust-mm2.

The outcome I want is simple: launch the game, get into a car, and drive
around a small but recognizably real piece of Stockholm. A small finished
slice is much better than a large unfinished city-generation framework.

Work autonomously through implementation, testing and visual iteration.
Make reasonable reversible decisions and record them. Do not stop after
research, scaffolding, a parser, or a task list. Respect the environment's
permissions; do not buy data, create accounts, or bypass access controls.

## 1. Scope and priorities

Build a slice around Stadshuset, the eastern part of Norr Mälarstrand,
Kungsholms torg and nearby streets such as Hantverkargatan. Verify their
positions and connectivity against the acquired data.

Suggested WGS84 starting envelope, not a surveyed final boundary:

    west=18.030, south=59.324, east=18.060, north=59.334

Adjust modestly to preserve a useful connected loop and the waterfront.
Fetch a small buffer outside the playable boundary before clipping.
Do not expand to the whole inner city, Västerbron, or the motorway yet.

Priority order:
1. Real geographic layout and an actual car driving on it.
2. Reliable road collision, joined intersections, spawn and reset.
3. Recognizable waterfront, building blocks and Stadshuset silhouette.
4. Better materials, roofs, facades and modest street decoration.
5. Repeatable generation, offline execution and clear evidence.

Original-retail MM2 compatibility is a future bonus, NOT a requirement
for this slice. Neither are traffic, pedestrians, multiplayer, a complete
race system, streaming, an editor, photogrammetry or accurate interiors.

## 2. Repository boundaries and upstream workflow

### What belongs in mm2-sthlm

This repository owns source snapshots and provenance, geographic boundaries,
normalized city data, overrides, procedural generation, authored landmarks,
materials, export/packaging, map-specific tests and driving routes, integration
scripts and evidence. This is the deliverable repository.

It must be possible to fetch, generate, validate and package the map without
building the game or having a sibling rust-mm2 checkout. Use ordinary pinned
libraries or versioned tools where helpful; independence does not require
reinventing format readers or copying their source.

Use a small stable export boundary:

    mm2-sthlm sources + generator
        -> portable map package
        -> separately built rust-mm2 executable
        -> actual playable Stockholm session

The game reads the generated package, not mm2-sthlm's source tree. No source
paths baked into engine code, runtime network calls, external absolute asset
paths, or implicit dependence on the developer's working directory.

### What belongs in rust-mm2

Reusable engine/tool improvements only: format inspection/writing, generic
custom-city package loading, map-provided spawn/environment metadata,
standalone custom maps with a procedural car, or generic screenshot/drive
probe support. Do not hard-code Stockholm coordinates, road names, landmark
meshes or geographic generation rules into the engine.

Reuse an existing output format when practical. Inspect the current PSDL,
INST, texture and mod-loading support first. A small PSDL writer may be a
useful route, but do not assume parsers are also exporters. A minimal native
map format is acceptable when demonstrably simpler; document and version its
contract. Do not spend the project on an abstract format or general editor.

A format that later permits retail export is welcome, but full retail
compatibility must not delay the modern playable slice. Do not promise that
loading PSDL in rust-mm2 proves that the original retail executable works.

### Inspect both projects, without merging them

Read all applicable AGENTS.md instructions in each repository. Inspect any
existing mm2-sthlm files before scaffolding. Read rust-mm2's README,
docs/architecture.md, docs/modding.md and relevant current source. Inspect
world selection, city loading, the dev car/world, session cleanup, reset,
materials, screenshots and existing smoke facilities.

Do not trust old documentation over current code. Resolving a .glb file is
not proof of a working importer. A --city flag is not proof that an external
map can already run without original game data. Test the actual path early.

Prefer an explicitly provided engine binary or checkout. When none is
provided and network access permits it, obtain an isolated upstream checkout
in an ignored integration/cache directory or outside this repository. Record
the exact revision; do not silently track a moving main branch. Preparation
that downloads/builds the engine must be explicit and separate from map
build/validation. Do not commit an engine checkout, embed its workspace,
or make a mandatory submodule the normal map-build prerequisite.

Reusing a small pure-format crate through a pinned dependency is fine when
licensing and dependency boundaries permit. Avoid permanent sibling path
dependencies or building the Bevy game just to generate a map.

### You are authorized to make necessary upstream improvements

Do not stop merely because a generic loader/tool feature is missing. Develop
and test the smallest necessary engine change in a separate branch/worktree
(e.g. feat/external-map-support). Follow that repository's rules and quality
gates. Keep map-specific work committed in mm2-sthlm, and generic engine work
committed in rust-mm2. No destructive resets, bare git stash, force pushes,
or overwriting another agent's work. Use isolated build output if needed.

Do not change shared vehicle handling, upgrade Bevy/Avian, or refactor the
entire city pipeline. Other agents may be working on the engine concurrently.

If authorized repository access allows it, push the focused engine branch
and open a PR explaining the integration need. Do not auto-merge or push to
main unless separately authorized. You do not need to wait for a PR merge:
playtest against the exact integration revision and record it. Distinguish a
patched-engine result from one verified on upstream main.

If engine writes/pushes are unavailable, still implement and test a local
patch when permitted. Keep a clearly named patch plus its base SHA, rationale
and reproduction commands under integration/rust-mm2/. Do not silently apply
patches to a user's dirty checkout or maintain a permanent engine fork here.
Track temporary patches so they can be removed after upstream acceptance.

Record the compatible engine/tool revision, any patch checksum and supported
package schema in a small lock/compatibility file. Make play/smoke reject
incompatible inputs with actionable diagnostics rather than silently falling
back to the old dev world or London.

Do not build a second game engine, duplicate vehicle physics, or accept an
independent 3D viewer as proof that the map is playable in rust-mm2.

## 3. Acquire real source data; do not wait for perfect data

Start with a compact OpenStreetMap snapshot for the slice. Obtain actual
road centerlines, building footprints and available water/land/park geometry.
Use a bounded Overpass request or another legitimate downloadable extract.
Cache successful responses; use timeouts, limited retries and backoff.
Do not repeatedly hammer public endpoints or download all Sweden by default.

Retain source feature IDs, tags, complete referenced geometry and relevant
relation membership. Handle building/water multipolygons and holes. Reject
or report incomplete geometry rather than quietly inventing it. A lake
polygon can extend well beyond the query bounds: ensure waterfront data is
complete enough before clipping, or add a reviewed shoreline override based
on verified source geometry. Do not assume "no water polygon returned"
means that water is absent.

Use OSM heights/levels where available. Otherwise estimate heights using
explicit, deterministic rules. Mark estimates as estimates. Smooth,
approximate terrain is acceptable for this first slice; false precision is
not. Keep roads, buildings and water in one coherent vertical reference.

Stockholm municipal building data and Lantmäteriet terrain are optional
upgrades. Briefly check accessibility, but registration, payment, inaccessible
services or inconvenient formats must not block the OSM-based slice.

Store a small genuine source snapshot, or an equivalently reusable source
fixture, with proper attribution and licence information. Keep OSM-derived
geodata separately identified from engine code and independently authored
artwork. Preserve applicable ODbL obligations; do not relabel it as the
engine's licence. Avoid unnecessary metadata about individual contributors.

Record URLs, retrieval date, source timestamps when available, query/bounds,
checksums, licences and all important approximations in a source manifest.
Do not redistribute retail MM2 assets or scrape Google/Apple 3D imagery.

If network access is unavailable, first look for an existing verified local
snapshot. Continue implementing with clearly labelled synthetic test fixtures
when necessary, but do not claim those fixtures are geographic Stockholm or
mark real-data acceptance complete. Record the exact fetch command needed.
Never fabricate a successful download or the provenance of coordinates.

## 4. Use a small reproducible pipeline

Implement the narrowest useful flow:

    real source snapshot + parameters + reviewed overrides
        -> normalized city description
        -> generated geometry, collision, materials and map metadata
        -> portable, self-contained map package
        -> separately launched game session

Keep input sources, hand-authored overrides and generated output separate.
All improvements must survive regeneration. Never hand-fix only generated
meshes. Use stable IDs, deterministic ordering and a fixed variation seed.

A suggested layout, adaptable to repository conventions:

    README.md
    AGENTS.md                    # Only create if absent; preserve existing rules
    sources/                     # Small licensed snapshot + provenance
    config/                      # Bounds, projection, seed, generation rules
    overrides/                   # Reviewed, reproducible corrections
    assets/materials/
    assets/landmarks/
    src/                         # Map-generation code; not engine gameplay
    tests/fixtures/
    scripts/sthlm                # Fetch/build/validate/play/smoke entrypoint
    integration/rust-mm2/        # Revision lock, contract, optional patches
    docs/STATUS.md
    docs/SOURCES.md
    docs/INTEGRATION.md
    evidence/                    # Small reports/captures or artifact index
    dist/stockholm/              # Generated standalone package, ignored by Git

This layout is guidance, not a requirement to scaffold empty directories.
Commit useful source fixtures and authored assets; keep large regenerable
outputs, engine checkouts, binaries and caches out of normal Git history.
Make the source fixture available in the checkout or as an explicit verified
package so the first offline build does not depend on a live data service.

Keep the source description modest: road polylines with connectivity and
widths, building rings with height/style metadata, land/water polygons,
landmark placement, a spawn and a test route. No general GIS framework.

Use double precision for geographic processing, convert to local metres,
and subtract a local origin before producing float game coordinates.
Document axis directions and winding; test known relative positions.
Use a proper projected CRS or a documented, tested local projection suitable
for this small area. Do not treat latitude/longitude as metres or accidentally
apply the legacy PSDL coordinate mirror twice.

Choose a small practical generator stack: Rust, Python, or a limited mix.
Engine changes remain in the engine's language and architecture. Keep
dependencies documented and locked. Separate dependency bootstrap and fetch
from map build: once dependencies and source fixtures are present, generation,
validation, tests and normal game startup must not require network access.

The generated package must include all redistributable assets it references,
its map identity, schema/version information, attribution/licence notices,
and enough metadata to locate a valid spawn and apply its world settings.
Document coordinate axes/units, material and collision conventions, bounds,
water/reset policy and feature support. This metadata is map data, not a
Stockholm-specific engine code branch.

Prefer the existing mod layout if appropriate. For example, a generated
package might live at dist/stockholm/mod.toml with city/ and texture/ below
it. Verify the real loader's directory convention: an option that expects
the parent directory of mod folders must receive dist/, not the wrong nested
level. Do not invent manifest fields and assume the engine understands them.
Validate all referenced files, reject escaping paths, and produce a content
manifest/checksum. A deliberately tiny second test package should load through
the same generic mechanism without any Stockholm-specific engine changes.

## 5. Make it playable early, from this repository

Get one real street and a working vehicle into rust-mm2 before perfecting
the importer. Then extend the same export/load path to the connected slice.
The first integrated milestone should establish package loading, not just
produce source data that the engine cannot yet consume.

Use the shortest clean format/integration chosen above. Keep the normalized
city description separate from that export choice. Do not write a complete
retail exporter or glTF stack merely to satisfy a future possibility.

Reuse rust-mm2's controls, vehicle simulation, cameras, HUD and reset.
The slice must be playable without proprietary MM2 data, using the existing
procedural/dev vehicle or a minimal original placeholder body on the same
simulation. Implement the generic engine support if missing. With a supplied
legitimate installation, preserve the ability to use a real vehicle where
practical. No retail assets are copied into mm2-sthlm or its package.

Give Stockholm an explicit world/city identity. CLI access is sufficient;
menu work is optional. A failed/missing/corrupt map must produce a useful
error, never silent substitution of another world.

Provide commands run from mm2-sthlm along these lines:

    ./scripts/sthlm fetch
    ./scripts/sthlm build --offline
    ./scripts/sthlm validate
    ./scripts/sthlm play --engine /absolute/path/to/mm2
    ./scripts/sthlm smoke --engine /absolute/path/to/mm2

These are TARGET interfaces to implement, not existing commands. An equally
simple documented command family is acceptable. A wrapper should pass the
actual exported package, city selection and required runtime configuration
to the external executable. Forward useful game flags with a clear convention.
An engine-checkout option may be an explicit convenience, not a map-build
requirement. Do not hard-code a sibling ../rust-mm2 path.

Play must not secretly fetch data, compile a different map, or modify the
engine's source tree. Allow the binary path to be passed by flag or a clearly
documented environment variable. Report the exact package and engine revision
used. Pin integration tests to a known engine revision; a future engine update
is a deliberate compatibility check, not an automatic breaking dependency.

Ensure generated entities/resources use normal engine session ownership and
cleanup. Reset must return the player to the map-provided road spawn. Handle
leaving the slice or entering water deliberately. Do not leave an invisible
driveable platform across the lake.

## 6. Road geometry and collision are the critical path

Construct a genuinely connected driveable network, including a loop and
several turns. Target a useful circuit of roughly one kilometre if the
verified streets allow it; do not fake road connections just to hit a number.

Generate road widths from source tags or explicit conservative defaults.
Join intersection surfaces rather than overlapping unrelated road ribbons.
Deduplicate consecutive points and handle sharp corners and short segments.
Preserve grade separation: roads crossing in plan view are not automatically
connected. Exclude/cap difficult peripheral structures explicitly if needed;
do not flatten a bridge onto an unrelated street.

Use watertight-enough, consistently wound driving surfaces with matched
shared edges. No cracks, abrupt unintended steps, duplicate collision layers
or competing ground colliders under the road. Keep decorative markings and
small pavement detail out of collision. Buildings and retaining walls need
simple, stable static colliders; water does not get road collision.

A mostly level road network with modest authored slopes is acceptable here.
Accurate difficult bridges can wait. Keep simplifications and any deliberate
arcade widening in override data rather than hidden in the importer.

Choose the spawn from a validated road surface, aligned with a valid travel
direction and clear of buildings. Validate it with the actual vehicle's
clearance and suspension, not just a point inside the map bounds.

## 7. Make it unmistakably Stockholm

Generate buildings from real footprints, retaining courtyards where present.
Use actual heights where known and documented defaults otherwise. Create
simple pitched/flat roofs, plausible facade colours and repeated window/door
patterns. A modest shared material/texture atlas is enough. Batch geometry
sensibly; do not create one entity or material for every window.

Build an original low-poly Stadshuset landmark placed against its verified
footprint: a readable brick building mass, courtyard and tall tower. Its
silhouette and placement matter more than tiny decoration. Use verifiable
references for modelling, not unlicensed ripped meshes or textures.

Give the waterfront an intentional shoreline/quay, visibly distinct water,
and a few trees or simple props where appropriate. Start with clear daylight
and a readable chase camera. Roads, paving, roofs and walls should have
coherent materials rather than random debugging colours.

Prefer deterministic procedural art or original primitive-based modelling.
AI image generation is optional if available and permitted; no paid API,
external model or image tool may be required to finish. Do not substitute a
concept image for actual in-engine visuals.

After the first render, inspect ground-level and aerial views. Fix the most
obvious visual defects, regenerate and capture again. Do not stop at the
first technically successful screenshot if the city is visibly broken.

## 8. Evidence and acceptance

Maintain docs/STATUS.md with completed work, current blockers, the next
integrated action and exact reproduction commands. Record both repositories'
revisions when applicable. Save useful progress before context limits. Do not
rewrite either AGENTS.md to weaken existing rules.

Completion requires all of the following, with honest evidence:

A. REAL LOCATION: a real sourced street/shoreline layout, several connected
streets, roughly 30 or more actual building footprints, and a placed
Stadshuset landmark. Prefer more buildings when the data makes that easy,
but do not enlarge the scope merely for a count.

B. PLAYABLE SESSION: a command run from mm2-sthlm launches the actual external
rust-mm2 executable with this generated package, without proprietary game
data. Responsive vehicle controls; functioning chase camera, spawn and reset;
a traversable connected route; sensible map-edge/water behaviour; and clean
session teardown. A package or viewer alone does not pass this gate.

C. INDEPENDENCE AND REPRODUCIBILITY: a fresh mm2-sthlm checkout can generate,
validate and package its fixture without a rust-mm2 checkout or a game build.
The packaged map can be loaded by the documented compatible engine binary
from an unrelated directory, without the map's sources/generator beside it.
Include this portability check in integration evidence. Dependency bootstrap
and engine preparation are separate explicit steps. Once dependencies, data
and the compatible binary are installed, generation, tests and play work
offline. Rebuilding identical inputs produces identical normalized/package
content, excluding explicitly non-content logs/timestamps. Prove this with
a second clean build and checksum comparison, not only a fixed random seed.

D. TESTS: cover coordinate orientation/scale, polygon holes, deterministic
height defaults, malformed inputs, connected junctions, grade-separated
crossings, collision seams and spawn clearance. Network must not be required
for unit tests. Check building-road overlaps along the benchmark route.

E. ACTUAL DRIVING: run the real vehicle simulation on Stockholm geometry.
Exercise acceleration, braking, at least one turn and reset. Reuse an existing
bot/replay where possible; a small test-only waypoint follower is acceptable.
Aim for at least 60 seconds of simulated motion and 500 metres of meaningful
route progress. Log distance, progress, speed, finite-state checks, resets
and collisions. Do not teleport or directly animate the chassis to fake a
drive test. Test reset separately from continuous-driving evidence.

Validate the rest of the proposed loop with geometry probes and a drive
where feasible. Distinguish a complete driving traversal from a connectivity
check. Do not retune shared handling to make this task's smoke test pass.

F. VISUAL EVIDENCE: save actual in-engine screenshots showing (1) the vehicle
beside the waterfront, (2) Stadshuset, and (3) an elevated view of the street
layout. Record camera poses and commands. Inspect the images when the
environment supports it. Do not fabricate screenshots or claim visual QA
from a headless physics run. Missing GPU/display capability is an explicitly
unverified gate, not a pass; continue all other implementation and testing.

G. QUALITY GATES AND REGRESSIONS: respect each repository's own AGENTS.md.
Set up formatting/linting/tests appropriate to mm2-sthlm's chosen stack. Its
normal CI must not fetch live OSM data or require a GPU, retail assets, or an
engine checkout. Keep engine integration checks separate and clearly named.

For any rust-mm2 change, run its required checks in that checkout before each
commit, including where prescribed:

    cargo fmt --all -- --check
    cargo clippy --workspace --all-targets --all-features -- -D warnings
    cargo test --workspace

Keep the existing dev world working. Smoke-test London/SF when a legitimate
local installation is available; report unavailable tests as such. Record
baseline failures separately instead of hiding them or rewriting unrelated
systems. Do not claim completion while required gates remain unmet.

H. UPSTREAM HANDOFF: document every external engine change separately with
its branch/commit and PR, or reproducible patch plus base revision. Explain
why it is reusable and which package capability needs it. The map package
must not rely on an undocumented dirty engine worktree.

## 9. Execution order and stop conditions

Proceed in integrated increments:
1. Inspect both repos, acquire a genuine snapshot, establish baselines, and
   choose the narrow export/load contract. Record the integration revision.
2. Generate a minimal external package and drive one real street in the game.
   Implement a focused generic upstream change immediately if it blocks this.
3. Expand to the connected loop, building footprints and water.
4. Add Stadshuset, simple finished materials and boundary/reset behaviour.
5. Run tests, drive probes and screenshots; fix defects; document the launch.

Subagents are optional. Give them non-overlapping responsibilities, such as
data normalization, landmark generation or a focused upstream loader change.
Keep one lead responsible for package-to-game integration. Do not let parallel
research replace implementation. The two repositories may progress separately,
but successful integration must be demonstrated before calling the slice done.

Once the slice works, improve its visible quality and reliability rather
than expanding into an unfinished whole-city project. Do not end with only
"the foundation is ready" while the runnable result is still missing.

At handoff, report the actual mm2-sthlm branch/commit, package location,
exact generation/validation/play commands, compatible engine revision and
any upstream PR/patch. Include what is playable, source/licence locations,
screenshot paths, measured test results and remaining limitations. Separate
implemented, tested, unverified and deferred work. An environment limit is
an explicitly unmet gate with reproduction steps, not a fabricated pass.
A missing permission must not erase progress on the independent generator;
finish all permitted work and describe the precise remaining integration step.

## Source starting points

These are discovery/documentation references, not guaranteed direct-download
endpoints. Verify current access and terms; do not let browsing displace work.

- OSM querying: https://wiki.openstreetmap.org/wiki/Overpass_API/Language_Guide
- OSM query syntax: https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL
- OSM licence: https://www.openstreetmap.org/copyright
- Stockholm geodata: https://kartor.stockholm/kartor-geodata/
- Optional terrain: https://www.lantmateriet.se/sv/geodata/vara-produkter/produktlista/markhojdmodell-nedladdning/

Start implementing now. Deliver an independently built Stockholm map from
mm2-sthlm that I can actually drive in rust-mm2. Do not move the map project
into the engine, and do not stop at an unplayed export or another proposal.
