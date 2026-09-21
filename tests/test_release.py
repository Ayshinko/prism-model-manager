"""Minimal-release checks; never launch a backend or signal an inference service."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'bin/prism-model-manager'


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('PMM_', 'XDG_'))}
        self.env.update(HOME=str(self.home), PMM_APP=str(APP))

    def shell(self, code, *, ok=True, env=None):
        result = subprocess.run(['bash', '-c', 'set -e\nsource "$PMM_APP"\n' + code],
                                env={**self.env, **(env or {})}, capture_output=True,
                                text=True, timeout=15)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def config(self, text):
        config = self.home / '.config/prism-model-manager/config.env'
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(text)
        return config

    def test_reference_inference_functions_are_unchanged(self):
        source = APP.read_text()
        hashes = json.loads((ROOT / 'tests/reference-functions.json').read_text())
        for name, expected in hashes.items():
            with self.subTest(function=name):
                body = re.search(rf'^{name}\(\) \{{\n.*?^\}}', source, re.M | re.S).group()
                self.assertEqual(hashlib.sha256(body.encode()).hexdigest(), expected)

    def test_defaults_and_home_layout(self):
        self.shell('[[ $CTX == 8192 && $UBATCH == 512 && $BATCH == 512 ]]\n[[ $NGL == 99 && $FLASH == on && $SPEC_MODE == OFF ]]\n[[ $MODEL_ROOT == "$HOME/Models" && $PRISM_ROOT == "$HOME/prism-llama" ]]\n[[ $CONFIG == "$HOME/.config/prism-model-manager/config.env" ]]\n[[ $SERVER_BIN == "$HOME/prism-llama/build-cuda/bin/llama-server" ]]')

    def test_configured_root_is_used_before_backend_derivation(self):
        self.config('PRISM_ROOT="$HOME/custom runtime"\nCTX=40960\nCACHE_K=q8_0\n')
        self.shell('[[ $SERVER_BIN == "$HOME/custom runtime/build-cuda/bin/llama-server" ]]\n[[ $CTX == 40960 && $CACHE_K == q8_0 ]]')

    def test_explicit_configured_backend_wins_over_root(self):
        self.config('PRISM_ROOT=/unused\nSERVER_BIN="$HOME/selected server"\nBENCH_BIN="$HOME/selected bench"\n')
        self.shell('[[ $SERVER_BIN == "$HOME/selected server" && $BENCH_BIN == "$HOME/selected bench" ]]')

    def test_environment_overrides_saved_paths(self):
        self.config('MODEL_ROOT=/saved/models\nPRISM_ROOT=/saved/root\nSERVER_BIN=/saved/server\nBENCH_BIN=/saved/bench\n')
        self.shell('[[ $MODEL_ROOT == /override/models && $PRISM_ROOT == /override/root ]]\n[[ $SERVER_BIN == /override/server && $BENCH_BIN == /override/bench ]]', env={
            'PMM_MODEL_ROOT': '/override/models', 'PMM_PRISM_ROOT': '/override/root',
            'PMM_SERVER_BIN': '/override/server', 'PMM_BENCH_BIN': '/override/bench'})

    def test_empty_saved_backend_uses_configured_root(self):
        self.config('PRISM_ROOT=/chosen/root\nSERVER_BIN=""\n')
        self.shell('[[ $SERVER_BIN == /chosen/root/build-cuda/bin/llama-server ]]')

    def test_configuration_and_profile_roundtrip(self):
        self.shell('''CURRENT_MODEL="$HOME/model with spaces.gguf"
SERVER_BIN="$HOME/server with spaces"
BENCH_BIN="$HOME/bench with spaces"
SPEC_MODE=MTP SPEC_DRAFT_MODEL="$HOME/draft with spaces.gguf" SPEC_DRAFT_TOKENS=6
LORA_PATH='literal $(touch SHOULD_NOT_EXIST)'
CTX=16384 CACHE_K=q8_0
save_config
save_model_profile
SPEC_MODE=OFF SPEC_DRAFT_TOKENS=1 CTX=2
load_model_profile
[[ $SPEC_MODE == MTP && $SPEC_DRAFT_TOKENS == 6 && $CTX == 16384 && $CACHE_K == q8_0 ]]
source "$CONFIG"
[[ $SERVER_BIN == "$HOME/server with spaces" && $BENCH_BIN == "$HOME/bench with spaces" ]]
[[ $LORA_PATH == 'literal $(touch SHOULD_NOT_EXIST)' && ! -e SHOULD_NOT_EXIST ]]
[[ $(stat -c %a "$CONFIG") == 600 ]]
''')

    def test_cli_is_documented_and_does_not_save_config(self):
        for option, expected in [('--version', '2.0.0'), ('-V', '2.0.0'), ('--help', 'Usage:'), ('-h', 'Usage:')]:
            result = subprocess.run([str(APP), option], env=self.env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn(expected, result.stdout)
        self.assertFalse((self.home / '.config/prism-model-manager/config.env').exists())
        for option in ('--scan', '--info', '--gpu', '--dry-run', '--logs'):
            result = subprocess.run([str(APP), option], env=self.env, capture_output=True)
            self.assertEqual(result.returncode, 2)

    def test_discovery_exclusions_and_spaces(self):
        self.shell('''MODEL_ROOT="$HOME/models"
mkdir -p "$MODEL_ROOT"
touch "$MODEL_ROOT/model with spaces.gguf" "$MODEL_ROOT/mmproj.gguf" "$MODEL_ROOT/abliterate-lora.gguf" "$MODEL_ROOT/test-dspark.gguf" "$MODEL_ROOT/kv-bias.gguf" "$MODEL_ROOT/test.gguf.part"
gum() { cat > "$HOME/picker"; head -n 1 "$HOME/picker"; }
choose_model
[[ $CURRENT_MODEL == "$MODEL_ROOT/model with spaces.gguf" ]]
[[ $(wc -l < "$HOME/picker") == 1 ]]
''')

    def test_inference_argument_modes_and_optional_features(self):
        for mode, draft, expected in [('OFF', False, None), ('MTP', False, 'draft-mtp'),
                                       ('MTP', True, 'draft-mtp'), ('Draft Model', True, 'draft-simple')]:
            with self.subTest(mode=mode, draft=draft):
                self.shell('''CURRENT_MODEL="$HOME/model with spaces.gguf"
LORA_PATH="$HOME/adapter with spaces.gguf"
SPEC_MODE="$TEST_MODE" SPEC_DRAFT_MODEL="" SPEC_DRAFT_TOKENS=4
if [[ $TEST_DRAFT == yes ]]; then SPEC_DRAFT_MODEL="$HOME/draft.gguf"; fi
touch "$CURRENT_MODEL" "$LORA_PATH" "$HOME/draft.gguf" "$HOME/mmproj.gguf"
LORA_ENABLED=on VISION=on REASONING_BUDGET=32
SERVER_BIN=/bin/true
save_model_profile
rm -f "$HOME/args"
gum() { :; }
pause() { :; }
curl() { printf '{}'; }
server_health() { [[ -s "$HOME/args" ]]; }
kill() { return 0; }
nohup() { printf '%s\\0' "$@" > "$HOME/args"; }
start_server
wait
''', env={'TEST_MODE': mode, 'TEST_DRAFT': 'yes' if draft else 'no'})
                args = (self.home / 'args').read_bytes().decode().strip('\0').split('\0')
                self.assertEqual(args[args.index('-c') + 1], '8192')
                self.assertEqual(args[args.index('-ub') + 1], '512')
                self.assertEqual(args[args.index('--mmproj') + 1], str(self.home / 'mmproj.gguf'))
                self.assertEqual(args[args.index('--lora-scaled') + 1], str(self.home / 'adapter with spaces.gguf') + ':2')
                self.assertEqual(args[args.index('--reasoning-budget') + 1], '32')
                if expected:
                    self.assertEqual(args[args.index('--spec-type') + 1], expected)
                    self.assertEqual(args[args.index('--spec-draft-n-max') + 1], '4')
                else:
                    self.assertNotIn('--spec-type', args)
                self.assertEqual('--spec-draft-model' in args, draft)

    def test_invalid_draft_tokens_do_not_launch(self):
        self.shell('''CURRENT_MODEL="$HOME/model.gguf"
touch "$CURRENT_MODEL"
SERVER_BIN=/bin/true SPEC_MODE=MTP SPEC_DRAFT_TOKENS=9
save_model_profile
server_health() { return 1; }
pause() { :; }
gum() { :; }
nohup() { touch "$HOME/unexpected"; }
start_server
[[ ! -e "$HOME/unexpected" ]]
''')

    def test_install_refusal_and_uninstall_preserve_data(self):
        prefix = self.home / 'install prefix'
        env = {**self.env, 'PREFIX': str(prefix)}
        def run(name):
            return subprocess.run([str(ROOT / name)], env=env, text=True, capture_output=True)
        self.assertEqual(run('install.sh').returncode, 0)
        self.assertEqual(sorted(p.name for p in (prefix / 'bin').iterdir()), ['prism-lora-ab-score.py', 'prism-model-manager'])
        self.assertNotEqual(run('install.sh').returncode, 0)
        version = subprocess.check_output([str(prefix / 'bin/prism-model-manager'), '--version'], env=env, text=True)
        self.assertEqual(version.strip(), '2.0.0')
        config = self.config('CTX=4096\n')
        (prefix / 'bin/prism-lora-ab-score.py').write_text('user modified helper')
        self.assertEqual(run('uninstall.sh').returncode, 0)
        self.assertTrue(config.exists())
        self.assertTrue((prefix / 'bin/prism-lora-ab-score.py').exists())
        self.assertFalse((prefix / 'bin/prism-model-manager').exists())


if __name__ == '__main__':
    unittest.main()
