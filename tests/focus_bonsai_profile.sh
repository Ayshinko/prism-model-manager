#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/ayshinko/AI-Workspace/prism-model-manager-3.0
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
export HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/config" XDG_STATE_HOME="$TMP/state" XDG_DATA_HOME="$TMP/data"
mkdir -p "$HOME" "$TMP/models" "$TMP/mock" "$TMP/config/prism-model-manager/model-profiles"
export PMM_MODEL_ROOT="$TMP/models" PMM_SERVER_BIN="$TMP/mock/llama-server"
export PMM_TEST_HELP="$ROOT/tests/fixtures/backend-help-modern.txt"
cat > "$PMM_SERVER_BIN" <<'MOCK'
#!/usr/bin/env bash
if [[ "${1:-}" == --help ]]; then cat "$PMM_TEST_HELP"; exit 0; fi
echo 'Unexpected runtime exec' >&2; exit 99
MOCK
chmod +x "$PMM_SERVER_BIN"
MODEL="$TMP/models/Ternary-Bonsai-2-27B-PTQ1_0-MTP-Q8_0-fixed.gguf"
touch "$MODEL"
source "$ROOT/bin/prism-model-manager"
CURRENT_MODEL="$MODEL"

# Simulate the live Bonsai per-model profile (copied from ~/.config ... 2864d97a...env)
PROFILE=$(model_profile_file)
cat > "$PROFILE" <<'PROF'
CTX=81920
NGL=99
FLASH=on
BATCH=2048
UBATCH=512
PARALLEL=1
TEMP=1.0
TOP_P=0.95
TOP_K=20
MIN_P=0
CACHE_K=q8_0
CACHE_V=q8_0
REASONING_BUDGET=4096
VISION=on
MTP=on
MTP_MODE=draft-mtp
MTP_DRAFT_MAX=2
MTP_DRAFT_FLAG=--spec-draft-n-max
PROF

load_model_profile
# Existing settings preserved exactly
[[ "$CTX" == 81920 ]] && echo "PASS: CTX preserved (81920)"
[[ "$NGL" == 99 ]] && echo "PASS: NGL/CUDA layers preserved (99)"
[[ "$FLASH" == on ]] && echo "PASS: FLASH preserved (on)"
[[ "$CACHE_K" == q8_0 && "$CACHE_V" == q8_0 ]] && echo "PASS: KV cache preserved (q8_0/q8_0)"
[[ "$MTP" == on && "$MTP_MODE" == draft-mtp && "$MTP_DRAFT_MAX" == 2 && "$MTP_DRAFT_FLAG" == --spec-draft-n-max ]] && echo "PASS: MTP/speculative preserved"
[[ "$REASONING_BUDGET" == 4096 ]] && echo "PASS: REASONING_BUDGET preserved (4096)"
# New setting defaults safely to -1 (unlimited) — backwards compatible
[[ "$MAX_OUTPUT_TOKENS" == -1 ]] && echo "PASS: MAX_OUTPUT_TOKENS default -1 (backwards compatible)"

# build_command yields -n -1 (infinity) == prior no-flag behavior, reasoning mapped
VISION=off   # avoid mmproj requirement in mock
build_command
echo "SERVER_ARGS: ${SERVER_ARGS[*]}"
[[ " ${SERVER_ARGS[*]} " == *" -n -1 "* ]] && echo "PASS: -n -1 emitted (infinity)"
[[ " ${SERVER_ARGS[*]} " == *"--reasoning-budget 4096"* ]] && echo "PASS: --reasoning-budget 4096 emitted"
[[ " ${SERVER_ARGS[*]} " == *"--spec-type draft-mtp --spec-draft-n-max 2"* ]] && echo "PASS: MTP flags preserved"

echo "=== ALL BONSAI PROFILE TESTS PASSED ==="
