# Changelog

## 2.0.0 — 2026-09-21

- Package the existing working local application; preserve its model loading,
  MTP, draft-model decoding, vision, LoRA, profiles and benchmark implementation.
- Remove the TradingAgents launcher function and menu integration.
- Replace machine-specific path defaults with configurable paths resolved after
  loading configuration; save explicit server and benchmark paths.
- Add version/help entry points and retain non-overwriting installation.
- Resolve the scoring helper beside the application for custom install prefixes.
- Correct documentation and replace incompatible tests with focused release tests.
- Do not include the experimental lifecycle or backend-capability redesign.

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
