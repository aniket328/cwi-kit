"""cwi bootstrap: rebuild the tree on a fresh machine from registry.json."""
import json
from pathlib import Path

from . import gitx, manifest, schema, ws as ws_mod


def load_registry(root, registry=None):
    p = Path(registry) if registry else Path(root) / schema.STUDIO_ROOM / "registry.json"
    if not p.is_file():
        raise FileNotFoundError(f"no registry at {p}; clone operation-room first or pass --registry")
    return json.loads(p.read_text(encoding="utf-8"))


def _clone(remote, dest, ref=None):
    dest = Path(dest)
    if dest.exists():
        return f"exists  {dest}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = gitx.clone(remote, dest, ref=ref)
    if r.returncode != 0:
        return f"FAILED  {dest}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'clone error'}"
    return f"cloned  {dest}"


def run(root, registry=None, only=None):
    root = Path(root).resolve()
    reg = load_registry(root, registry)
    lines, ok = [], True
    for e in reg["workspaces"]:
        if only and e["name"] != only:
            continue
        if not e.get("room_mode"):
            lines.append(f"skip    {e['path']}: no room in registry")
            continue
        ws = root / e["path"]
        room = ws / "ops" if e["room_mode"] == "repo" else ws
        if not gitx.is_repo(room):
            if not e.get("room_remote"):
                lines.append(f"FAILED  {room}: room has no remote in registry")
                ok = False
                continue
            line = _clone(e["room_remote"], room)
            lines.append(line)
            if line.startswith("FAILED"):
                ok = False
                continue
        m = manifest.load(room)
        for r in m["repos"]:
            if r.get("remote"):
                line = _clone(r["remote"], ws / r["path"])
                lines.append(line)
                ok = ok and not line.startswith("FAILED")
            else:
                lines.append(f"skip    {ws / r['path']}: no remote in manifest")
        for k in m["kits"]:
            line = _clone(k["remote"], ws / k["path"], ref=k["ref"])
            lines.append(line)
            ok = ok and not line.startswith("FAILED")
        ws_mod.meta(room)
        ws_mod.link(room)
        lines.append(f"ready   {ws}")
    return lines, ok
