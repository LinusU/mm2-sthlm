# Current race integration

Latest upstream main was fetched over SSH at
`2dd688171553dd747339cc75e8ff40f6d455c3a7`. The separate ready
[PR #6](https://github.com/LinusU/rust-mm2/pull/6) branch builds at
`c4156b780969666f420375d9f5647f51913646a0`, including reusable native race QA
controls and a focused steep-heightfield rendering fix. All 1,869 engine
workspace tests, strict Clippy and formatting pass. The locally retained
binary is `.cache/engine/mm2-race-guide-latest`; SHA-256 is
`b2f82e39f58ab16032c4fbf59c6a2dc0851a4bbb871ebe32d984e6af788d8742`.

The guide supplies normal steering, throttle and braking to existing vehicle
physics. Native gates, laps, clocks and opponents remain authoritative.
Guided QA runs cannot earn player progression records. The engine contains no
Stockholm map content; its checkout stays outside this repository. The exact
base, revision, ready PR and cumulative patch checksum are recorded under
`integration/rust-mm2/`.

The adaptive road package uses 95 portable native PSDL pools. The coherent
0c69b559 package passes the full 102-gate waterfront drive on c4156b7 with zero
impacts, resets or recovery, plus second-city loading and missing-chunk
rejection. The same-engine unchanged Circuit1 comparison demonstrates the
hillside collision repair. The native identical-camera steep-fan comparison
also closes the former blue slit without altering map geometry. These reports
retain their own package/engine hashes.
Full race acceptance on the latest coherent package remains in progress;
initial legs or finishes using player recovery do not count.

Initial full race tests expose an actual opponent-driver issue: native AI
advances five-metre route samples using a 14-metre reach threshold, skipping
some corners/gate approaches. Rival escapes and an incomplete Professional
Checkpoint event are retained as diagnostics. A focused generic engine
follow-up is in progress; clean player pilots alone do not resolve it.

The common optional runner is `scripts/check-races.py --family checkpoint`,
`--family blitz` or `--family circuit`, documented in
[races/MATRIX.md](races/MATRIX.md). It checks both ranks, native parameter
CSV identities, actual Circuit lap counts, all gates and clean player physics.
Racing impacts and opponent recovery remain visible in the report.

The sections below are historical evidence at their recorded identities.

# Earlier expanded terrain integration

The earlier pulled upstream main was
`46f351b9186ad2d4d955e9d0d0a1ef1240d2332f`; PRs #1–#3 are merged.
The current tested package uses engine
`b3d9804489bdcd576dd4b85b3f40fec75c545071`, adding two focused fixes:
[PR #4](https://github.com/LinusU/rust-mm2/pull/4) gives intact movable props
valid convex collision bodies, and [PR #5](https://github.com/LinusU/rust-mm2/pull/5)
preserves upward winding for steep road/paving fans. PR #5 is stacked on #4.
Exact patches, checksums, tested revisions and preparation commands are in
`integration/rust-mm2/CONTRACT.md`. `scripts/prepare-engine` selects the tested
revision in `compatibility.json`.

The current ignored local binary is `.cache/engine/mm2`. Reproduce the latest
portable-package check with:

```sh
.venv/bin/python scripts/check-integration.py --engine .cache/engine/mm2 --output evidence/latest-engine
```

It finishes all 102 checkpoints over 1,503.8 m with zero impacts or resets,
finite state and four wheels. It also loads a second independent city and
rejects a missing package chunk. The package is copied alone into a temporary
mod root and launched from an empty working directory. Raw logs and identities
are in `evidence/latest-engine/`.

No Stockholm content or shared handling changes are in the engine. Normal map
CI has no dependency on the engine. The expanded package uses 55 independent
PSDL pools because the combined map exceeds the format's 16-bit vertex limit.
CPVS visibility is rejected for this extension. Native breakable props use the
engine's existing pathset/PKG/banger implementation.

Current commands and evidence are in [EXPANDED-STATUS.md](EXPANDED-STATUS.md).
The following original-slice report remains as historical evidence for its own
package checksum and engine revision.

# External engine integration

Upstream base: `1a568de7996be6813d32ab4f50d2f3dc150f258c`.
Tested integration revision: `cf5d4741100f78fc372398d36e06b228a3c0e938`.
Branch: `codex/smoke-motion-evidence`.
Ready-for-review PR: https://github.com/LinusU/rust-mm2/pull/1 (not auto-merged).

The map loads on the unmodified base through the existing PSDL/mod path,
without proprietary data. No custom city loader was needed. Two focused
engine commits add reusable **evidence tools** only:

- `a7015aa594791f28c830f9ca2157b41082348558`: solver travel, simulated time,
  finite/control/reset metrics; optional `--bot-speed` throttle/brake ceiling.
- `cf5d4741100f78fc372398d36e06b228a3c0e938`: count cruise teleports once and
  retain travel after a reset, with a production smoke regression test.

No Stockholm coordinates, assets, source processing or vehicle handling
changes exist in that branch. The speed ceiling changes driver inputs only.
The default engine driver is unchanged. The complete benchmark is verified
against this patched engine, **not upstream main**; base-engine interactive
play and the early one-street smoke are separately evidenced. The base's
30 m/s bot completed most of the loop with several reverse escapes, so it
is not used as full-loop acceptance evidence.

Explicit preparation (network/build work, separate from the map pipeline):

```sh
./scripts/prepare-engine /absolute/new/external/engine-checkout
# Then:
./scripts/sthlm play --engine /absolute/new/external/engine-checkout/target/debug/mm2
./scripts/sthlm smoke --engine /absolute/new/external/engine-checkout/target/debug/mm2
```

`prepare-engine` clones the engine outside this project and checks out the
exact tested SHA. It refuses existing directories and paths inside this map
repository. Alternatively obtain that revision's binary independently. The
original local engine checkout was read-only during this work; development
used `/private/tmp/mm2-sthlm-engine` with its own cloned build cache.

The original-slice local tested binary was:

```sh
/private/tmp/mm2-sthlm-engine/target/debug/mm2
```

A copy is retained in the ignored local map cache at `.cache/engine/mm2` for
convenient play after temporary engine-source cleanup. Neither binary nor
engine checkout is part of the repository/package; no sibling path dependency
exists. Regeneration/tests need only Python, pinned dependencies and OSM fixture.

For an offline patch handoff, `custom-map-probes.patch` contains both commits
against the base above. Its SHA256 and compatibility contract are recorded in
`compatibility.json`. Apply in a **clean separate checkout**:

```sh
git checkout 1a568de7996be6813d32ab4f50d2f3dc150f258c
git -c user.name=Codex -c user.email=noreply@openai.com \
    -c commit.gpgsign=false am --committer-date-is-author-date \
    /absolute/path/to/mm2-sthlm/integration/rust-mm2/custom-map-probes.patch
cargo build --locked -p mm2_app --bin mm2
```

That committer identity/date reproduces the documented unsigned commit IDs;
it is not needed when fetching the already-pushed exact revision. Local
commits used Codex attribution and unsigned commits because the configured
1Password signing socket was unavailable. No signing policy was weakened in
either repository. Remove the temporary patch after upstream acceptance and
perform an explicit compatibility re-test when adopting a new engine revision.

Required engine gates passed before each committed change:

```sh
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace
```

The final full workspace run passed 1771 tests across 92 suites. Local TCP
binds require execution outside the filesystem sandbox; an initial restricted
run failed on `Operation not permitted`, then a complete permitted run passed.
`evidence/engine-quality.json` records the results. Dev-world, London and SF
headless physics regressions passed. London/SF used the existing local retail
installation solely as a read-only test target; nothing was copied into the
map. The map's own play/visual/portability tests used no retail installation.

Independent integration checks are explicit and excluded from ordinary CI:

```sh
.venv/bin/python scripts/check-integration.py --engine /absolute/path/to/mm2
```

This copies only the package to a temporary mod root, starts from an empty
working directory, runs the whole physics loop, then loads a second original
synthetic `triangle` city through the same generic mod loader. The copied
package has no map sources/generator/config beside it. `evidence/portability.*`
and `second-map.log` record both tests.

`smoke` is strict: ≥500 m, ≥60 simulated seconds, all race gates complete,
finite state, throttle/brake/steer activity and no resets or bot recoveries.
Teleport/reset override flags are rejected on this continuous leg. Use
`play -- --headless` for separate reset/restart/water probes. Unknown/corrupt
package or unlocked engine revision fails with actionable diagnostics.
