# Changelog

## 2.0.0 — development candidate

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
