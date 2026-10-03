# Overnight Stockholm playability work

Authorized 2026-10-03 by Linus: one GPT-6.1 Sol Medium worker for each of eight
tracks; coordinator integrates validated increments straight to main and pushes
origin using SSH. Aim: enjoyable, connected driving without glitches, with a
Stockholm layout and skyline the player recognizes. This supersedes exact
OSM positioning for road paint and signal designs, not geographic road topology.

The first baseline is map `3724732`, separate tested engine
`b3d9804489bdcd576dd4b85b3f40fec75c545071` in `.cache/engine/mm2`.
User screenshots remain untracked. Worktrees are outside the map checkout.
Existing road paint is native render-only PTH ribbons, not physical objects;
the requested replacement is texture-based native road surfaces regardless.

Hourly thread heartbeat: `stockholm-overnight-improvements`. Continue through
the night, pausing the heartbeat after completion or at 09:00 Europe/Stockholm
on 2026-10-04. Keep actual completion separate from scheduled intention.
The desktop host must remain running for its local work to execute.

## Work queue

At most three workers run concurrently with the coordinator, matching the
four available agent slots. There are eight separate prepared managed worktrees
under `/Users/linus/.codex/worktrees/`; each contains `mm2-sthlm`.

| Track | Agent / worktree suffix | Initial state | Ownership / acceptance |
| --- | --- | --- | --- |
| Road textures and heuristic signals | `/root/overnight_road_surfaces` / `overnight-road-surfaces` | Handoff cb325fe; root native-layer fix pending | RoadNoSidewalks aligned road textures, asphalt detail, graph-based intersection designs, movable signal props; replace PTH paint; checked native UVs and drives. |
| Smooth road profiles | `/root/overnight_road_smoothing` / `overnight-road-smoothing` | Handoff 168e285; root integration pending | `elevation.py`, source-aware profiles, numerical citywide diagnostics, continuous junctions and upper/lower levels; worst-road drives. |
| All bridges | `/root/overnight_bridges` / `overnight-bridges` | Code handed off; root integration pending | Researched source-ID inventory, simple bridge-specific structures, coherent deck ends, underside/lower-road clearance; multiple actual crossings. |
| Tunnels and missing highways | `/root/overnight_tunnels` / `overnight-tunnels` | Running | Research Klara/Söder/Lundagatan and other sourced internal tunnels; include in-bound motorway/trunk links, portals, underground corridors and level separation. Preserve excluded islands/boundary; no phantom road from intersecting XY. |
| Gamla Stan cobblestone | `/root/overnight_gamla_stan` / `overnight-gamla-stan` | Running | Researched historic street/square ground cover: original cobblestone native materials, preserve real parks and water, no blanket grass replacement outside Old Town. Cooperate with road textures. |
| Shallow ponds | `/root/overnight_ponds` / `overnight-ponds` | Running; native basin drives pass | Inventory source ponds/fountains including Kungsträdgården, use local terrain-relative banks and shallow driveable basin floors; compare legitimate retail London semantics read-only, copy no retail assets. Ensure shallow water does not trigger ocean recovery. |
| Thirty landmarks | `/root/overnight_landmarks` / `overnight-landmarks` | Running; 30 inventory/26 new models | Pick/research exactly 30 included landmarks; source IDs/positions/reference image links, restrained original silhouettes and materials. Preserve existing authored Stadshuset/courthouse/church/manor/bar; recognizable native skyline captures. |
| District facades with doors | `/root/overnight_district_facades` / `overnight-district-facades` | Running; native door prototype passes | Research district aesthetics/photos; varied original plaster/brick/roof/window materials, ground-floor doors using real native facade semantics. Coordinate landmark overrides, retain restrained MM2 art style. |

Queued agents must be spawned using model `gpt-6.1-sol`, reasoning effort
`medium`, fork_turns `none`, with their own worktree path and this full task.
Do not leave queued tracks as documentation-only work: implement and test them.
Use initial existing worktree branch as-is; before starting a queued worker,
bring its clean checkout to latest main to consume integrated dependencies.
Do not discard old or new worktree changes. Inspect statuses before rebasing.

## Coordinator rules

- Workers do not change main or push it independently. Coordinator owns shared
  `src/sthlm.py` export/validator hooks and `src/expanded.py` source normalization.
  Module agents send exact hook patches. Coordinate APIs before integration.
- Smoothing defines source-aware roadway heights consumed by bridges, road
  textures, tunnels and props. Keep independent crossing layers separate.
- Bridge inventory must include unnamed/internal viaducts and trunk roads;
  explicit Tranebergsbron, Essingen, Lidingö and south outward bridge exclusions
  persist even where the drawn mask happens to cover a piece of bridge.
- Keep `.venv` tools and the compiled engine shared read-only. Every worker
  builds into its own `dist`; do not share Cargo targets or replace the binary.
  Engine fixes belong to separate engine branches/ready PRs with exact SHA.
