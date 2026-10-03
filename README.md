# mm2-sthlm

An independent, real-data Stockholm map project. Generate a portable PSDL mod
and drive it in a **separately built** [rust-mm2](https://github.com/LinusU/rust-mm2).
No retail MM2 assets are needed. This repository contains no engine checkout
or vehicle physics.

The first slice covers Stadshuset, eastern Norr Mälarstrand, Kungsholmstorg
and Hantverkargatan. It includes 407 sourced building footprints, a 1.53 km
connected benchmark loop, the actual waterfront, an original schematic
Stadshuset model, shared facade/material textures and physical edge barriers.

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
./scripts/sthlm fetch
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

The package is `dist/stockholm/`. Copy that folder beneath an arbitrary mod
parent and load it from any working directory:

```sh
/absolute/path/to/mm2 --mods /tmp/my-maps --city stockholm --no-profile \
  --spawn=-31.4881664128,3.5,138.0584324824,-90.6975907056
```

See [integration and exact engine preparation](docs/INTEGRATION.md),
[package contract](integration/rust-mm2/CONTRACT.md),
[source provenance and approximations](docs/SOURCES.md), and
[measured acceptance status](docs/STATUS.md). Screenshots and logs live in
[evidence](evidence/). Generated output is deliberately ignored by Git.

Code and original procedural artwork are MIT; OSM data and derived geographic
database/geometry are ODbL 1.0, © OpenStreetMap contributors. The package carries
its own attribution notice and reusable normalized database. No retail assets,
Google/Apple imagery or downloaded third-party landmark meshes are included.
