"""cwi sync: keep rooms committed and in sync; pull code repos; pin kits. Never commits code."""
import datetime as _dt
import socket
from pathlib import Path

from . import gitx, manifest, schema
from .room import find_room, is_room, room_paths, workspace


def hostname():
    return socket.gethostname().split(".")[0]


def commit_message():
    return f"ops: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} {hostname()}"


def sync_room(room, m, push=True):
    """Stage only the room's own paths, commit if dirty, pull --rebase, push. Returns (lines, ok)."""
    lines, ok = [], True
    room = Path(room)
    if not gitx.is_repo(room):
        return [f"room: {room} is not a git repository"], False
    paths = room_paths(room, m)
    gitx.run(["add", "-A", "--", *paths], room)
    staged = gitx.run(["diff", "--cached", "--quiet"], room).returncode != 0
    if staged:
        n = len(gitx.run(["diff", "--cached", "--name-only"], room).stdout.splitlines())
        r = gitx.run(["commit", "-q", "-m", commit_message()], room)
        if r.returncode != 0:
            lines.append(f"room: commit failed: {r.stderr.strip()}")
            ok = False
        else:
            lines.append(f"room: committed {n} file(s)")
    else:
        lines.append("room: clean")
    remote = gitx.remote_url(room)
    if not remote:
        lines.append("room: no remote, not pushed")
        return lines, ok
    if not gitx.has_commits(room):
        return lines, ok
    branch = gitx.current_branch(room)
    if gitx.has_upstream(room):
        r = gitx.run(["pull", "-q", "--rebase", "--autostash"], room)
        if r.returncode != 0:
            lines.append(f"room: pull --rebase failed, resolve by hand: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}")
            return lines, False
    if push:
        r = gitx.run(["push", "-q", "-u", "origin", branch], room)
        if r.returncode != 0:
            lines.append(f"room: push failed: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}")
            ok = False
        else:
            lines.append("room: pushed")
    return lines, ok


def sync_repos(ws, m):
    lines, ok = [], True
    for r in m["repos"]:
        p = Path(ws) / r["path"]
        tag = f"repo {r['path']}"
        if not p.exists():
            lines.append(f"{tag}: missing, run cwi bootstrap")
            continue
        if not gitx.is_repo(p):
            lines.append(f"{tag}: not a git repository")
            ok = False
            continue
        if gitx.status_porcelain(p):
            lines.append(f"{tag}: dirty, left alone")
            continue
        if not gitx.remote_url(p):
            lines.append(f"{tag}: no remote")
            continue
        if not gitx.has_upstream(p):
            lines.append(f"{tag}: no upstream, not pulled")
            continue
        res = gitx.run(["pull", "-q", "--ff-only"], p)
        lines.append(f"{tag}: pulled" if res.returncode == 0 else f"{tag}: pull --ff-only failed (diverged?)")
    return lines, ok


def sync_kits(ws, m):
    lines, ok = [], True
    for k in m["kits"]:
        p = Path(ws) / k["path"]
        tag = f"kit {k['name']}@{k['ref']}"
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            res = gitx.clone(k["remote"], p, ref=k["ref"], depth=1)
            if res.returncode != 0:
                lines.append(f"{tag}: clone failed: {res.stderr.strip().splitlines()[-1] if res.stderr.strip() else ''}")
                ok = False
            else:
                lines.append(f"{tag}: cloned")
            continue
        if gitx.status_porcelain(p):
            lines.append(f"{tag}: dirty, left alone")
            continue
        gitx.run(["fetch", "-q", "--tags"], p)
        res = gitx.run(["checkout", "-q", k["ref"]], p)
        lines.append(f"{tag}: at ref" if res.returncode == 0 else f"{tag}: ref not found")
    return lines, ok


def sync_ws(path=None, ops_only=False, push=True):
    room = find_room(path)
    if room is None:
        return [f"no room found from {Path(path or Path.cwd()).resolve()}"], False
    m = manifest.load(room)
    ws = workspace(room, m)
    lines = [f"== {m['name']} ({room})"]
    l, ok = sync_room(room, m, push=push)
    lines += l
    if not ops_only:
        l2, ok2 = sync_repos(ws, m)
        l3, ok3 = sync_kits(ws, m)
        lines += l2 + l3
        ok = ok and ok2 and ok3
    return lines, ok


def iter_workspaces(root):
    """(workspace, room|None) for the studio room and every folder inside a group."""
    root = Path(root)
    studio = root / schema.STUDIO_ROOM
    if studio.is_dir():
        yield studio, (studio if is_room(studio) else None)
    for g in schema.GROUPS:
        gd = root / g
        if not gd.is_dir():
            continue
        for ws in sorted(p for p in gd.iterdir() if p.is_dir() and not p.name.startswith(".")):
            room = ws / "ops" if is_room(ws / "ops") else (ws if is_room(ws) else None)
            yield ws, room


def sync_all(root, ops_only=False, push=True):
    lines, ok = [], True
    for ws, room in iter_workspaces(root):
        if room is None:
            lines.append(f"== {ws.name}: no room, skipped")
            continue
        l, o = sync_ws(room, ops_only=ops_only, push=push)
        lines += l
        ok = ok and o
    return lines, ok
