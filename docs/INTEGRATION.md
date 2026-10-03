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

The current local tested binary is:

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
