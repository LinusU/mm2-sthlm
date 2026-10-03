# Working in mm2-sthlm

When starting a new session, check tracked uncommitted changes and ask Linus
before continuing if any exist. Untracked files can be left alone.

Keep map generation independent of rust-mm2. Never copy engine or vehicle
physics into this project. Engine improvements belong in a separate branch
or checkout, with a tested revision and patch/PR under integration/rust-mm2.

Run before committing map code:

```sh
.venv/bin/ruff format --check src tests scripts/check-integration.py
.venv/bin/ruff check src tests scripts/check-integration.py
.venv/bin/python -m unittest discover -s tests -v
./scripts/sthlm build --offline
./scripts/sthlm validate
```

Keep source snapshots, overrides and generated output separate. Fix source or
generator, never only dist meshes. Normal CI must not require network data,
a GPU, retail content, or an engine checkout. Never claim screenshots from a
viewer or physics-only run as in-engine visual evidence.

When addressing GitHub review comments, push separate commits for each class.
End GitHub comments with /ChatGPT. Avoid "and" in commit subjects. Open regular,
ready-for-review PRs. Never scan Linus's whole home directory. Never spawn Sol
subagents unless specifically instructed; do not delegate by default.
