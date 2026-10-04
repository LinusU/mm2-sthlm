# Old Town stone surfaces

`oldtown.py` authors muted grey granite setts on sourced Stadsholmen,
Riddarholmen and Helgeandsholmen land. The profile lives in
`config/overrides/oldtown-surfaces.json`; source snapshots remain unchanged.
This is an approximate historical streetscape treatment, not a surveyed
street-by-street material inventory.

## Research and original artwork

- [Visit Stockholm district guide](https://professionals.visitstockholm.com/documents/226/QUIZ_Stadsdelar_ENG_2023.pdf)
  describes the narrow winding cobblestone streets and Stortorget.
- [Official Stortorget page](https://www.visitstockholm.com/o/stortorget/)
  establishes the square's location and historical role. Reference photographs
  were viewed for material appearance; none of their pixels are distributed.
- [Stockholm's pocket park plan](https://start.stockholm/globalassets/start/om-stockholms-stad/sa-arbetar-staden/natur-parker-och-gronomraden/parkplan-sodermalm-del-2---fickparker-och-tappor.pdf)
  describes Junotäppan's green character and playground.
- The original 500×500 pixel procedural texture and provenance live in
  `assets/materials/oldtown/`. Fifty courses of staggered granite setts repeat
  seamlessly over the native ten-metre world-UV period. No retail or photographic
  assets are used. Builds require no image service or network.

The source inventory includes Stortorget way332635708, Järntorget way27345570,
Mynttorget way25033140, Junotäppan way326282776, Logården way24968391,
Bollhustäppan way178895733 and Strömparterren way120288396. All complete source
ways tagged park, garden, playground, grass, flowerbed, wood, scrub, grassland,
water or railway are excluded from the stone ground mask. There are 23 protected
features covering 19,998.16 m², with 413,246.39 m² of stone land in this snapshot.
Water and land outside the three actual islands are excluded.

The work found a pre-existing normalization error: the old Helgeandsholmen
reference selected Stadsholmen. The verified reference `(18.0686,59.3284)`
lies in its actual sourced 29,798 m² land component. The coordinator owns this
reference correction and its source-normalization regression.

## Integration API

- `apply(source,cfg,city)` stores `city.oldtown` coverage/provenance and annotates
  historic roads with `sthlm:surface=oldtown_setts`.
- `material_for(road)` chooses `sthlm_oldtown_setts`; major motor routes,
  bridges, tunnels, Skeppsbron, Munkbroleden, Centralbron and Munkbrogatan
  retain asphalt. Old Town road classification suppresses lane paint.
- `partition(geometry,city)` returns disjoint stone/remaining land or shoulders.
- `road_partition(geometry,city)` partitions native fan remainder; asphalt
  source-road footprints win intersections. The cached mask is computed once.
  Both materials use the existing identical seam-height callback and native
  physical RoadFan attributes. There are no PTH paint overlays or stone objects.
- `write_textures(texture_directory)` writes the original deterministic image.
- `eligible_pedestrian_ways(source,cfg,land=selected)` returns explicit source
  IDs and widths for historic pedestrian alleys entirely on the actual islands
  outside their protected green areas. Default width is 3.5 m; width/est_width below 2.5 m,
  steps, footway, path, area=yes, closed plazas, bridges and tunnels are excluded.
  Normalization retains the ordinary five-metre minimum outside those IDs.

Minimal coordinator patches are `oldtown-hook.patch` (material/ground hooks)
and `oldtown-alley-hook.patch` (scoped source alley inclusion). Apply the first
before the second. The latter adds `cfg.allowed_surface_ways` as an ID-to-width
map. Shared `sthlm.py`, `expanded.py`, `elevation.py`, road profiles and road
surface changes are deliberately absent from the standalone module commit.
Source metadata for 476 pedestrian/footway/steps candidates is recorded in
`oldtown-pedestrian-source-inventory.json`; this is an audit, not an inclusion
list. The integrated local export retained 177 historic pedestrian segments
and classified 245 source road segments as stone.

## Verification and reproduction

Run the repository's full formatting, lint, tests, offline build and validator
with both coordinator hooks integrated. Local integration passed 120 tests,
Ruff, offline build and package validation: 7,916 roads, 55 parts, 58,073 rooms,
1,278,426 vertices and 2,064,709 triangles. The isolated module also passes all 96 baseline-plus-module tests
without the shared hooks.

Native reproduction (explicit external engine; ordinary CI does not run it):

```sh
.venv/bin/python scripts/check-oldtown.py \
  --engine /Users/linus/coding/mm2-sthlm/.cache/engine/mm2 \
  --output evidence/oldtown/repro --visual
```

The tested external engine is `b3d9804489bdcd576dd4b85b3f40fec75c545071`.
`evidence/oldtown/build-inventory.json` records the binary/source/export hashes
and the exact limits of the evolving local coordinator integration state.
Final module metadata reproduces the tested exported metadata exactly and the
original artwork matches the exported texture byte-for-byte.

Actual native screenshots in `evidence/oldtown/steep/` show Stortorget covered
in stone, Junotäppan still green inside the block, and stone beside Helgeand's
preserved planted patches. These are actual engine captures, not viewer images.
High overhead views show minification aliasing in the fine stone repeat; this
remains a visual limitation of the tested native rendering/material pairing.

Actual vehicle drives on the 38.63 m, 8.78% Storkyrkobrinken incline section
travelled 27.6 m uphill and 37.7 m downhill, with `finite=true`, `wheels=4/4`,
zero impacts and zero resets in both directions. `final-drive/results.json`
contains source-section coordinates, commands and enforced acceptance checks.
This proves short incline traversals, not a completed Old Town circuit.
An initial nine-second blind-throttle run on a shallow section overshot its
bend and caused impacts; its observed summary is retained explicitly in
`initial-overshoot-records.json`. The original full initial logs were overwritten
before that retention request, so their limited provenance is stated there.

Mapped green polygons are preserved wholesale, even where a park also contains
small paved paths. Unmapped courtyard planting cannot be inferred from this
snapshot. Optional missing/incomplete island or green data is reported in
`city.oldtown`; no network data, GPU or engine is needed for normal CI.
Final acceptance against a committed integrated main revision is coordinator
owned and must be repeated after its shared road-height changes are merged.

## Current committed road-base integration

`docs/oldtown-current-hooks.patch` supersedes the two earlier hook patches and
is based on coordinator commit `bd7566b`. It changes only `expanded.py`,
`sthlm.py` and the road classification/fan material emission blocks of
`road_surfaces.py`. Bridge layer/color grouping, source station callbacks,
fan seam-height calculations and native triangle sinks are unchanged.
Elevated groups always retain asphalt, including approaches over stone land.
The fan remainder area report retains its full area after material partitioning.

`tests/test_oldtown_integration.py` checks stone/asphalt physical coverage,
height continuity, native triangle collection and elevated material isolation.
`evidence/oldtown/current-base/preservation-checks.json` verifies that the
bridge grouping and callback/sink ASTs match `bd7566b`, and that `elevation.py`
and `road_profiles.py` match it byte-for-byte. The hook-integrated full suite
passes 124 tests plus Ruff. The required current-base offline build and
validation also pass: 55 parts, 58,258 rooms, 1,283,372 vertices and 2,069,143
triangles. Both source incline native drives pass again with four grounded
wheels, no impacts and no resets. Results are recorded alongside those
preservation checks. The coordinator applies
these hooks to its combined tunnel/Old Town integration before final acceptance.

### Coordinator paving-overlap correction

The first current-base hook reassigned `paving` to its non-stone remainder,
then subtracted only that remainder from `land`. Already emitted `stone_paving`
was therefore emitted again as stone land. Both material partitions are now
subtracted before land emission, for expanded and slice paths. The focused
actual-exporter regression initially observed 1,542.273 m² emitted onto a
1,400 m² fixture, then passes with full area conservation and pairwise disjoint
road, stone paving, other paving, stone land and grass surfaces.

`docs/oldtown-current-hooks.patch` includes the correction;
`docs/oldtown-paving-fix.patch` is the correction alone for an already integrated
hook. No helper or native road/bridge rendering changes were introduced.
Earlier current-base build/native evidence predates this correction and does
not prove the absence of duplicated ground. The corrected scope is covered by
Ruff, three focused tests and all 125 offline tests; the coordinator repeats the combined
export and package acceptance. No worker broad rebuild was requested for this
small subtraction correction.
