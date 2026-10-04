# Native race acceptance matrices

This explicit developer QA command loads all ten Checkpoint events at both native difficulty ranks using an immutable copied map and a copied, hashed engine binary. It is excluded from ordinary offline CI. It uses each exported `.opp` QA guide, retains the real four-to-seven opponent roster, and is ineligible for player progression records.

```sh
.venv/bin/python scripts/check-checkpoint-races.py \
  --engine /private/tmp/checkpoint-acceptance-engine/mm2-occurrence \
  --mods /private/tmp/checkpoint-final-mods \
  --out /private/tmp/checkpoint-complete-matrix \
  --workers 1 --require-finish
```

Full-course runs allocate at least 12,000 updates, then scale to source gameplay length at eight metres per second plus a one-minute allowance. `--frames N` overrides this budget. Omitting `--require-finish` produces 2,400-update initial-leg diagnostics, which cannot establish full-course completion. An optional `--bot-speed N` caps player inputs only and is explicitly recorded; opponent actors and native difficulty parameters remain unchanged.

The common entry point supports each ten-event family. Keep a different empty
output directory for every matrix so failed diagnostics remain available:

```sh
.venv/bin/python scripts/check-races.py --family blitz \
  --engine /path/to/mm2 --mods /path/to/immutable/mods \
  --out /private/tmp/stockholm-blitz-matrix --require-finish
.venv/bin/python scripts/check-races.py --family circuit \
  --engine /path/to/mm2 --mods /path/to/immutable/mods \
  --out /private/tmp/stockholm-circuit-matrix --require-finish --bot-speed 12
```

Circuit budgets multiply source length by the actual native difficulty's lap
count. Acceptance verifies that lap count explicitly. The parameter CSV is
hashed alongside the catalog, guide, package manifest and engine binary.
Blitz retains its authored countdown; finishing after native timeout fails.
Guided driver times are useful repeatable measurements, but do not establish
human clock difficulty or progression eligibility.

Acceptance requires native process success, finite four-wheel movement, positive physical distance, zero player resets, zero `p_rec` reanchors/escapes, positive matching gate counts, native `race=Complete`, and a finished outcome. A finish with any recovery is rejected. Impacts and native per-actor gate/finish/escape/reanchor counts remain separate diagnostics. Long budgets include post-finish coasting/AI impacts; native `sim` is the player finish time. Absence of `p_rec` is the native report convention for zero recovery.

Each `report.json` records binary, checksum-manifest, catalog, guide and raw-log SHA-256 identities; exact commands; frame budgets; wall times; native smoke summaries; rejection reasons; and explicit initial-leg versus complete-course scope. It verifies binary/catalog/manifest immutability after the matrix. Preserve failed diagnostic runs under separate output directories instead of overwriting them.
