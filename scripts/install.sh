#!/usr/bin/env bash
# Install the cwi CLI: symlink bin/cwi into ~/.local/bin and verify.
# Usage: scripts/install.sh          (from anywhere; resolves the kit from its own path)
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${CWI_BIN_DIR:-$HOME/.local/bin}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found; cwi-kit needs Python 3.10 or newer" >&2; exit 1
fi
python3 - <<'EOF' || { echo "Python 3.10 or newer required" >&2; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)
EOF
if ! command -v git >/dev/null 2>&1; then
  echo "git not found" >&2; exit 1
fi

mkdir -p "$BIN"
chmod +x "$KIT/bin/cwi"
ln -sfn "$KIT/bin/cwi" "$BIN/cwi"
echo "linked $BIN/cwi -> $KIT/bin/cwi"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "note: $BIN is not on PATH; add: export PATH=\"$BIN:\$PATH\"" ;;
esac

"$BIN/cwi" --version
