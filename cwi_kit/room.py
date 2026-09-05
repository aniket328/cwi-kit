"""Find a room from any path, and check it against the schema."""
from pathlib import Path

from . import frontmatter, manifest, schema


def is_room(d):
    d = Path(d)
    return (d / "manifest.json").is_file() and (d / "_meta.md").is_file()


def find_room(start=None):
    """Walk up from start (default cwd). A directory is a room if it has manifest.json and
    _meta.md; a workspace is recognised by an ops/ child that is a room."""
    p = Path(start or Path.cwd()).resolve()
    for d in (p, *p.parents):
        if is_room(d):
            return d
        if is_room(d / "ops"):
            return d / "ops"
    # the tree root itself is not a room; a session started there belongs to the studio room
    if is_room(p / schema.STUDIO_ROOM):
        return p / schema.STUDIO_ROOM
    return None


def workspace(room, m=None):
    m = m or manifest.load(room)
    room = Path(room)
    return room.parent if m["room"]["mode"] == "repo" else room


def extras(m):
    return {e["name"] for e in m.get("shelves_extra", []) if isinstance(e, dict) and e.get("name")}


def room_paths(room, m):
    """Top-level entries that belong to the room: core, optional shelves present, declared extras.
    Used by sync so an embedded room never stages an unrelated dirty file."""
    room = Path(room)
    names = set(schema.CORE_FILES) | set(schema.CORE_DIRS) | set(schema.OPTIONAL_DIRS) \
        | set(schema.OPTIONAL_FILES) | extras(m) | {".gitignore"}
    return sorted(n for n in names if (room / n).exists())


def check(room):
    room = Path(room)
    errors = []
    for f in schema.CORE_FILES:
        if not (room / f).is_file():
            errors.append(f"missing core file {f}")
    for d in schema.CORE_DIRS:
        if not (room / d).is_dir():
            errors.append(f"missing core dir {d}/")
    m = None
    try:
        m = manifest.load(room)
        errors += [f"manifest: {e}" for e in manifest.validate(m)]
    except manifest.ManifestError as e:
        errors.append(str(e))

    allowed = set(schema.CORE_FILES) | set(schema.CORE_DIRS) | set(schema.OPTIONAL_DIRS) \
        | set(schema.OPTIONAL_FILES) | set(schema.TOLERATED) | (extras(m) if m else set())
    for entry in sorted(room.iterdir(), key=lambda p: p.name):
        if entry.name not in allowed:
            errors.append(f"undeclared shelf {entry.name!r}: declare it in manifest shelves_extra with a why, or move it")

    for f, kind in schema.FRONTMATTER_KIND.items():
        p = room / f
        if not p.is_file():
            continue
        meta, _ = frontmatter.parse(p.read_text(encoding="utf-8", errors="replace"))
        if meta.get("kind") != kind:
            errors.append(f"{f}: frontmatter kind must be {kind!r}, got {meta.get('kind')!r}")
        if meta.get("audience") not in schema.AUDIENCES:
            errors.append(f"{f}: frontmatter audience must be one of {schema.AUDIENCES}")
        if meta.get("cadence") not in schema.CADENCES:
            errors.append(f"{f}: frontmatter cadence must be one of {schema.CADENCES}")
        if not frontmatter.is_date(meta.get("updated")):
            errors.append(f"{f}: frontmatter updated must be YYYY-MM-DD")
        if m and meta.get("audience") and meta.get("audience") != m.get("audience"):
            errors.append(f"{f}: audience {meta.get('audience')!r} disagrees with manifest {m.get('audience')!r}")

    if m and isinstance(m.get("room"), dict) and m["room"].get("mode") in schema.ROOM_MODES:
        ws = workspace(room, m)
        under_clients = ws.parent.name == "clients"
        if under_clients and m.get("audience") != "client":
            errors.append("workspace sits under clients/ so audience must be 'client'")
        if not under_clients and m.get("audience") == "client":
            errors.append("audience 'client' is only for workspaces under clients/")
    return errors
