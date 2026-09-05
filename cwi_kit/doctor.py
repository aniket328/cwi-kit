"""cwi doctor: the no-loose-files rule, repository hygiene, room conformance."""
import os
from pathlib import Path

from . import gitx, schema
from .room import check as room_check
from .sync import iter_workspaces

STALE_HOURS = 24
ERROR_CODES = {"LOOSE", "NOREMOTE", "STALE", "UNPUSHED", "ROOM"}


class Finding:
    __slots__ = ("code", "path", "message")

    def __init__(self, code, path, message=""):
        self.code, self.path, self.message = code, str(path), message

    @property
    def is_error(self):
        return self.code in ERROR_CODES

    def as_dict(self):
        return {"code": self.code, "path": self.path, "message": self.message}

    def __str__(self):
        return f"{self.code:9s} {self.path}  {self.message}".rstrip()


def repo_findings(repo):
    out = []
    repo = Path(repo)
    remote = gitx.remote_url(repo)
    if not remote:
        out.append(Finding("NOREMOTE", repo, "no origin; add one or move to archive/"))
    dirty = gitx.dirty_paths(repo)
    if dirty:
        age = gitx.hours_since(gitx.newest_mtime(repo, dirty))
        if age > STALE_HOURS:
            out.append(Finding("STALE", repo, f"{len(dirty)} uncommitted path(s), newest {age / 24:.1f} d old"))
    if remote and gitx.has_commits(repo):
        head_age = gitx.hours_since(gitx.head_commit_time(repo))
        if gitx.has_upstream(repo):
            ahead = gitx.ahead_count(repo) or 0
            if ahead and head_age > STALE_HOURS:
                out.append(Finding("UNPUSHED", repo, f"{ahead} commit(s) ahead of upstream, newest {head_age / 24:.1f} d old"))
        elif head_age > STALE_HOURS:
            out.append(Finding("UNPUSHED", repo, f"branch has no upstream; push -u origin {gitx.current_branch(repo)}"))
    return out


def loose_in_workspace(ws):
    """Files under ws that live outside every repository and outside _scratch."""
    ws = Path(ws)
    if gitx.is_repo(ws):
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(ws):
        d = Path(dirpath)
        if d != ws and (gitx.is_repo(d)):
            dirnames[:] = []
            continue
        dirnames[:] = [n for n in dirnames if n not in schema.SKIP_DIRS and n not in schema.WS_ALLOWED]
        for f in filenames:
            if d == ws and f in schema.WS_ALLOWED:
                continue
            if f == ".DS_Store":
                continue
            out.append(Finding("LOOSE", d / f, "not inside any repository"))
    return out


def loose_at_root(root):
    root = Path(root)
    out = []
    for entry in root.iterdir():
        n = entry.name
        if n in schema.ROOT_ALLOWED or n in schema.GROUPS or n in (schema.STUDIO_ROOM, schema.ARCHIVE):
            continue
        out.append(Finding("LOOSE", entry, "not a group folder; move it into products/ kits/ rsi/ clients/ exp/ or archive/"))
    for g in schema.GROUPS:
        gd = root / g
        if not gd.is_dir():
            continue
        for entry in gd.iterdir():
            if entry.is_file() and entry.name not in schema.GROUP_ALLOWED:
                out.append(Finding("LOOSE", entry, "files do not live directly in a group folder"))
    return out


def run(root=None, path=None):
    """Return (findings, warnings). With path, check that workspace only."""
    findings, warnings = [], []
    if path:
        targets = [(Path(path).resolve(), None)]
        from .room import find_room
        r = find_room(path)
        targets = [(r.parent if r and r.name == "ops" else (r or Path(path).resolve()), r)]
    else:
        root = Path(root).resolve()
        findings += loose_at_root(root)
        targets = list(iter_workspaces(root))
        if (root / schema.ARCHIVE).is_dir():
            warnings.append(Finding("ARCHIVE", root / schema.ARCHIVE, "skipped; no off-machine mirror yet"))
    for ws, room in targets:
        if room is None:
            warnings.append(Finding("NOROOM", ws, "no room yet; cwi ws init when this workspace is converted"))
        else:
            errs = room_check(room)
            if errs:
                findings.append(Finding("ROOM", room, "; ".join(errs[:3]) + (" …" if len(errs) > 3 else "")))
        findings += loose_in_workspace(ws)
        for repo in gitx.find_repos(ws):
            findings += repo_findings(repo)
    return findings, warnings


def report(findings, warnings):
    lines = []
    for f in findings:
        lines.append(str(f))
    for w in warnings:
        lines.append(str(w))
    errors = [f for f in findings if f.is_error]
    lines.append(f"-- {len(errors)} error(s), {len(warnings)} warning(s)")
    return lines, not errors
