# 2.0.0 development candidate verification

Checks use temporary HOME/XDG directories, synthetic GGUF headers, fake backend
help and test-owned Python HTTP servers or sleep processes. Existing model files,
custom inference backends, running inference services and system configuration
are not modified. No real model is loaded and no benchmark is executed.

Candidate results: Bash syntax PASS; ShellCheck 0.11.0 PASS with no diagnostics;
shell integration suite PASS; 29 Python regression tests PASS; Python AST syntax
checks PASS; `git diff --check` PASS. These are fixture-based results, not a real
model performance or compatibility certification.

Run from the repository root:

```bash
bash -n bin/prism-model-manager install.sh uninstall.sh tests/test.sh
shellcheck -x -P SCRIPTDIR bin/prism-model-manager install.sh uninstall.sh tests/test.sh
bash tests/test.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Coverage includes model scanning/exclusions and split shards; escaped private
configuration and profile round trips; atomic persistence; command arguments;
MTP mode/draft flag variants; missing/ambiguous projectors; invalid settings and
GGUF headers; unsupported or missing backends; occupied non-HTTP ports; process
identity and lifecycle locks; ready, failed and timed-out starts; cancelled,
invalid and successful switches; stable loaded endpoints after config edits;
no-execution dry runs; install/uninstall and retained data.

Remaining manual checks: real GGUF tensor integrity, custom backend/CUDA
compatibility, actual MTP decoding and vision responses (including their combined
operation), VRAM behavior under load, and full interactive terminal rendering.
Backend help fixtures test flag handling, not actual backend compatibility.
Very large GGUF metadata that exceeds the bounded inspector's 64 MiB limit is
rejected by preflight. No automatic recovery to the old model follows a confirmed
switch whose replacement fails during real loading.
