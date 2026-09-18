#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PREFIX=${PREFIX:-$HOME/.local}
# Only remove files identical to this checkout; leave replacements and user data intact.
for name in prism-model-manager prism-lora-ab-score.py prism-gguf-info.py; do
    target="$PREFIX/bin/$name"
    if [[ -f "$target" && ! -L "$target" ]] && cmp -s "$ROOT/bin/$name" "$target"; then
        rm -- "$target"
        echo "Removed $target"
    elif [[ -e "$target" || -L "$target" ]]; then
        echo "Kept modified or unrelated file: $target" >&2
    fi
done
echo "Configuration, model profiles, logs, runtimes and models are retained."
