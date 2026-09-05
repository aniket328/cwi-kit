"""Thin git helpers. Every call is a subprocess; nothing here raises unless asked to."""
import os
import subprocess
import time
from pathlib import Path

from . import schema


class GitError(Exception):
    pass


def run(args, cwd, check=False):
    r = subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True)
    if check and r.returncode != 0:
        raise GitError(f"git {' '.join(args)} in {cwd}: {r.stderr.strip() or r.stdout.strip()}")
    return r


def is_repo(p):
    return (Path(p) / ".git").exists()


def toplevel(p):
    r = run(["rev-parse", "--show-toplevel"], p)
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def remote_url(p, name="origin"):
    r = run(["remote", "get-url", name], p)
    return r.stdout.strip() if r.returncode == 0 else None


def init(p, remote=None):
    run(["init", "-q"], p, check=True)
    if remote:
        run(["remote", "add", "origin", remote], p)


def status_porcelain(p, paths=None):
    args = ["status", "--porcelain", "--untracked-files=all"]
    if paths:
        args += ["--", *paths]
    r = run(args, p)
    return [line for line in r.stdout.splitlines() if line.strip()]


def dirty_paths(p, paths=None):
    """Relative paths of every modified/untracked entry (porcelain column 4+)."""
    out = []
    for line in status_porcelain(p, paths):
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append(path.strip('"'))
    return out


def has_commits(p):
    return run(["rev-parse", "--verify", "HEAD"], p).returncode == 0


def current_branch(p):
    r = run(["rev-parse", "--abbrev-ref", "HEAD"], p)
    return r.stdout.strip() if r.returncode == 0 else None


def has_upstream(p):
    return run(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], p).returncode == 0


def ahead_count(p):
    r = run(["rev-list", "--count", "@{u}..HEAD"], p)
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else None


def head_commit_time(p):
    r = run(["log", "-1", "--format=%ct"], p)
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else None


def last_commit_date(p):
    r = run(["log", "-1", "--format=%cs"], p)
    return r.stdout.strip() if r.returncode == 0 else ""


def newest_mtime(root, rel_paths):
    """Newest mtime among the given relative paths (files or dirs); 0 if none exist."""
    newest = 0
    for rel in rel_paths:
        p = Path(root) / rel
        try:
            if p.is_dir():
                for sub in p.rglob("*"):
                    if sub.is_file():
                        newest = max(newest, sub.stat().st_mtime)
            elif p.exists() or p.is_symlink():
                newest = max(newest, p.lstat().st_mtime)
        except OSError:
            continue
    return newest


def hours_since(ts):
    return (time.time() - ts) / 3600.0 if ts else 0.0


def find_repos(root, skip=schema.SKIP_DIRS):
    """Every git repository under root (including nested ones and worktrees), depth-first."""
    root = Path(root)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        if ".git" in dirnames or ".git" in filenames:
            found.append(d)
        dirnames[:] = [n for n in dirnames if n not in skip]
    return found


def clone(remote, dest, ref=None, depth=None):
    args = ["clone", "-q"]
    if ref:
        args += ["--branch", ref]
    if depth:
        args += ["--depth", str(depth)]
    args += [remote, str(dest)]
    return run(args, Path(dest).parent)
