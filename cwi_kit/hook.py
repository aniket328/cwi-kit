"""What the Claude Code hooks call. Every entry point exits 0; a hook must never fail a turn."""
import datetime as _dt
from pathlib import Path

from . import frontmatter, manifest
from .room import find_room, workspace
from .sync import sync_ws


def _log(ws, event, lines):
    try:
        d = Path(ws) / ".cwi"
        d.mkdir(exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with (d / "sync.log").open("a", encoding="utf-8") as f:
            f.write(f"{stamp} {event}: " + " | ".join(lines) + "\n")
    except OSError:
        pass


def _sync(event, push):
    room = find_room()
    if room is None:
        return 0
    try:
        m = manifest.load(room)
        ws = workspace(room, m)
        lines, _ = sync_ws(room, ops_only=True, push=push)
        _log(ws, event, lines)
    except Exception as e:  # noqa: BLE001 — a hook never raises
        try:
            _log(Path.cwd(), event, [f"error: {e}"])
        except Exception:
            pass
    return 0


def stop():
    return _sync("stop", push=False)


def end():
    return _sync("end", push=True)


def start(out=print):
    room = find_room()
    if room is None:
        return 0
    try:
        m = manifest.load(room)
        out(f"[cwi] room {m['name']} ({m['kind']}, audience {m['audience']}) at {room}")
        state = room / "STATE.md"
        if state.is_file():
            _, body = frontmatter.parse(state.read_text(encoding="utf-8", errors="replace"))
            out("[cwi] STATE.md:")
            for line in body.splitlines()[:25]:
                out("  " + line)
        agenda = room / "AGENDA.md"
        if agenda.is_file():
            _, body = frontmatter.parse(agenda.read_text(encoding="utf-8", errors="replace"))
            take, buf = False, []
            for line in body.splitlines():
                if line.startswith("## "):
                    take = line.strip().lower() == "## next"
                    continue
                if take and line.strip():
                    buf.append(line)
            if buf:
                out("[cwi] AGENDA.md → Next:")
                for line in buf[:12]:
                    out("  " + line)
    except Exception as e:  # noqa: BLE001
        out(f"[cwi] start hook: {e}")
    return 0
