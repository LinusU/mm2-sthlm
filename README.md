# mm2-sthlm

An independent, real-data Stockholm map project. Generate a portable PSDL mod
and drive it in a **separately built** [rust-mm2](https://github.com/LinusU/rust-mm2).
No retail MM2 assets are needed. This repository contains no engine checkout
or vehicle physics.

Latest measured status and remaining defects: [2026-10-04 morning handoff](docs/MORNING-2026-10-04.md).

The default map covers Kungsholmen, Södermalm, Djurgården and the central
Stockholm mainland within the agreed boundary. It contains 8,025 sourced road
ways, 10,770 building footprints, real RH2000 terrain, internal bridge decks,
and 1,585 independent breakable tree props. The original waterfront
benchmark remains available as a separate QA fixture. The source now includes
100 simplified landmarks, tunnels, local shallow ponds and district facades. `--profile stadshuset` builds the original flat
comparison slice.

Bootstrap once with Python 3.14:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Generate and validate the checked-in OSM fixture **offline**:

```sh
./scripts/sthlm build --offline
./scripts/sthlm validate
.venv/bin/python -m unittest discover -s tests -v
```

Optional explicit source refresh (changes the source manifest and generation):

```sh
.venv/bin/pip install -r requirements-acquisition.txt
.venv/bin/python scripts/acquire-expanded.py
.venv/bin/python scripts/acquire-terrain.py
# Original small OSM fixture only:
./scripts/sthlm fetch --profile stadshuset
```

Launch the independently built engine:

```sh
./scripts/sthlm play --engine /absolute/path/to/mm2
./scripts/sthlm smoke --engine /absolute/path/to/mm2
# Forward game options after --, for example:
./scripts/sthlm play --engine /absolute/path/to/mm2 -- --headless --frames 400 --reset-at 650
```

`MM2_ENGINE` can replace `--engine`. The wrapper checks package checksums and
engine revision, prints both identities and attribution, mounts **dist/**
(the parent of mod folders), sets the map-provided spawn and starts Stockholm.
Play does not build, fetch or modify the engine. It briefly probes the binary's
embedded revision through its no-GPU dev smoke interface before launch.

W/S accelerate/brake or reverse; A/D steer; Space handbrake; R reset; C cycles
chase/cockpit/free camera; F4 restarts; Escape exits. The red procedural car
uses rust-mm2's existing Avian vehicle simulation. `--bot` drives through
ordinary control inputs. Smoke results are evidence, not a substitute for
interactive driving.

The generated native minimap uses cyan water, beige land, green parks and
cream-white roads, following the SF/London reference style. Tab cycles the
corner map sizes/off; E zooms, F toggles rotation, and Q opens the full-screen
pause map. Player and race markers use original generated assets. See
[minimap generation and evidence](docs/MINIMAP.md).

Thirty native races are generated: ten each of Checkpoint, Blitz and Circuit,
ordered from shorter introductions to longer city tours. The final Circuit is
an in-boundary route inspired by the Stockholm Marathon. Race driving and timer
calibration are still in progress; see [race export](docs/races/EXPORT.md),
[Checkpoint designs](docs/races/CHECKPOINT.md), [Blitz designs](docs/races/BLITZ.md)
and [Circuit designs](docs/races/CIRCUIT.md).

```sh
/absolute/path/to/mm2 --mods "$PWD/dist" --city stockholm --no-profile --car sthlm_racer --event blitz:0
/absolute/path/to/mm2 --mods "$PWD/dist" --city stockholm --no-profile --car sthlm_racer --event checkpoint:0
/absolute/path/to/mm2 --mods "$PWD/dist" --city stockholm --no-profile --car sthlm_racer --event circuit:0
```

Event indices run from `0` to `9`; add `--pro` for Professional. These commands
use the original generated race car and normal player controls. Optional guided
native QA matrices are documented in [race acceptance](docs/races/MATRIX.md);
their bot runs are separate from player progression records.

The package is `dist/stockholm/`. Copy that folder beneath an arbitrary mod
parent and load it from any working directory:

```sh
/absolute/path/to/mm2 --mods /tmp/my-maps --city stockholm --no-profile \
  --spawn=-31.4881664128,4.5897098965,138.0584324824,-90.6975907056
```

See [integration and exact engine preparation](docs/INTEGRATION.md),
[package contract](integration/rust-mm2/CONTRACT.md),
[source provenance and approximations](docs/SOURCES.md), and
[measured expanded acceptance](docs/EXPANDED-STATUS.md), and
[expanded-map generation](docs/EXPANDED.md), [terrain provenance](docs/TERRAIN.md),
and [the agreed boundary](docs/BOUNDARY.md). Screenshots and logs live in
[evidence](evidence/). Generated output is deliberately ignored by Git.

Terrain data is CC BY 4.0, ©Lantmäteriet, with resampling and mesh modifications
described in the package attribution. Code and original procedural artwork are MIT; OSM data and derived geographic
database/geometry are ODbL 1.0, © OpenStreetMap contributors. The package carries
its own attribution notice and reusable normalized database. No retail assets,
Google/Apple imagery or downloaded third-party landmark meshes are included.
