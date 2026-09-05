"""cwi registry: the studio's map of every workspace, rebuilt from manifests and STATE files."""
import datetime as _dt
import json
from pathlib import Path

from . import frontmatter, gitx, manifest, schema
from .sync import iter_workspaces


def state_line(room):
    p = Path(room) / "STATE.md"
    if not p.is_file():
        return ""
    _, body = frontmatter.parse(p.read_text(encoding="utf-8", errors="replace"))
    for line in body.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return s[:160]
    return ""


def entries(root):
    out = []
    for ws, room in iter_workspaces(root):
        rel = str(ws.relative_to(root))
        if room is None:
            out.append({"name": ws.name, "path": rel, "room_mode": None, "note": "no room yet"})
            continue
        m = manifest.load(room)
        out.append({
            "name": m["name"], "kind": m["kind"], "owner": m["owner"], "audience": m["audience"],
            "path": rel, "room_mode": m["room"]["mode"],
            "room_remote": m["room"].get("remote") or gitx.remote_url(room),
            "repos": m["repos"], "kits": m["kits"], "servers": m["servers"], "vault": m["vault"],
            "parent": m.get("parent"), "state": state_line(room),
            "updated": gitx.last_commit_date(room),
        })
    return out


def write(root):
    root = Path(root).resolve()
    ents = entries(root)
    hq = root / schema.STUDIO_ROOM
    data = {"generated": _dt.datetime.now().isoformat(timespec="seconds"), "root": str(root), "workspaces": ents}
    (hq / "registry.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        f"{schema.GENERATED_MARK.replace('ws meta', 'registry')} {data['generated']} — run `cwi registry` to refresh -->",
        "# Registry — every workspace the studio runs",
        "",
        "One row per workspace. `state` is the first line of the room's STATE.md; `updated` is the room's last commit.",
        "Machine form: `registry.json` beside this file. Rebuild from a fresh machine with `cwi bootstrap`.",
        "",
        "| Name | Kind | Owner | Path | Room | Repos | Servers | Vault | State | Updated |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for e in ents:
        if not e.get("room_mode"):
            lines.append(f"| {e['name']} | — | — | `{e['path']}` | **none yet** | | | | | |")
            continue
        repos = ", ".join(r["path"] for r in e["repos"]) or "—"
        servers = ", ".join(f"{s['name']}@{s['host']}" for s in e["servers"]) or "—"
        vault = f"{e['vault'].get('provider')}:{e['vault'].get('project')}" if e.get("vault") else "—"
        lines.append(f"| {e['name']} | {e['kind']} | {e['owner']} | `{e['path']}` | {e['room_mode']} | {repos} | {servers} | {vault} | {e['state']} | {e['updated']} |")
    (hq / "REGISTRY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hq / "REGISTRY.md", hq / "registry.json", ents
