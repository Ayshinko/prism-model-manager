#!/usr/bin/env bash
# Intentional literal shell metacharacters test safe config serialization.
# shellcheck disable=SC2016
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
export HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/config" XDG_STATE_HOME="$TMP/state" XDG_DATA_HOME="$TMP/data"
mkdir -p "$HOME" "$TMP/models with spaces" "$TMP/mock"
export PMM_MODEL_ROOT="$TMP/models with spaces" PMM_SERVER_BIN="$TMP/mock/llama-server"
cat > "$PMM_SERVER_BIN" <<'MOCK'
#!/usr/bin/env bash
echo 'Unexpected server execution' >&2
exit 99
MOCK
chmod +x "$PMM_SERVER_BIN"
touch "$PMM_MODEL_ROOT/Bonsai-PTQ1_0.gguf" "$PMM_MODEL_ROOT/model two.gguf" "$PMM_MODEL_ROOT/mmproj.gguf" "$PMM_MODEL_ROOT/adapter-lora.gguf" "$PMM_MODEL_ROOT/incomplete.gguf.part"
# shellcheck source=../bin/prism-model-manager
source "$ROOT/bin/prism-model-manager"
check() { echo "PASS: $*"; }
[[ $(scan_models | wc -l) == 2 ]]
check 'scan excludes adapters, projectors and partial downloads; supports spaces'
for format in PTQ1_0 PQ2_0 Q2_0 Q1_0; do
    [[ $(model_info "Bonsai-$format.gguf") == *"$format"* ]]
done
[[ $(model_info unknown.gguf) == *Unknown* ]]
check 'four quantization hints plus unknown fallback'
CURRENT_MODEL="$PMM_MODEL_ROOT/model two.gguf"
LORA_PATH='$HOME/literal $(touch SHOULD_NOT_EXIST) adapter.gguf'
CTX=2048
save_config
LORA_PATH=''
# shellcheck disable=SC1090
source "$CONFIG"
[[ "$LORA_PATH" == '$HOME/literal $(touch SHOULD_NOT_EXIST) adapter.gguf' ]]
[[ ! -e SHOULD_NOT_EXIST && $(stat -c %a "$CONFIG") == 600 ]]
save_model_profile
CTX=8192
load_model_profile
[[ "$CTX" == 2048 ]]
check 'escaped config and per-model profile round trip; private file permissions'
build_command
[[ ${SERVER_ARGS[2]} == "$CURRENT_MODEL" ]]
[[ " ${SERVER_ARGS[*]} " == *' -c 2048 '* ]]
LORA_ENABLED=on
LORA_PATH="$TMP/adapter with spaces.gguf"
touch "$LORA_PATH" "$(dirname "$CURRENT_MODEL")/mmproj.gguf"
VISION=on REASONING_BUDGET=32
build_command
[[ " ${SERVER_ARGS[*]} " == *"--lora-scaled $LORA_PATH:2"* ]]
[[ " ${SERVER_ARGS[*]} " == *'--reasoning-budget 32'* ]]
[[ " ${SERVER_ARGS[*]} " == *'--mmproj '* ]]
CTX=invalid
if build_command 2>/dev/null; then exit 1; fi
CTX=2048
check 'command arrays, optional LoRA/vision/reasoning flags and invalid context'
"$ROOT/bin/prism-model-manager" --dry-run "$CURRENT_MODEL" > "$TMP/dry-run"
[[ -s "$TMP/dry-run" ]]
check 'dry-run never executes runtime'
cat > "$TMP/mock/nvidia-smi" <<'MOCK'
#!/usr/bin/env bash
echo 'Mock NVIDIA RTX, 8.9'
MOCK
cat > "$TMP/mock/less" <<'MOCK'
#!/usr/bin/env bash
[[ "$1" == +F ]]
cat "$2"
MOCK
chmod +x "$TMP/mock/"*
export PATH="$TMP/mock:$PATH"
[[ $(gpu_info) == *'Ada: prefer PTQ1_0'* ]]
printf '#!/usr/bin/env bash\nexit 1\n' > "$TMP/mock/nvidia-smi"
[[ $(gpu_info) == *'architecture unknown'* ]]
echo 'test log content' > "$LOGFILE"
[[ $(show_logs) == 'test log content' ]]
check 'Ada advice, missing driver fallback and less +F log viewer'
echo "$$" > "$PIDFILE"
echo invalid > "$PIDFILE.start"
if server_pid; then exit 1; fi
check 'stale PID identity rejected'
# Start only a tiny fake process. Never execute the configured real runtime.
cat > "$PMM_SERVER_BIN" <<'MOCK'
#!/usr/bin/env bash
if [[ "${1:-}" == --help ]]; then
    echo '-m -ngl -fa -c -b -ub -np --temp --top-p --top-k --min-p --host --port --cache-type-k --cache-type-v --jinja --mmproj --reasoning-budget'
    exit 0
fi
exec sleep 30
MOCK
pause() { :; }
gum() { :; }
curl() { echo '{}'; }
server_health() { server_pid >/dev/null; }
python3 - "$CURRENT_MODEL" <<'PYMODEL'
import struct, sys
with open(sys.argv[1], 'wb') as f:
    f.write(b'GGUF' + struct.pack('<IQQ', 3, 0, 0))
PYMODEL
LORA_ENABLED=off VISION=off
save_model_profile
start_server
managed_pid=$(server_pid)
[[ "$managed_pid" =~ ^[0-9]+$ ]]
stop_server
if kill -0 "$managed_pid" 2>/dev/null; then exit 1; fi
check 'start and stop lifecycle with a fake process only'

PREFIX="$TMP/install prefix" "$ROOT/install.sh"
if PREFIX="$TMP/install prefix" "$ROOT/install.sh" 2>/dev/null; then exit 1; fi
[[ $("$TMP/install prefix/bin/prism-model-manager" --version) == 2.0.0 ]]
PREFIX="$TMP/install prefix" "$ROOT/uninstall.sh"
[[ ! -e "$TMP/install prefix/bin/prism-model-manager" && -f "$CONFIG" && -f "$LOGFILE" ]]
PREFIX="$TMP/install prefix" "$ROOT/uninstall.sh"
check 'installation, overwrite refusal, installed execution, uninstall, retained data and idempotence'
echo 'All tests passed; no real model or GPU workload executed.'