- Research sources support dimensions/appearance as approximate authored art.
  Never redistribute Google/retail photographs or retail textures/models.
  AI bitmap artwork may use the imagegen skill; save assets plus prompt/provenance
  in the repository, make offline build deterministic and independent of that tool.
- Run AGENTS.md Ruff/full tests/offline build/validate before map code commits.
  Check actual external engine vehicle drives and native screenshots for each
  feature class, then repeat the full benchmark/relocated package acceptance.
  Do not interpret geometry tests or standalone renderers as engine evidence.
- Record each track's research, overrides, code API, exact tested revision,
  remaining failures, repro commands and actual evidence. Report partial
  completion candidly. Keep this file updated so hourly continuation can recover.

## First coordinator increment

Source normalization now selects all complete internal motor-road bridge ways
within the approved mask, including unnamed viaducts and Centralbron trunk
carriageways, while rejecting explicit boundary bridges, pedestrian-only
connections, tunnels and incomplete geometry. Motorway/trunk road classes are
retained for subsequent tunnel/highway work. Targeted boundary regressions
cover those inclusions/exclusions. Ruff and 90 offline tests pass. The first build exposed a named-only
deck-group assumption for unnamed viaducts; the smoothing worker is fixing
that grouping before this source increment can be committed. This is not
yet an accepted bridge-driving result. Bridge-specific deck/underpass work
remains assigned to its worker.

### Continuing coordination notes

- First source audit identified incorrect Beckholmen island reference and
  omitted Strömsborg. Corrected source-component references link to real
  bridge endpoints: Beckholmsbron way5173793 endpoint35970109;
  Strömsborgsbron way5120305 endpoint180940 and named islet way4879618.
  Normalization edits remain in root pending elevation/bridge integration.
- Road surface worker proved native UVs in a synthetic in-engine crossroads
  and a full Stockholm export. Original imagegen asphalt asset is saved with
  prompt/provenance. Bridge undersides must consume the actual textured
  road facets, rather than separately tessellating the deck above them.
- Smoothing inventory baseline: 287 ordinary roads over16% grade, 2,367 over
  target longitudinal curvature. Iterative graph fairing is converging;
  treat intermediate diagnostic numbers as unfinished until actual driving.
- Root's tracked changes in expanded.py/test_expanded.py are authorized ongoing
  coordinator work, not unrelated user changes. Preserve them across hourly
  continuation; agent changes live only in assigned external worktrees.

### Prototype integration gate

The first 7,733-road prototype builds and passes99 offline tests, but package
validation rejects shared junction heights after bridge clearance adjustments.
Do not commit that prototype or claim an accepted driving run: full-loop smoke
correctly stops at validation. The old per-way lift envelope restarts at every
source junction, leaking raises through the city. Root has replaced it with
one source-node height variable and distance-limited graph envelopes, with an
interior-junction regression. Required integrated rebuild is pending.
The smoothing worker is simultaneously constraining common tangent planes in
its solver because post-hoc planes could reintroduce bumps. Do not overwrite
root's new bridge clearance function when copying older bridge worktree files.
Root owns the clearance hook inserted after smooth() in elevation.apply;
preserve that hook when recopying a newer elevation.py from the worker.

### Native stacked-deck correction

Root's first textured/smoothed package passed112 offline tests and its full
1,503.6 m circuit (102/102 gates, zero impacts/resets, four wheel contacts).
Targeted upper/lower Centralbron probes nevertheless failed: the combined
bridge XY union collapsed source layers despite numerical clearance passing.
Do not treat that package as accepted bridge work. `render_bridge_layers`
now unions decks per source layer and gives approach pieces their connected
bridge layer, with a regression preserving both heights at one XY crossing.
Structure groups also separate source layers. Fresh build/native retests are
pending; logs in evidence/overnight-driving retain the failed first probes.
Smoothing screenshots in evidence/road-profiles belong to isolated RoadFan
handoff168e285, not the root combined package. Pustegränd finalzero wheel
contacts remains an open crest/mesh probe. Root main pending edits are all
coordinator-owned continuing work; never discard them as unrelated dirty files.

### First accepted map increment

The integrated native textured package now passes the full102-gate circuit,
separate package relocation, second-city load and missing-part rejection.
Targeted upper Centralbron59.2m, lower Vattugatan59.9m, and steep Tryckerigatan
57.7m source drives all have zero impacts/resets and four wheel contacts.
Native centralbron-layers.png was captured and inspected. Package/source hashes
and scoped limitations are in evidence/overnight-driving/acceptance.json.
Height-incompatible overlaps receive separate native surface groups even when
OSM assigns both ways the same relative layer. Owner-scoped tangent planes keep
upper approach seams from pulling nearby lower road surfaces. Seven native deck
surface groups represent the three source layers in this build.

All eight requested GPT-6.1SolMedium workers have now started. Landmarks handoff
0916a1e and OldTown bb15be4 are ready; tunnels module/hook handoff is ready;
ponds and districtfacades are finishing native acceptance. Their shared hooks
are not yet integrated into root's accepted road-era package. Preserve pending
untracked tunnels module/config/tests/docs/script for the next increment.
