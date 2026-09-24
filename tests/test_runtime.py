"""Regression tests: only synthetic GGUFs, private HOME and local fake servers."""
import fcntl
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY_HELP = (ROOT / 'tests/fixtures/backend-help-legacy.txt').read_text()
MODERN_HELP = (ROOT / 'tests/fixtures/backend-help-modern.txt').read_text()
FAKE = '''#!/usr/bin/env python3
import http.server, os, sys, time
if '--help' in sys.argv:
    print(os.environ['FAKE_HELP'])
    sys.exit(0)
mode = os.environ.get('FAKE_MODE', 'ready')
if mode == 'exit':
    print('synthetic backend failure', flush=True)
    sys.exit(7)
if mode == 'timeout':
    time.sleep(60)
    sys.exit(0)
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')
    def log_message(self, *_): pass
host = sys.argv[sys.argv.index('--host') + 1]
port = int(sys.argv[sys.argv.index('--port') + 1])
http.server.HTTPServer((host, port), Handler).serve_forever()
'''


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = self.root / 'renamed model.gguf'
        self.model.write_bytes(b'GGUF' + struct.pack('<IQQ', 3, 0, 0))
        self.backend = self.root / 'fake-server'
        self.backend.write_text(FAKE)
        self.backend.chmod(0o755)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.env = {**os.environ, 'HOME': str(self.root), 'FAKE_HELP': LEGACY_HELP,
                    'XDG_CONFIG_HOME': str(self.root / 'config'),
                    'XDG_STATE_HOME': str(self.root / 'state'),
                    'XDG_DATA_HOME': str(self.root / 'data'),
                    'PMM_MODEL_ROOT': str(self.root),
                    'PMM_SERVER_BIN': str(self.backend),
                    'TEST_MODEL': str(self.model), 'TEST_PORT': str(self.port)}
        self.state = self.root / 'state/prism-model-manager'
        self.addCleanup(self.cleanup_server)

    def cleanup_server(self):
        # Clean only a test-owned PID with its recorded process start identity.
        pidfile = self.state / 'server.pid'
        try:
            pid = int(pidfile.read_text())
            stat = Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()
            if stat[19] == Path(str(pidfile) + '.start').read_text().strip():
                os.kill(pid, signal.SIGKILL)
        except (OSError, ValueError):
            pass

    def run_shell(self, code, *, env=None, ok=True):
        prefix = 'set -e\nsource "$1/bin/prism-model-manager"\nCURRENT_MODEL="$TEST_MODEL"\nPORT="$TEST_PORT"\npause() { :; }\ngum() { :; }\n'
        result = subprocess.run(['bash', '-c', prefix + code, 'test', str(ROOT)],
                                env={**self.env, **(env or {})}, text=True,
                                encoding='utf-8', errors='replace',
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=20)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result.stdout

    def test_ready_stop_and_runtime_endpoint_survives_edits(self):
        self.run_shell('start_server\npid=$(server_pid)\nHOST=invalid.example PORT=1\nserver_health\n[[ $(api_base) == "http://127.0.0.1:$TEST_PORT" ]]\nstop_server\n! server_pid\n[[ ! -f "$PIDFILE" ]]')

    def test_failed_start_returns_failure_and_cleans_identity(self):
        output = self.run_shell('if start_server; then exit 1; fi\n[[ ! -f "$PIDFILE" ]]', env={'FAKE_MODE': 'exit'})
        self.assertIn('synthetic backend failure', output)

    def test_timeout_cleans_only_launched_process(self):
        output = self.run_shell('STARTUP_TIMEOUT=1\nif start_server; then exit 1; fi\n! server_pid\n[[ ! -f "$PIDFILE" ]]', env={'FAKE_MODE': 'timeout'})
        self.assertIn('Startup timed out', output)

    def test_occupied_non_http_port_is_preserved(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', self.port))
            listener.listen()
            output = self.run_shell('if start_server; then exit 1; fi\n[[ ! -f "$PIDFILE" ]]')
            self.assertIn('Cannot bind', output)
            self.assertEqual(listener.getsockname()[1], self.port)

    def test_invalid_settings(self):
        for setting in ('PORT=65536', 'PORT=08080', 'NGL=-2', 'TEMP=nan',
                        'TOP_P=1.1', 'MIN_P=-1', 'TOP_K=no', 'CTX=0',
                        'UBATCH=1024', 'FLASH=invalid', 'CACHE_V=garbage',
                        'MTP=maybe', 'MTP_DRAFT_MAX=0', 'STARTUP_TIMEOUT=0'):
            with self.subTest(setting=setting):
                self.run_shell(setting + '\nvalidate_settings', ok=False)

    def test_mtp_variants_and_vision_arguments(self):
        projector = self.root / 'projector with spaces.gguf'
        projector.write_bytes(self.model.read_bytes())
        self.run_shell('''MTP=on VISION=on MMPROJ_PATH="$PMM_MODEL_ROOT/projector with spaces.gguf"
preflight
[[ " ${SERVER_ARGS[*]} " == *" --spec-type draft-mtp --spec-draft-n-max 3 "* ]]
[[ " ${SERVER_ARGS[*]} " == *" --mmproj $MMPROJ_PATH "* ]]
MTP_MODE=mtp
preflight
[[ " ${SERVER_ARGS[*]} " == *" --spec-type mtp --spec-draft-n-max 3 "* ]]
MTP_MODE=draft-mtp MTP_DRAFT_FLAG=--draft-max
preflight
[[ " ${SERVER_ARGS[*]} " == *" --spec-type draft-mtp --draft-max 3 "* ]]''')

    def test_mmproj_auto_is_used_when_advertised(self):
        help_text = MODERN_HELP + '\n--mmproj-auto                         auto-select adjacent projector\n'
        self.run_shell('''VISION=on
preflight
[[ $VISION_ARG_MODE == auto ]]
[[ " ${SERVER_ARGS[*]} " == *" --mmproj-auto "* ]]
[[ " ${SERVER_ARGS[*]} " != *" --mmproj "* ]]''', env={'FAKE_HELP': help_text})

    def test_unsupported_mtp_backend(self):
        self.run_shell('MTP=on\npreflight', env={'FAKE_HELP': LEGACY_HELP.split('--spec-type')[0]}, ok=False)

    def test_missing_and_ambiguous_projector(self):
        self.run_shell('VISION=on\nbuild_command', ok=False)
        for name in ('one-mmproj.gguf', 'two-mmproj.gguf'):
            (self.root / name).write_bytes(self.model.read_bytes())
        self.run_shell('VISION=on\nbuild_command', ok=False)
        self.run_shell('VISION=on MMPROJ_PATH="$PMM_MODEL_ROOT/one-mmproj.gguf"\nbuild_command')

    def test_explicit_projector_path_is_validated(self):
        output = self.run_shell('''VISION=on
MMPROJ_PATH="$PMM_MODEL_ROOT/missing-projector.gguf"
preflight''', ok=False)
        self.assertIn('Projector not readable:', output)

    def test_settings_round_trip(self):
        self.run_shell('MTP=on MTP_MODE=draft-mtp MTP_DRAFT_MAX=7 MTP_DRAFT_FLAG=--draft-max\nMMPROJ_PATH="/path with spaces/mmproj.gguf"\nsave_model_profile\nsave_config\nMTP=off MTP_MODE=mtp MTP_DRAFT_MAX=1 MMPROJ_PATH=""\nload_model_profile\n[[ $MTP == on && $MTP_MODE == draft-mtp && $MTP_DRAFT_MAX == 7 && $MTP_DRAFT_FLAG == --draft-max ]]\n[[ $MMPROJ_PATH == "/path with spaces/mmproj.gguf" ]]\nsource "$CONFIG"\n[[ $MTP == on ]]\n[[ $(stat -c %a "$CONFIG") == 600 ]]')

    def test_cancelled_switch_does_not_stop_model(self):
        self.run_shell('start_server\npid=$(server_pid)\nchoose_model() { return 1; }\nif switch_model; then exit 1; fi\n[[ $(server_pid) == "$pid" ]]\nchoose_model() { return 0; }\nsettings_menu() { return 0; }\ngum() { return 1; }\nif switch_model; then exit 1; fi\n[[ $(server_pid) == "$pid" ]]\nstop_server')

    def test_bad_candidate_does_not_stop_model(self):
        self.run_shell('start_server\npid=$(server_pid)\nCURRENT_MODEL=/missing/model.gguf\nif switch_server_locked "$pid"; then exit 1; fi\n[[ $(server_pid) == "$pid" ]]\nstop_server')

    def test_switch_rechecks_identity(self):
        self.run_shell('start_server\npid=$(server_pid)\nif switch_server_locked wrong; then exit 1; fi\n[[ $(server_pid) == "$pid" ]]\nstop_server')

    def test_switch_valid_model(self):
        (self.root / 'second.gguf').write_bytes(self.model.read_bytes())
        self.run_shell('start_server\npid=$(server_pid)\nCURRENT_MODEL="$PMM_MODEL_ROOT/second.gguf"\nwith_lifecycle_lock switch_server_locked "$pid"\n[[ $(server_pid) != "$pid" ]]\nsource "$STATE_DIR/runtime.env"\n[[ $RUN_MODEL == "$CURRENT_MODEL" ]]\nstop_server')

    def test_stale_identity_cannot_stop_other_process(self):
        self.run_shell('echo $$ > "$PIDFILE"\necho invalid > "$PIDFILE.start"\ncat /proc/sys/kernel/random/boot_id > "$PIDFILE.boot"\nstop_server\nkill -0 $$')

    def test_lifecycle_lock(self):
        self.state.mkdir(parents=True)
        with (self.state / 'lifecycle.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            output = self.run_shell('start_server', ok=False)
            self.assertIn('Another manager', output)

    def test_shards_and_exclusions(self):
        for name in ('split-00001-of-00002.gguf', 'split-00002-of-00002.gguf',
                     'mmproj.gguf', 'adapter-lora.gguf', 'model.gguf.part'):
            (self.root / name).write_bytes(self.model.read_bytes())
        self.run_shell('scan_models > "$HOME/scan"\n[[ $(wc -l < "$HOME/scan") == 2 ]]\nCURRENT_MODEL="$HOME/split-00001-of-00002.gguf"\npreflight\nrm "$HOME/split-00002-of-00002.gguf"\nif preflight; then exit 1; fi')

    def test_invalid_gguf_fails_before_backend_launch(self):
        self.model.write_bytes(b'not a model')
        self.run_shell('preflight', ok=False)

    def test_dry_run_does_not_execute_backend(self):
        self.backend.write_text('''#!/usr/bin/env bash
if [[ "$1" == --help ]]; then
  printf '%s\n' "$FAKE_HELP"
  exit 0
fi
touch "$HOME/unexpected-launch"
exit 1
''')
        self.backend.chmod(0o755)
        self.run_shell('"$1/bin/prism-model-manager" --dry-run "$TEST_MODEL"\n[[ ! -e "$HOME/unexpected-launch" ]]')

    def test_missing_backend(self):
        self.run_shell('SERVER_BIN=/missing/llama-server\npreflight', ok=False)

    def test_invalid_edit_restores_previous_value(self):
        self.run_shell('''title() { :; }
gum() {
    case "$1" in
        choose)
            if [ -f "$HOME/chosen" ]; then echo Back; else touch "$HOME/chosen"; echo 'Context size'; fi ;;
        input) echo invalid ;;
    esac
}
settings_menu edit
[[ $CTX == 4096 ]]
source "$CONFIG"
[[ $CTX == 4096 ]]
''')

    def test_boot_identity_mismatch_is_not_managed(self):
        self.run_shell('echo $$ > "$PIDFILE"\nprocess_start $$ > "$PIDFILE.start"\necho other-boot > "$PIDFILE.boot"\n! server_pid\nstop_server\nkill -0 $$')

    def test_second_start_keeps_existing_model(self):
        self.run_shell('start_server\npid=$(server_pid)\nif start_server; then exit 1; fi\n[[ $(server_pid) == "$pid" ]]\nstop_server')

    def test_removed_draft_flag_is_rejected(self):
        self.run_shell('MTP=on MTP_DRAFT_FLAG=--draft-max\npreflight', env={'FAKE_HELP': MODERN_HELP}, ok=False)

    def test_gpu_missing_still_reports_ram(self):
        output = self.run_shell('nvidia-smi() { return 1; }\nmemory_status')
        self.assertIn('NVIDIA usage unavailable', output)
        self.assertIn('RAM:', output)

    def test_failed_atomic_save_keeps_previous_config(self):
        self.run_shell('save_config\ncp "$CONFIG" "$HOME/previous"\nCTX=8192\nmv() { return 1; }\nif save_config; then exit 1; fi\ncmp "$CONFIG" "$HOME/previous"')

    def test_modern_replacement_flag_is_not_removed(self):
        self.run_shell('MTP=on MTP_MODE=draft-mtp\npreflight\n[[ " ${SERVER_ARGS[*]} " == *" --spec-type draft-mtp --spec-draft-n-max 3 "* ]]', env={'FAKE_HELP': MODERN_HELP})

    def test_mode_is_validated_against_spec_type_usage(self):
        output = self.run_shell('MTP=on MTP_MODE=mtp\npreflight', env={'FAKE_HELP': MODERN_HELP + '\nDescription mentions mtp, but does not advertise it.\n'}, ok=False)
        self.assertIn("Unsupported MTP mode 'mtp'", output)
        self.assertIn('draft-mtp', output)

    def test_description_reference_does_not_advertise_flag(self):
        help_text = MODERN_HELP.replace('--mmproj FILE                          vision projector', 'Vision is available elsewhere with --mmproj FILE')
        (self.root / 'mmproj.gguf').write_bytes(self.model.read_bytes())
        self.run_shell('VISION=on\npreflight', env={'FAKE_HELP': help_text}, ok=False)

    def test_validation_failure_remains_visible_after_pause_eof(self):
        output = self.run_shell('''start_server
pid=$(server_pid)
choose_model() { return 0; }
settings_menu() { MTP=on; MTP_MODE=mtp; }
export FAKE_HELP="$MODERN_HELP"
pause() { read -r ignored < /dev/null || true; }
if switch_model; then exit 1; fi
[[ $LAST_ACTION == *"Validation failed"* && $LAST_ACTION == *"Unsupported MTP mode"* ]]
[[ $(server_pid) == "$pid" ]]
stop_server
''', env={'MODERN_HELP': MODERN_HELP})
        self.assertIn('Unsupported MTP mode', output)

    def test_start_failure_result_is_preserved(self):
        self.run_shell('''choose_model() { return 0; }
settings_menu() { return 0; }
if switch_model; then exit 1; fi
[[ $LAST_ACTION == *"Model loading failed"* && $LAST_ACTION == *"synthetic backend failure"* ]]
''', env={'FAKE_MODE': 'exit'})

    def test_load_success_result(self):
        self.run_shell('''choose_model() { return 0; }
settings_menu() { return 0; }
switch_model
[[ $LAST_ACTION == "Model loading succeeded." ]]
server_health
stop_server
''')

    def test_settings_cancellation_preserves_running_model(self):
        self.run_shell('''start_server
pid=$(server_pid)
choose_model() { return 0; }
settings_menu() { return 1; }
if switch_model; then exit 1; fi
[[ $LAST_ACTION == *"cancelled in settings"* ]]
[[ $(server_pid) == "$pid" ]]
stop_server
''')

    def test_cancelled_backend_edit_preserves_saved_path(self):
        for value in ('', '/missing/runtime'):
            with self.subTest(value=value):
                self.run_shell('''unset PMM_SERVER_BIN
title() { :; }
gum() {
    case "$1" in
        choose) if [ -f "$HOME/chosen" ]; then echo Back; else touch "$HOME/chosen"; echo 'Backend executable'; fi ;;
        input) printf '%s' "$INPUT_VALUE" ;;
    esac
}
rm -f "$HOME/chosen"
old_backend=$SERVER_BIN
settings_menu edit
[[ $SERVER_BIN == "$old_backend" ]]
source "$CONFIG"
[[ $SERVER_BIN == "$old_backend" ]]
''', env={'INPUT_VALUE': value})

    def test_backend_override_precedence_and_edit_lock(self):
        self.run_shell('''printf 'SERVER_BIN=/missing/saved-backend\\n' > "$CONFIG"
source "$1/bin/prism-model-manager"
[[ $SERVER_BIN == "$PMM_SERVER_BIN" ]]
title() { :; }
gum() {
    case "$1" in
        choose) if [ -f "$HOME/chosen" ]; then echo Back; else touch "$HOME/chosen"; echo 'Backend executable'; fi ;;
        input) touch "$HOME/unexpected-edit" ;;
    esac
}
settings_menu edit
[[ ! -e "$HOME/unexpected-edit" ]]
[[ $SERVER_BIN == "$PMM_SERVER_BIN" ]]
''')

    def test_saved_explicit_backend_is_not_replaced_by_path_fallback(self):
        self.run_shell('''unset PMM_SERVER_BIN
printf 'SERVER_BIN=/missing/custom-backend\\n' > "$CONFIG"
source "$1/bin/prism-model-manager"
[[ $SERVER_BIN == /missing/custom-backend ]]
if build_command; then exit 1; fi
''')

    def test_legacy_spec_settings_migrate_without_overriding_canonical_values(self):
        config_dir = self.root / 'config/prism-model-manager'
        config_dir.mkdir(parents=True)
        (config_dir / 'config.env').write_text(
            'SPEC_MODE=mtp\nSPEC_DRAFT_MODEL=/legacy/draft.gguf\nSPEC_DRAFT_TOKENS=7\n')
        self.run_shell('''[[ $MTP == on && $MTP_MODE == mtp && $MTP_DRAFT_MAX == 7 ]]
[[ $LEGACY_SPEC_DRAFT_MODEL_SET == 1 ]]''')
        (config_dir / 'config.env').write_text(
            'MTP=off\nMTP_MODE=draft-mtp\nMTP_DRAFT_MAX=2\n'
            'SPEC_MODE=mtp\nSPEC_DRAFT_MODEL=/legacy/draft.gguf\nSPEC_DRAFT_TOKENS=7\n')
        self.run_shell('''[[ $MTP == off && $MTP_MODE == draft-mtp && $MTP_DRAFT_MAX == 2 ]]''')

    def test_session_backend_override_is_not_persisted(self):
        config_dir = self.root / 'config/prism-model-manager'
        config_dir.mkdir(parents=True)
        (config_dir / 'config.env').write_text(
            'SERVER_BIN=/saved/backend\nMODEL_ROOT=/saved/models\n')
        self.run_shell('''save_config
source "$CONFIG"
[[ $SERVER_BIN == /saved/backend ]]
[[ $MODEL_ROOT == /saved/models ]]
! grep -q '/session/backend' "$CONFIG"
''', env={'PMM_SERVER_BIN': '/session/backend', 'PMM_MODEL_ROOT': '/session/models'})

    def test_runtime_state_status_and_clear_are_non_destructive(self):
        output = self.run_shell('''server_health() { return 1; }
echo $$ > "$PIDFILE"
echo invalid > "$PIDFILE.start"
cat /proc/sys/kernel/random/boot_id > "$PIDFILE.boot"
set +e
runtime_state_status
state_status=$?
set -e
[[ $state_status == 2 ]]
clear_stale_state
[[ ! -e "$PIDFILE" && ! -e "$PIDFILE.start" && ! -e "$PIDFILE.boot" ]]
kill -0 $$
''')
        self.assertIn('STALE:', output)

    def test_api_models_info_selects_loaded_model_and_rejects_unreachable(self):
        self.run_shell('''echo $$ > "$PIDFILE"
process_start $$ > "$PIDFILE.start"
cat /proc/sys/kernel/random/boot_id > "$PIDFILE.boot"
printf 'RUN_MODEL=%q\\n' "$PMM_MODEL_ROOT/loaded model.gguf" > "$STATE_DIR/runtime.env"
curl() { printf '%s' '{"data":[{"id":"other"},{"id":"loaded model.gguf"}]}'; }
[[ $(api_models_info) == 'loaded model.gguf' ]]
curl() { return 6; }
if api_models_info; then exit 1; fi
''')


if __name__ == '__main__':
    unittest.main()
