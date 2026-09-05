"""Minimal `key: value` frontmatter. No YAML library: the schema only needs flat scalars."""
import re

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse(text):
    """Return (meta: dict, body: str). Missing or malformed frontmatter -> ({}, text)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    block = text[4:end]
    rest = text[end + 4:]
    if rest.startswith("\n"):
        rest = rest[1:]
    meta = {}
    for line in block.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, rest


def render(meta, body):
    lines = ["---"] + [f"{k}: {v}" for k, v in meta.items()] + ["---", ""]
    return "\n".join(lines) + body


def is_date(value):
    return bool(value and _DATE.match(value))
