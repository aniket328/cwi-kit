---
kind: meta
audience: public
cadence: living
updated: 2026-09-05
---
# cwi-kit — router

Studio kit, owner **cwi**, public. This repository is tooling and conventions; it holds no data and is safe on any machine.

| Path | What |
|---|---|
| `bin/cwi` | the executable; `scripts/install.sh` symlinks it to `~/.local/bin/cwi` |
| `cwi_kit/` | the package: `schema` (vocabulary) · `room` (find, check) · `ws` (init, meta, link) · `sync` · `doctor` · `registry` · `bootstrap` · `hook` · `gitx` · `manifest` · `frontmatter` · `cli` |
| `templates/room/` | the four core markdown files and the room `.gitignore` |
| `templates/ws/` | the `CLAUDE.md` / `AGENTS.md` shims a workspace gets |
| `docs/ROOM-SCHEMA.md` | the schema, human version; the source of truth for the catalogue |
| `tests/` | `python3 -m unittest discover -s tests` |
| `VERSION` | semver; a schema change bumps the minor |

Change the catalogue only here, then release; rooms declare local extras in their manifest instead of inventing shelf names.
