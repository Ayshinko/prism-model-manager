#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/ayshinko/AI-Workspace/prism-model-manager-3.0
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
export HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/config" XDG_STATE_HOME="$TMP/state" XDG_DATA_HOME="$TMP/data"
mkdir -p "$HOME" "$TMP/models" "$TMP/mock"
export PMM_MODEL_ROOT="$TMP/models" PMM_SERVER_BIN="$TMP/mock/llama-server"
export PMM_TEST_HELP="$ROOT/tests/fixtures/backend-help-modern.txt"
cat > "$PMM_SERVER_BIN" <<'MOCK'
#!/usr/bin/env bash
if [[ "${1:-}" == --help ]]; then cat "$PMM_TEST_HELP"; exit 0; fi
echo 'Unexpected runtime exec' >&2; exit 99
MOCK
chmod +x "$PMM_SERVER_BIN"
touch "$PMM_MODEL_ROOT/Bonsai-PTQ1_0.gguf"
source "$ROOT/bin/prism-model-manager"

[[ "$MAX_OUTPUT_TOKENS" == -1 ]] && echo "PASS: MAX_OUTPUT_TOKENS default is -1"
[[ "$REASONING_BUDGET" == -1 ]] && echo "PASS: REASONING_BUDGET default is -1"

CURRENT_MODEL="$PMM_MODEL_ROOT/Bonsai-PTQ1_0.gguf"
MAX_OUTPUT_TOKENS=-1
REASONING_BUDGET=-1
build_command
[[ " ${SERVER_ARGS[*]} " == *" -n -1 "* ]] && echo "PASS: build_command emits '-n -1' for MAX_OUTPUT_TOKENS=-1"
[[ " ${SERVER_ARGS[*]} " != *"--reasoning-budget"* ]] && echo "PASS: REASONING_BUDGET=-1 omits --reasoning-budget"

MAX_OUTPUT_TOKENS=4096
REASONING_BUDGET=2048
build_command
[[ " ${SERVER_ARGS[*]} " == *" -n 4096 "* ]] && echo "PASS: build_command emits '-n 4096'"
[[ " ${SERVER_ARGS[*]} " == *"--reasoning-budget 2048"* ]] && echo "PASS: emits '--reasoning-budget 2048'"

MAX_OUTPUT_TOKENS=-1; REASONING_BUDGET=-1; validate_settings && echo "PASS: validate accepts -1"
MAX_OUTPUT_TOKENS=0; REASONING_BUDGET=0; validate_settings && echo "PASS: validate accepts 0"
MAX_OUTPUT_TOKENS=4096; REASONING_BUDGET=12345; validate_settings && echo "PASS: validate accepts positives"
if MAX_OUTPUT_TOKENS=abc; REASONING_BUDGET=-1; validate_settings 2>/dev/null; then echo "FAIL: abc accepted"; exit 1; fi
echo "PASS: validate rejects 'abc'"
if MAX_OUTPUT_TOKENS=0800; REASONING_BUDGET=-1; validate_settings 2>/dev/null; then echo "FAIL: leading-zero 0800 accepted"; exit 1; fi
echo "PASS: validate rejects leading-zero '0800'"

MAX_OUTPUT_TOKENS=8192; REASONING_BUDGET=64
save_config
MAX_OUTPUT_TOKENS=-1; REASONING_BUDGET=-1
source "$CONFIG"
[[ "$MAX_OUTPUT_TOKENS" == 8192 && "$REASONING_BUDGET" == 64 ]] && echo "PASS: config round-trip preserves MAX_OUTPUT_TOKENS=8192 and REASONING_BUDGET=64"

echo "=== ALL FOCUSED TESTS PASSED ==="
