#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PREFIX=${PREFIX:-$HOME/.local}
DEST="$PREFIX/bin"
# Refuse to replace an existing installation, including dangling symlinks.
for name in prism-model-manager prism-lora-ab-score.py; do
    if [[ -e "$DEST/$name" || -L "$DEST/$name" ]]; then
        echo "Already exists: $DEST/$name. Choose a different PREFIX." >&2
        exit 1
    fi
done
mkdir -p "$DEST"
install -m 755 "$ROOT/bin/prism-model-manager" "$DEST/prism-model-manager"
install -m 755 "$ROOT/bin/prism-lora-ab-score.py" "$DEST/prism-lora-ab-score.py"
echo "Installed in $DEST. Add this directory to PATH."
