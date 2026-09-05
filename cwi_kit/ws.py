"""Workspace operations: init a room, regenerate routers and hooks, link Claude memory."""
import datetime as _dt
import json
import re
import shutil
from pathlib import Path

from . import TEMPLATES, __version__, gitx, manifest, schema
from .room import workspace


class WsError(Exception):
    pass


HOOKS = (
    ("SessionStart", "cwi hook start", 15, None),
    ("Stop", "cwi hook stop", 60, "cwi: committing ops"),
    ("SessionEnd", "cwi hook end", 120, None),
)


def today():
    return _dt.date.today().isoformat()


def render(text, variables):
    for k, v in variables.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def slug(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(s)).strip("-").lower()
    return s or "root"


def enc(path):
    """Claude Code's project-directory encoding of an absolute path."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _vars(m, mode):
    return {"NAME": m["name"], "KIND": m["kind"], "OWNER": m["owner"], "AUDIENCE": m["audience"],
            "DATE": today(), "MODE": mode, "KIT_VERSION": __version__}


def init(path, name, kind, owner, mode="repo", remote=None):
    if kind not in schema.KINDS:
        raise WsError(f"kind must be one of {schema.KINDS}")
    if mode not in schema.ROOM_MODES:
        raise WsError(f"mode must be one of {schema.ROOM_MODES}")
    ws = Path(path).resolve()
    ws.mkdir(parents=True, exist_ok=True)
    room = ws / "ops" if mode == "repo" else ws
    room.mkdir(exist_ok=True)
    if mode == "repo" and not gitx.is_repo(room):
        gitx.init(room, remote)
    if mode == "embedded" and not gitx.is_repo(room):
        raise WsError(f"embedded mode needs an existing git repository at {room}")

    if manifest.path(room).is_file():
        m = manifest.load(room)
    else:
        m = manifest.new(name, kind, owner, mode, remote)
        manifest.save(room, m)
    v = _vars(m, mode)
    for tpl in ("_meta.md", "STATE.md", "MEMORY.md", "AGENDA.md"):
        dst = room / tpl
        if not dst.exists():
            dst.write_text(render((TEMPLATES / "room" / tpl).read_text(), v), encoding="utf-8")
    for d in schema.CORE_DIRS:
        (room / d).mkdir(exist_ok=True)
        if not any(p.name != ".DS_Store" for p in (room / d).iterdir()):
            (room / d / ".gitkeep").touch()
    _ensure_gitignore(room)
    meta(room)
    link(room)
    return room


def _ensure_gitignore(room):
    wanted = (TEMPLATES / "room" / "gitignore").read_text().splitlines()
    gi = room / ".gitignore"
    existing = gi.read_text().splitlines() if gi.exists() else []
    missing = [w for w in wanted if w and w not in existing]
    if not gi.exists():
        gi.write_text("\n".join(wanted) + "\n")
    elif missing:
        gi.write_text("\n".join(existing + ["", "# cwi-kit room"] + missing) + "\n")


def meta(room):
    room = Path(room)
    m = manifest.load(room)
    mode = m["room"]["mode"]
    ws = workspace(room, m)
    v = _vars(m, mode)
    if mode == "repo":
        (ws / "_meta.md").write_text(render_ws_meta(m, ws), encoding="utf-8")
        for shim in ("CLAUDE.md", "AGENTS.md"):
            (ws / shim).write_text(render((TEMPLATES / "ws" / shim).read_text(), v), encoding="utf-8")
    else:
        for shim in ("CLAUDE.md", "AGENTS.md"):
            dst = ws / shim
            if not dst.exists():
                text = render((TEMPLATES / "ws" / shim).read_text(), v).replace("ops/", "")
                dst.write_text(text, encoding="utf-8")
    settings(ws)
    return ws


def render_ws_meta(m, ws):
    lines = [
        f"{schema.GENERATED_MARK} {today()} from ops/manifest.json — edit the manifest, not this file -->",
        f"# {m['name']} — workspace router",
        "",
        f"{m['kind']} workspace, owner **{m['owner']}**, audience **{m['audience']}**. "
        "Read `ops/STATE.md` next, then `ops/AGENDA.md`.",
        "",
        "| Folder | What | Notes |",
        "|---|---|---|",
        "| `ops/` | the room: state, memory, agenda, log, runbooks | committed by the Stop hook, never left dirty |",
    ]
    for r in m["repos"]:
        lines.append(f"| `{r['path']}/` | {r.get('role', 'code')} | `{r.get('remote', 'no remote')}` · never auto-committed |")
    for k in m["kits"]:
        lines.append(f"| `{k['path']}/` | kit {k['name']} @ `{k['ref']}` | pinned, re-pin via manifest |")
    lines.append("| `_scratch/` | disposable | gitignored, may be deleted at any time |")
    if m["servers"]:
        lines += ["", "## Servers", "", "| Name | Host | Owner | Role | Access |", "|---|---|---|---|---|"]
        for s in m["servers"]:
            lines.append(f"| {s['name']} | `{s['host']}` | {s.get('owner', '')} | {s.get('role', '')} | `{s.get('access', '')}` |")
    vault = m.get("vault") or {}
    lines += [
        "",
        "## Secrets",
        "",
        f"Vault: **{vault.get('provider', '?')}** project `{vault.get('project', '?')}`, configs {', '.join(vault.get('configs', []))}. "
        "Secrets are injected at run time; none is ever written into this workspace. `ops/ACCESS.md`, if present, lists key names only.",
    ]
    if m.get("parent"):
        lines += ["", f"Studio-side file for this workspace: `{m['parent']}` (private, not on this machine unless it is the studio's)."]
    if m.get("people"):
        lines += ["", "## People", ""] + [f"- {p.get('name', '')} — {p.get('role', '')}" for p in m["people"]]
    return "\n".join(lines) + "\n"


CODEX_CONFIG_LINES = ("[features]", "hooks = true")


def _merge_hooks(path):
    """Add the three cwi hooks to a Claude/Codex hooks JSON file, keeping every other key."""
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    hooks = data.setdefault("hooks", {})
    changed = False
    for event, cmd, timeout, msg in HOOKS:
        entries = hooks.setdefault(event, [])
        present = any(h.get("command") == cmd for e in entries for h in e.get("hooks", []))
        if not present:
            hook = {"type": "command", "command": cmd, "timeout": timeout}
            if msg:
                hook["statusMessage"] = msg
            entries.append({"hooks": [hook]})
            changed = True
    if changed or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def settings(ws):
    """Write the hooks for Claude Code (.claude/settings.json) and Codex (.codex/hooks.json +
    features.hooks in .codex/config.toml). Codex project hooks still need a one-time /hooks trust."""
    ws = Path(ws)
    claude = ws / ".claude" / "settings.json"
    codex = ws / ".codex" / "hooks.json"
    _merge_hooks(claude)
    _merge_hooks(codex)
    cfg = ws / ".codex" / "config.toml"
    text = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
    if "hooks = true" not in text and "codex_hooks = true" not in text:
        text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + "\n".join(CODEX_CONFIG_LINES) + "\n"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(text, encoding="utf-8")
    return claude


def link_targets(room, m=None):
    room = Path(room)
    m = m or manifest.load(room)
    ws = workspace(room, m)
    targets = [(ws, "root")]
    for r in m["repos"]:
        targets.append((ws / r["path"], slug(Path(r["path"]).name)))
    for extra in m.get("memory_paths", []):
        p = Path(extra).expanduser()
        targets.append((p, slug(p.name)))
    return targets


def link(room, projects_dir=None):
    """Symlink each Claude memory dir into <room>/memory/<slug>/. Existing files move in first."""
    room = Path(room)
    m = manifest.load(room)
    projects_dir = Path(projects_dir) if projects_dir else Path.home() / ".claude" / "projects"
    done = []
    for path, name in link_targets(room, m):
        mem = projects_dir / enc(path.resolve() if path.exists() else path) / "memory"
        dest = room / "memory" / name
        dest.mkdir(parents=True, exist_ok=True)
        if mem.is_symlink():
            if mem.resolve() == dest.resolve():
                done.append((mem, dest, "ok"))
                continue
            mem.unlink()
        elif mem.is_dir():
            for f in list(mem.iterdir()):
                target = dest / f.name
                if target.exists():
                    target = dest / f"{f.stem}.imported-{today()}{f.suffix}"
                shutil.move(str(f), str(target))
            mem.rmdir()
        mem.parent.mkdir(parents=True, exist_ok=True)
        mem.symlink_to(dest)
        done.append((mem, dest, "linked"))
    return done
