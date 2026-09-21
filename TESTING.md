# 2.0.0 minimal-release verification

The behavioral reference is the existing working installed application, not the
experimental development branch. A source comparison confirmed that only the
configuration writer (portable backend paths), LoRA helper lookup (sibling path),
and main menu (removed launcher) differ among shared function implementations.
The external launcher function is removed. Version/help handling and generic
path defaults are packaging changes outside the inference functions.

## Results

- Bash syntax: PASS for the manager, installer, uninstaller and test runner.
- Focused release suite: PASS, 12 Python test methods (including subcases).
- Reference checks: PASS, 16 inference-related functions match the working
  reference byte-for-byte through recorded SHA-256 hashes.
- Python AST syntax and Git diff whitespace checks: PASS.
- ShellCheck: unavailable in the final minimal-release session; not installed.

Run `bash tests/test.sh`. Tests use temporary HOME and installation directories.
Backend launch, HTTP and signal commands are mocked. No inference service is
started or stopped and no model weights are loaded or modified.

Coverage includes default values, saved-root derivation, explicit backend paths,
environment precedence, empty saved paths, shell-escaped configuration and model
profiles, picker exclusions, version/help and rejected unsupported CLI options,
OFF/MTP/draft-model command construction, LoRA/vision/reasoning arguments, draft
token bounds, custom-prefix installation, overwrite refusal and data retention.

The old shell suite and metadata tests targeted the previous GitHub application,
including CLI/functions absent from the working reference. They were replaced
rather than changing inference behavior to satisfy them. The unused metadata
helper is no longer packaged. Historical screenshots are not current UI tests.

## Limits and review

These checks do not certify live CUDA inference, MTP correctness or performance,
vision responses, terminal rendering, or compatibility with every backend/model.
No new real-model inference test was performed for this minimal release.

Inherited behavior remains: switching stops the healthy model before selection;
PID tracking checks liveness without a start-time identity; startup timeout can
leave a process loading; some failures return success; missing projectors fall
back to text. These are explicit review considerations, not silently redesigned
in this release. Keep existing production state separate when reviewing.

The installed application checksum and the experimental checkout's existing diff
were unchanged during minimal-release work. No production configuration, custom
backend, model directory or running service was modified. Version 2.0.0 has
already been published. Review and explicit approval are still required
before tagging or replacing an installation.
