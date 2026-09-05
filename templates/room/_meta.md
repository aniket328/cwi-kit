---
kind: meta
audience: {{AUDIENCE}}
cadence: living
updated: {{DATE}}
---
# {{NAME}} — room router

{{KIND}} room, owner **{{OWNER}}**, audience **{{AUDIENCE}}**, mode {{MODE}}. Read this first, then `STATE.md`, then `AGENDA.md`.

| Shelf | What | Cadence |
|---|---|---|
| `STATE.md` | what is live, where, which version, who is on call, open risks, blocked-on | snapshot, overwrite |
| `MEMORY.md` | decisions with reasons, facts that would otherwise be re-litigated | ledger, append, dated |
| `AGENDA.md` | Next (ordered) / Parked (with unpark condition) / Done (dated) | living |
| `manifest.json` | repos, kits, servers, vault, people, parent, extra shelves | config |
| `log/` | one file per session or piece of work, `YYYY-MM-DD-<slug>.md` | append |
| `runbooks/` | repeatable procedures; scripts sit beside their prose | living |
| `memory/` | agent lessons; Claude's memory directory symlinks here | append |

Optional shelves come from the catalogue in cwi-kit `docs/ROOM-SCHEMA.md`: `events/ incidents/ bugs/ plans/ releases/ comms/ specs/ evidence/ reference/ archive/ tenants/ _scratch/ ACCESS.md README.md`. Anything else must be declared in `manifest.json` → `shelves_extra` with a reason, or `cwi room check` fails.

Rules: no secret in any file here, ever; `ACCESS.md` names keys, never values. `*.local.md` and `_scratch/` are gitignored and disposable. The Stop hook commits this room; the session end pushes it.
