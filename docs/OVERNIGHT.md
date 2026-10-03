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
| Road textures and heuristic signals | `/root/overnight_road_surfaces` / `overnight-road-surfaces` | Running | RoadNoSidewalks aligned road textures, asphalt detail, graph-based intersection designs, movable signal props; replace PTH paint; checked native UVs and drives. |
| Smooth road profiles | `/root/overnight_road_smoothing` / `overnight-road-smoothing` | Running | `elevation.py`, source-aware profiles, numerical citywide diagnostics, continuous junctions and upper/lower levels; worst-road drives. |
| All bridges | `/root/overnight_bridges` / `overnight-bridges` | Running | Researched source-ID inventory, simple bridge-specific structures, coherent deck ends, underside/lower-road clearance; multiple actual crossings. |
| Tunnels and missing highways | `overnight_tunnels` / `overnight-tunnels` | Queued, next available slot | Research Klara/Söder/Lundagatan and other sourced internal tunnels; include in-bound motorway/trunk links, portals, underground corridors and level separation. Preserve excluded islands/boundary; no phantom road from intersecting XY. |
| Gamla Stan cobblestone | `overnight_gamla_stan` / `overnight-gamla-stan` | Queued | Researched historic street/square ground cover: original cobblestone native materials, preserve real parks and water, no blanket grass replacement outside Old Town. Cooperate with road textures. |
| Shallow ponds | `overnight_ponds` / `overnight-ponds` | Queued | Inventory source ponds/fountains including Kungsträdgården, use local terrain-relative banks and shallow driveable basin floors; compare legitimate retail London semantics read-only, copy no retail assets. Ensure shallow water does not trigger ocean recovery. |
| Thirty landmarks | `overnight_landmarks` / `overnight-landmarks` | Queued | Pick/research exactly 30 included landmarks; source IDs/positions/reference image links, restrained original silhouettes and materials. Preserve existing authored Stadshuset/courthouse/church/manor/bar; recognizable native skyline captures. |
| District facades with doors | `overnight_district_facades` / `overnight-district-facades` | Queued | Research district aesthetics/photos; varied original plaster/brick/roof/window materials, ground-floor doors using real native facade semantics. Coordinate landmark overrides, retain restrained MM2 art style. |

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
