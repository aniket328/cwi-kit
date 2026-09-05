"""cwi-kit: the room schema, workspace routers, sync, doctor, registry and bootstrap for CWI Studio."""
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = KIT_ROOT / "templates"
__version__ = (KIT_ROOT / "VERSION").read_text().strip()
