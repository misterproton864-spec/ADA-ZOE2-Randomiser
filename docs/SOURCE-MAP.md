# Source map

The existing directory layout is retained to preserve Local.22's relative imports and data lookups.

| Path | Purpose |
| --- | --- |
| `app/main.py` | Entry point, initial game selection, startup self-test |
| `app/portable_paths.py` | Tester-specific state and build paths |
| `app/beta_support.py` | Original-input verification and diagnostic exports |
| `app/work/seed-v6/source/` | GUI, seed builder, encounter rules, validation, recovery |
| `app/work/seed-v6/runtime-fixes/` | Aumaan and Vic Viper runtime helper source/binaries |
| `app/work/ship-v5/` | Installer templates, audio builder and legacy helpers |
| `app/work/progression-v4/source/` | Progression and encounter capture |
| `app/legacy/` | Existing generators, archive tooling and authoring catalogues |
| `app/precompiled/finite-mosquito.obj` | Pinned original ADA helper object; C source is in `mosquito_runtime.py` |
| `packaging/` | Launcher source and baseline file provenance |
| `tools/` | Public distribution audit and packaging |

JSON/XML/TBL files here are lookup/validation catalogues. Original game files, generated seeds, game backups, local settings and research dumps are excluded.
