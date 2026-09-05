# Room schema, version 1

A **room** is the operations folder every product, client, kit, RSI site and the studio itself keeps. It is plain committed markdown plus one JSON manifest. An agent that can read one room can read all of them, because every room has the same shape.

## Core entries, mandatory

| Entry | Kind | Cadence | Holds |
|---|---|---|---|
| `_meta.md` | meta | living | router: what this room is, who may read it, shelves in use |
| `STATE.md` | state | snapshot, overwritten | what is live, where, which version, who is on call, open risks, blocked-on |
| `MEMORY.md` | memory | ledger, append-only, dated | decisions with reasons; facts that would otherwise be re-litigated |
| `AGENDA.md` | agenda | living | Next (ordered) / Parked (with unpark condition) / Done (dated) |
| `manifest.json` | config | — | repos, kits, servers, vault, people, parent, extra shelves |
| `log/` | append | one file per session or piece of work, `YYYY-MM-DD-<slug>.md` |
| `runbooks/` | living | repeatable procedures; scripts sit beside their prose |
| `memory/` | append | agent lessons; Claude Code's memory directory symlinks here |

## Optional shelves, from the closed catalogue

| Shelf | Cadence | Holds |
|---|---|---|
| `events/` | immutable dated folder | one executed operation: data, mapping, scripts, RUNBOOK, EXECUTION-LOG, results, rollback |
| `incidents/` | one file per outage | window, what broke, fixes, facts worth keeping, alert to add |
| `bugs/` | intake, dated | client bugsheets, dogfood logs, one file per batch or bug |
| `plans/` | living until executed | forward plans, cutover runbooks in draft, handoffs; promoted to `events/` or `log/` when run |
| `releases/` | one per version | `vX.md` internal, `vX.user.md` client-facing |
| `comms/` | dated | outbound drafts and finals, inbound emails as PDF |
| `specs/` | living | PRD extraction, gap analysis, design specs, architecture |
| `evidence/` | immutable | QA packs, verification screenshots, audit reports |
| `reference/` | immutable, inherited | the client's own diagrams, KT documents, inventories, decks received |
| `archive/` | immutable | signed originals, superseded versions |
| `tenants/<slug>/` | nested room | a full room, same schema, for a product's customers |
| `_scratch/` | disposable | gitignored; may be deleted at any time |
| `ACCESS.md` | pointer | vault project and key names, which identity may read what; values never |
| `README.md` | living | human-facing description, optional |

Always tolerated and never a shelf: `.git .gitignore .gitkeep .DS_Store .claude .codex .serena _index.json .cwi`.

## The stretch valve

Anything else at the room's top level fails `cwi room check` unless it is declared in `manifest.json`:

```json
"shelves_extra": [{"name": "templates", "why": "document factory templates; studio-only shelf"}]
```

A room may grow, never silently. When several rooms declare the same extra, promote it into this catalogue with a kit release.

## Frontmatter

`_meta.md`, `STATE.md`, `MEMORY.md`, `AGENDA.md` begin with:

```
---
kind: meta | state | memory | agenda
audience: studio | client | public
cadence: living | snapshot | ledger | append
updated: YYYY-MM-DD
---
```

`kind` must match the file. `audience` must match the manifest. `updated` is bumped on every edit of that file.

## Audience rule

A workspace under `clients/` declares `audience: client`: the client may read the whole room, so nothing studio-private goes in it. Studio-private material about a client lives in `operation-room/clients/<slug>/`. Every other workspace declares `studio`.

## Two modes

- **repo** — the room is its own git repository at `<workspace>/ops/`, named `<name>-ops` on GitHub. For clients and products that hold several code repositories.
- **embedded** — the room is the top level of an existing repository. For the studio room and single-repo products.

## Conventions kept from the rooms that existed before this schema

Dated filenames `YYYY-MM-DD-<slug>`. `*.local.md` is gitignored (machine-only). `*.user.md` is client-facing. Registers and ledgers are append-only. A tenant is a room inside a room.
