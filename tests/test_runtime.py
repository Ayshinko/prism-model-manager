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
FAKE = '''#!/usr/bin/env python3
import http.server, os, sys, time
if '--help' in sys.argv:
    print(os.environ.get('FAKE_HELP', '-m -ngl -fa -c -b -ub -np --temp --top-p --top-k --min-p --host --port --cache-type-k --cache-type-v --jinja --mmproj --spec-type [none,mtp,draft-mtp] --spec-draft-n-max --draft-max --lora-scaled --reasoning-budget'))
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
        self.env = {**os.environ, 'HOME': str(self.root),
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
        self.run_shell('MTP=on VISION=on MMPROJ_PATH="$PMM_MODEL_ROOT/projector with spaces.gguf"\npreflight\n[[ " ${SERVER_ARGS[*]} " == *" --spec-type mtp --spec-draft-n-max 3 "* ]]\n[[ " ${SERVER_ARGS[*]} " == *" --mmproj $MMPROJ_PATH "* ]]\nMTP_MODE=draft-mtp MTP_DRAFT_FLAG=--draft-max\npreflight\n[[ " ${SERVER_ARGS[*]} " == *" --spec-type draft-mtp --draft-max 3 "* ]]')

    def test_unsupported_mtp_backend(self):
        self.run_shell('MTP=on\npreflight', env={'FAKE_HELP': '-m -ngl -fa -c -b -ub -np --temp --top-p --top-k --min-p --host --port --cache-type-k --cache-type-v --jinja'}, ok=False)

    def test_missing_and_ambiguous_projector(self):
        self.run_shell('VISION=on\nbuild_command', ok=False)
        for name in ('one-mmproj.gguf', 'two-mmproj.gguf'):
            (self.root / name).write_bytes(self.model.read_bytes())
        self.run_shell('VISION=on\nbuild_command', ok=False)
        self.run_shell('VISION=on MMPROJ_PATH="$PMM_MODEL_ROOT/one-mmproj.gguf"\nbuild_command')

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
        self.backend.write_text('#!/bin/sh\ntouch "$HOME/unexpected-launch"\nexit 1\n')
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
        help_text = '-m -ngl -fa -c -b -ub -np --temp --top-p --top-k --min-p --host --port --cache-type-k --cache-type-v --jinja --spec-type mtp\n--draft-max N\nargument has been removed'
        self.run_shell('MTP=on MTP_DRAFT_FLAG=--draft-max\npreflight', env={'FAKE_HELP': help_text}, ok=False)

    def test_gpu_missing_still_reports_ram(self):
        output = self.run_shell('nvidia-smi() { return 1; }\nmemory_status')
        self.assertIn('NVIDIA usage unavailable', output)
        self.assertIn('RAM:', output)

    def test_failed_atomic_save_keeps_previous_config(self):
        self.run_shell('save_config\ncp "$CONFIG" "$HOME/previous"\nCTX=8192\nmv() { return 1; }\nif save_config; then exit 1; fi\ncmp "$CONFIG" "$HOME/previous"')


if __name__ == '__main__':
    unittest.main()
