# 3.1.0 release verification

Checks use temporary HOME/XDG directories, synthetic GGUF headers, fake backend
help and test-owned Python HTTP servers or sleep processes. Existing model files,
custom inference backends, running inference services and system configuration
are not modified. No real model is loaded and no benchmark is executed.

Candidate results (fixture-based, not a real model performance or compatibility
certification):

- `bash -n` syntax: PASS for `bin/prism-model-manager`, `install.sh`,
  `uninstall.sh` and `tests/*.sh`.
- ShellCheck: **not run** — `shellcheck` is not installed in this environment
  (`exit 127`), so it must not be claimed as passing. Run it in a CI or
  maintainer environment before release.
- Python syntax/AST compilation: PASS for `bin/prism-backend-info.py` and the
  analyzer helpers.
- Python regression suite: **55 tests PASS**
  (`test_metadata.py` ×4, `test_backend_info.py` ×10, `test_runtime.py` ×41).
- Shell integration suite (`tests/test.sh`): PASS.
- Focused regression tests (`tests/focus_max_tokens.sh`, `tests/focus_bonsai_profile.sh`): PASS.
- `git diff --check`: PASS (no whitespace errors).

Run from the repository root:

```bash
bash -n bin/prism-model-manager install.sh uninstall.sh tests/*.sh
shellcheck -x -P SCRIPTDIR bin/prism-model-manager install.sh uninstall.sh tests/*.sh
bash tests/test.sh
bash tests/focus_max_tokens.sh
bash tests/focus_bonsai_profile.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Coverage includes backend-help parsing (aliases, boolean flags, wrapped
descriptions, ANSI output, removed options, composite usage forms, and prose that
must not be advertised); model scanning/exclusions and split shards; escaped
private configuration and profile round trips; config-provenance tracking and
legacy `SPEC_*` migration; session-only `PMM_SERVER_BIN` override; atomic
persistence; command arguments; MTP mode/draft flag variants; missing, ambiguous
and auto-selected projectors; unsupported or missing backends; occupied
non-HTTP ports; process identity and lifecycle locks; ready, failed and timed-out
starts; cancelled, invalid and successful switches; stable loaded endpoints after
config edits; no-execution dry runs; `--api-ready` unreachable exit code;
install/uninstall and retained data; MAX_OUTPUT_TOKENS default, round-trip and
build-command emission; REASONING_BUDGET -1/0/positive/preserved semantics;
backwards-compatible new-setting defaults for existing model profiles.

Remaining manual checks: real GGUF tensor integrity, custom backend/CUDA
compatibility, actual MTP decoding and vision responses (including their combined
operation), VRAM behavior under load, and full interactive terminal rendering.
Backend help fixtures test flag handling, not actual backend compatibility. Very
large GGUF metadata that exceeds the bounded inspector's 64 MiB limit is rejected
by preflight. No automatic recovery to the old model follows a confirmed switch
whose replacement fails during real loading. This candidate was released as
v3.1.0 after the checks above; this file documents the validation that was run
for that release.