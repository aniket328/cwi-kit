"""cwi — one executable, subcommands for the room, workspace, sync, doctor, registry, bootstrap, hooks."""
import argparse
import json
import sys
from pathlib import Path

from . import __version__, bootstrap, doctor, hook, registry, room, schema, sync, ws


def _root_of(path=None):
    """The CWI tree root: the nearest ancestor holding operation-room/ or a group folder."""
    p = Path(path or Path.cwd()).resolve()
    for d in (p, *p.parents):
        if (d / schema.STUDIO_ROOM).is_dir() or any((d / g).is_dir() for g in schema.GROUPS):
            if (d / "_meta.md").is_file() or (d / schema.STUDIO_ROOM).is_dir():
                return d
    return None


def build_parser():
    p = argparse.ArgumentParser(prog="cwi", description="CWI Studio workspace tooling (cwi-kit)")
    p.add_argument("--version", action="version", version=f"cwi-kit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pw = sub.add_parser("ws", help="workspace: init, meta, link")
    wsub = pw.add_subparsers(dest="wcmd", required=True)
    pi = wsub.add_parser("init", help="create a room in a workspace (idempotent)")
    pi.add_argument("path")
    pi.add_argument("--name", required=True)
    pi.add_argument("--kind", required=True, choices=schema.KINDS)
    pi.add_argument("--owner", required=True)
    pi.add_argument("--mode", default="repo", choices=schema.ROOM_MODES)
    pi.add_argument("--remote")
    pm = wsub.add_parser("meta", help="regenerate _meta.md, CLAUDE.md, AGENTS.md, .claude/settings.json")
    pm.add_argument("path", nargs="?")
    pl = wsub.add_parser("link", help="symlink Claude memory dirs into the room")
    pl.add_argument("path", nargs="?")

    pr = sub.add_parser("room", help="room: check")
    rsub = pr.add_subparsers(dest="rcmd", required=True)
    pc = rsub.add_parser("check", help="schema conformance; exit 1 on violations")
    pc.add_argument("path", nargs="?")
    pc.add_argument("--json", action="store_true")

    ps = sub.add_parser("sync", help="commit + pull + push the room; pull clean code repos; pin kits")
    ps.add_argument("path", nargs="?")
    ps.add_argument("--all", action="store_true", help="every workspace under the tree root")
    ps.add_argument("--ops-only", action="store_true")
    ps.add_argument("--no-push", action="store_true")

    pd = sub.add_parser("doctor", help="no-loose-files rule, repo hygiene, room conformance")
    pd.add_argument("path", nargs="?")
    pd.add_argument("--all", action="store_true")
    pd.add_argument("--json", action="store_true")

    pg = sub.add_parser("registry", help="rebuild operation-room/REGISTRY.md and registry.json")
    pg.add_argument("--root")

    pb = sub.add_parser("bootstrap", help="rebuild the tree from registry.json on a fresh machine")
    pb.add_argument("--root")
    pb.add_argument("--registry")
    pb.add_argument("--only")

    ph = sub.add_parser("hook", help="entry points for Claude Code hooks")
    ph.add_argument("event", choices=("start", "stop", "end"))
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "ws":
        if args.wcmd == "init":
            try:
                r = ws.init(args.path, args.name, args.kind, args.owner, args.mode, args.remote)
            except ws.WsError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            print(f"room ready at {r}")
            return 0
        r = room.find_room(args.path)
        if r is None:
            print("error: no room found", file=sys.stderr)
            return 1
        if args.wcmd == "meta":
            print(f"regenerated workspace files in {ws.meta(r)}")
        else:
            for mem, dest, state in ws.link(r):
                print(f"{state:7s} {mem} -> {dest}")
        return 0

    if args.cmd == "room":
        r = room.find_room(args.path)
        if r is None:
            print("error: no room found", file=sys.stderr)
            return 1
        errs = room.check(r)
        if args.json:
            print(json.dumps({"room": str(r), "errors": errs}, indent=2))
        else:
            print(f"room {r}")
            for e in errs:
                print(f"  ✗ {e}")
            if not errs:
                print("  ✓ conforms to room schema v1")
        return 1 if errs else 0

    if args.cmd == "sync":
        if args.all:
            root = _root_of(args.path)
            if root is None:
                print("error: not inside a CWI tree", file=sys.stderr)
                return 1
            lines, ok = sync.sync_all(root, ops_only=args.ops_only, push=not args.no_push)
        else:
            lines, ok = sync.sync_ws(args.path, ops_only=args.ops_only, push=not args.no_push)
        print("\n".join(lines))
        return 0 if ok else 1

    if args.cmd == "doctor":
        if args.all or not args.path:
            root = _root_of(args.path)
            if root is None:
                print("error: not inside a CWI tree; pass a workspace path", file=sys.stderr)
                return 1
            findings, warnings = doctor.run(root=root)
        else:
            findings, warnings = doctor.run(path=args.path)
        if args.json:
            print(json.dumps({"findings": [f.as_dict() for f in findings],
                              "warnings": [w.as_dict() for w in warnings]}, indent=2))
            return 0 if not any(f.is_error for f in findings) else 1
        lines, ok = doctor.report(findings, warnings)
        print("\n".join(lines))
        return 0 if ok else 1

    if args.cmd == "registry":
        root = Path(args.root).resolve() if args.root else _root_of()
        if root is None:
            print("error: not inside a CWI tree", file=sys.stderr)
            return 1
        md, js, ents = registry.write(root)
        print(f"wrote {md} and {js}: {len(ents)} workspace(s)")
        return 0

    if args.cmd == "bootstrap":
        root = Path(args.root).resolve() if args.root else _root_of()
        if root is None:
            print("error: pass --root", file=sys.stderr)
            return 1
        try:
            lines, ok = bootstrap.run(root, registry=args.registry, only=args.only)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print("\n".join(lines))
        return 0 if ok else 1

    if args.cmd == "hook":
        return {"start": hook.start, "stop": hook.stop, "end": hook.end}[args.event]()
    return 2
