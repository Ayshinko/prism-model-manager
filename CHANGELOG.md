# Changelog

## 3.0.0 — 2026-09-22

- Default MTP mode to `draft-mtp` (maps to `--spec-type draft-mtp`) and validate
  the selected mode against the backend's advertised `--spec-type` values, plus
  modern speculative-draft flags, instead of trusting free-text settings.
- Parse `llama-server --help` (including aliases, boolean flags, wrapped
  descriptions, ANSI output and removed options) to decide advertised
  capabilities; refuse options or draft flags the backend marks as removed.
  Handle composite usage forms such as `--override-tensor
  <tensor name pattern>=<buffer type>,...` and `-hf [<repo>/]<model>[:quant]`.
- Add embedded-MTP migration for legacy `SPEC_MODE`, `SPEC_DRAFT_MODEL` and
  `SPEC_DRAFT_TOKENS` environment variables, only when the corresponding
  canonical config value was not saved explicitly. Embedded MTP uses no
  sidecar/draft model; a migrated `SPEC_DRAFT_MODEL` emits a warning and keeps
  embedded MTP.
- Support automatic vision selection: empty `MMPROJ_PATH` uses `--mmproj-auto`
  when the backend advertises it, and falls back to a single adjacent
  `*mmproj*.gguf`; an explicit path uses `--mmproj FILE`. Missing or ambiguous
  projectors still block startup.
- Add session-only backend override via `PMM_SERVER_BIN` (and `PMM_MODEL_ROOT`,
  `PMM_PRISM_ROOT`, `PMM_BENCH_BIN`), tracked as session state so it is not
  persisted over an explicitly saved config value; `--state` reports the current
  runtime state and `--clear-state` removes stale state.
- Rewrite preflight to validate executable, model file, inference settings and
  shard completeness before launching, and to resolve backend capabilities from
  the parsed help table rather than regex over raw text.
- Add `--api-ready` (reports API base URL, reachability, model id; exits nonzero
  when unreachable) and `--check` validating the saved selection without launch.
- Track config provenance (which settings were saved vs. environment-provided)
  so migrations and session overrides never overwrite explicit user values.

## 2.0.0 — 2026-09-21

- Validate inference settings and backend help before loading; provide explicit
  errors for missing models/backends, unsupported options and occupied ports.
- Select and preflight a replacement model before confirming a managed shutdown;
  serialize lifecycle changes and recheck process identity before signals.
- Record boot identity and the loaded model/API endpoint, distinguish managed and
  external status, and clean up failed or timed-out launches.
- Add persisted MTP mode/draft controls and explicit vision projector selection;
  reject missing/ambiguous projectors instead of silently falling back to text.
- Correct GGUF file-type interpretation, expose architecture/name/context metadata,
  and validate numbered shard sets while listing only their first shard.
- Display NVIDIA memory/utilization and system RAM snapshots; retain existing
  inference, LoRA, chat, log and benchmark functionality.
- Save profiles/configuration atomically, keep settings available before first
  model selection, and target chat requests at the actual API model ID.
- Add isolated regression coverage for lifecycle, configuration, MTP/vision,
  ports, backend errors, discovery and metadata. Real CUDA inference is not
  certified by these tests. No backend replacement or final release tag.

## 0.1.0 — 2026-09-18

- Package the existing Bash/gum model manager as an independent community project.
- Preserve model selection, per-model profiles, server lifecycle, chat, Web UI,
  VRAM monitoring, benchmarks and live logs.
- Replace machine-specific defaults with XDG paths, environment overrides and
  runtime discovery; keep installation non-destructive.
- Add format compatibility hints, NVIDIA architecture detection and Ada advice.
- Add dry-run command construction, isolated tests and distribution documentation.
- Adopt the MIT License, copyright 2026 Ayshinko.
- Document Omarchy / Arch Linux installation and first-launch configuration.
