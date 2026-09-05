"""manifest.json: the one config file a room carries. Load, validate, write, create."""
import json
from pathlib import Path

from . import schema


class ManifestError(Exception):
    pass


REQUIRED = ("schema", "name", "kind", "owner", "audience", "room", "repos", "kits",
            "servers", "vault", "parent", "people", "memory_paths", "shelves_extra")


def new(name, kind, owner, mode="repo", remote=None, audience=None):
    if audience is None:
        audience = "client" if kind == "client" else "studio"
    return {
        "schema": schema.SCHEMA_VERSION,
        "name": name,
        "kind": kind,
        "owner": owner,
        "audience": audience,
        "room": {"mode": mode, "remote": remote},
        "repos": [],
        "kits": [],
        "servers": [],
        "vault": {"provider": "doppler", "project": name, "configs": ["dev", "prd"]},
        "parent": None,
        "people": [],
        "memory_paths": [],
        "shelves_extra": [],
    }


def path(room):
    return Path(room) / "manifest.json"


def load(room):
    p = path(room)
    if not p.is_file():
        raise ManifestError(f"no manifest.json in {room}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ManifestError(f"{p}: invalid JSON: {e}") from e


def save(room, m):
    path(room).write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate(m):
    errors = []
    if not isinstance(m, dict):
        return ["manifest is not an object"]
    for key in REQUIRED:
        if key not in m:
            errors.append(f"missing key {key!r}")
    if errors:
        return errors
    if m["schema"] != schema.SCHEMA_VERSION:
        errors.append(f"schema must be {schema.SCHEMA_VERSION}, got {m['schema']!r}")
    if m["kind"] not in schema.KINDS:
        errors.append(f"kind must be one of {schema.KINDS}, got {m['kind']!r}")
    if m["audience"] not in schema.AUDIENCES:
        errors.append(f"audience must be one of {schema.AUDIENCES}, got {m['audience']!r}")
    for key in ("name", "owner"):
        if not isinstance(m[key], str) or not m[key].strip():
            errors.append(f"{key} must be a non-empty string")
    room = m["room"]
    if not isinstance(room, dict) or room.get("mode") not in schema.ROOM_MODES:
        errors.append(f"room.mode must be one of {schema.ROOM_MODES}")
    for key in ("repos", "kits", "servers", "people", "memory_paths", "shelves_extra"):
        if not isinstance(m[key], list):
            errors.append(f"{key} must be a list")
    if isinstance(m["repos"], list):
        for i, r in enumerate(m["repos"]):
            if not isinstance(r, dict) or not r.get("path"):
                errors.append(f"repos[{i}] needs a path")
    if isinstance(m["kits"], list):
        for i, k in enumerate(m["kits"]):
            if not isinstance(k, dict) or not all(k.get(f) for f in ("name", "remote", "ref", "path")):
                errors.append(f"kits[{i}] needs name, remote, ref, path")
    if isinstance(m["servers"], list):
        for i, s in enumerate(m["servers"]):
            if not isinstance(s, dict) or not s.get("name") or not s.get("host"):
                errors.append(f"servers[{i}] needs name and host")
            elif any(len(str(v)) > 200 for v in s.values()):
                errors.append(f"servers[{i}]: a value looks like a pasted secret; servers hold pointers only")
    if isinstance(m["shelves_extra"], list):
        for i, e in enumerate(m["shelves_extra"]):
            if not isinstance(e, dict) or not e.get("name") or not e.get("why"):
                errors.append(f"shelves_extra[{i}] needs name and why")
    vault = m["vault"]
    if not isinstance(vault, dict) or not vault.get("provider"):
        errors.append("vault needs a provider")
    return errors
