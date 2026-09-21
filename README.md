# Prism Model Manager

> A simple TUI for loading and managing Prism/Bonsai models on Omarchy / Arch Linux.

[![Latest release](https://img.shields.io/github/release/Ayshinko/prism-model-manager/latest?label=Release&logo=github&logoColor=black&color=72af9d&borderColor=black)](https://github.com/Ayshinko/prism-model-manager/releases/latest)
[![License: MIT](https://img.shields.io/github/license/Ayshinko/prism-model-manager?logo=github&logoColor=black&color=72af9d&borderColor=black)](https://opensource.org/licenses/MIT)
[![Platform: Linux](https://img.shields.io/badge/Linux-x86_64-007ACC?logo=linux&logoColor=white&borderColor=black)](https://github.com/Ayshinko/prism-model-manager)
[![Omarchy / Arch Linux](https://img.shields.io/badge/Omarchy%2F_Arch-Linux-433F1A?color=white&borderColor=black&labelColor=433F1A)](https://github.com/omacom/omarchy)

Prism Model Manager is a terminal UI for running and managing PrismML Bonsai GGUF models with the Prism llama.cpp fork.

It handles model discovery, per-model profiles, server start/stop, inference settings, live logs, VRAM monitoring, quick chat tests and benchmarks without having to maintain long llama-server commands manually.

**Independent community project. Not affiliated with, endorsed by, or maintained by PrismML.**

<p align="center">
  <img src="assets/prism-model-manager-showcase.png" width="100%" alt="Prism Model Manager">
</p>

Version **2.0.0**, licensed under the [MIT License](LICENSE).
Copyright (c) 2026 Ayshinko. Models and runtimes are not bundled and retain their
own licenses. [GitHub repository](https://github.com/Ayshinko/prism-model-manager).

Originally developed on **Omarchy / Arch Linux**. The launcher uses standard Linux
command-line tools and does not depend on Hyprland or an Omarchy desktop session.
Other distributions may work with the dependencies below; they have not been
validated by the maintainer.

## Screenshots

Historical screenshots; some menu details differ in this minimal release.

<p align="center">
  <img src="assets/screenshots/main-menu.png" width="900" alt="Prism Model Manager main menu">
</p>

<p align="center">
  <img src="assets/screenshots/model-settings.png" width="900" alt="Prism Model Manager model settings">
</p>

<p align="center">
  <img src="assets/screenshots/model-picker.png" width="900" alt="Prism Model Manager model picker">
</p>

<p align="center">
  <img src="assets/screenshots/benchmark.png" width="900" alt="Prism Model Manager benchmark">
</p>

## What it does

- Discover and switch GGUF models
- Save individual model profiles
- Configure context, GPU layers, KV cache and sampling
- Use the existing MTP, draft-model and vision settings
- Start / stop the Prism llama.cpp server
- Follow live server logs
- Monitor NVIDIA VRAM
- Run quick chat tests
- Launch the Web UI
- Run raw speed benchmarks
- Optional LoRA configuration and A/B scoring

## Quick start

```bash
git clone https://github.com/Ayshinko/prism-model-manager.git
cd prism-model-manager
./install.sh
export PATH="$HOME/.local/bin:$PATH"
```

## Dependencies

Linux, Bash 4.4+, gum, curl, jq, less, Python 3 (standard library only), GNU
coreutils/findutils, procps-ng (`watch`), and a separately installed compatible
`llama-server`. `llama-bench` is needed only for benchmarks. `xdg-open` is optional
for the browser UI. NVIDIA monitoring requires a working driver and `nvidia-smi`.
ShellCheck is a development dependency.

On Arch Linux / Omarchy, install missing userland dependencies:

```bash
sudo pacman -S --needed git bash gum curl jq less python coreutils findutils procps-ng xdg-utils shellcheck
```

The installer does not install packages, change GPU drivers, download models, or
build/download a runtime. Run from an existing terminal; no desktop configuration
changes are required.

## Installation and removal

For the first launch, use your existing model directory and backend:

```bash
PMM_MODEL_ROOT="$HOME/Models" \
PMM_SERVER_BIN="$HOME/path/to/custom/llama-server" \
prism-model-manager
```

No runtime or model is bundled. Keep your custom build; the manager does not
replace it, rebuild it, or substitute a system backend. Installation copies the
manager and its optional LoRA scoring helper. The default prefix is `$HOME/.local`;
the installer refuses to overwrite existing files, including symlinks.

To review alongside an existing installation:

```bash
PREFIX="$HOME/.local/prism-model-manager-review" ./install.sh
"$HOME/.local/prism-model-manager-review/bin/prism-model-manager" --version
PREFIX="$HOME/.local/prism-model-manager-review" ./uninstall.sh
```

Uninstall removes only installed files identical to this checkout. It retains
modified files, configuration, profiles, logs, models and runtimes, and does not
stop servers. Neither installation nor uninstallation migrates an existing config.

## Configuration and model directories

The default model directory is `$HOME/Models`. Set it in the TUI, in `config.env`,
or with `PMM_MODEL_ROOT`. The picker scans `.gguf` files recursively, excluding
names containing `mmproj`, `dspark`, `kv-bias`, or `abliterate-lora`, and partial or
disabled filenames. Other adapter filenames are not automatically classified.
Paths with spaces work; newline-containing filenames are unsupported. For a
split model, select its first shard; the manager does not group or verify shards.

Configuration lives at `$HOME/.config/prism-model-manager/config.env`; model
profiles live in `model-profiles/` beside it. PID and log files live at
`$HOME/.local/state/prism-model-manager`. This application uses HOME, not XDG
config/state overrides. For an isolated review, set a temporary HOME:

```bash
review_home=$(mktemp -d)
HOME="$review_home" \
PMM_MODEL_ROOT="/path/to/existing/models" \
PMM_SERVER_BIN="/path/to/existing/custom/llama-server" \
./bin/prism-model-manager
```

Do not delete that HOME while a server it manages is still running. Exiting the
TUI leaves the server running. Never share state directories between unrelated
manager instances or copy a PID file from another installation.

`examples/config.env.example` is a template, not an installer action. Copy it
manually only when no config exists. Configuration and profiles are trusted Bash
files, sourced as code. Saved values are shell-escaped; created files are private.
`--help` and `--version` do not save configuration, but initialization creates its
private directories and reads an existing config.

Defaults preserve the working application's settings: context 8192, GPU layers 99,
Flash Attention on, batch/ubatch 512, one parallel slot, f16 K/V cache, temperature
1.0, top-p 0.95, top-k 20 and min-p 0. Vision, LoRA and speculative decoding start
disabled. These settings are not a promise that a model will fit in VRAM.
Existing per-model profiles take precedence when loading a model.

## Backend paths

Configuration is loaded before resolving backend paths:

1. Nonempty `PMM_SERVER_BIN` overrides saved `SERVER_BIN`.
2. A saved nonempty `SERVER_BIN` takes precedence over a derived path.
3. Otherwise use `$PRISM_ROOT/build-cuda/bin/llama-server`.

`PMM_PRISM_ROOT` overrides saved `PRISM_ROOT`; the default is `$HOME/prism-llama`.
`PMM_MODEL_ROOT` similarly overrides the saved model directory. An existing config
that sets only `PRISM_ROOT` therefore continues to select that build's CUDA server.
If `SERVER_BIN` has been saved, changing only `PRISM_ROOT` does not replace it:
update or clear `SERVER_BIN` deliberately. There is no fallback to a system binary.

Benchmark resolution follows `PMM_BENCH_BIN`, saved `BENCH_BIN`, then
`$PRISM_ROOT/build-cuda/bin/llama-bench`. Paths are saved by the TUI.
`PMM_SCORE_BIN` can override the LoRA scoring helper; otherwise the sibling
`prism-lora-ab-score.py` is used, including with a custom install prefix.

The default API is `http://127.0.0.1:8080/v1`, without authentication configured by
the manager. Configure appropriate access controls before changing the bind host.
Model, quantization and runtime compatibility remain the backend's responsibility.
There is no backend-help gate or automatic metadata compatibility certification.

## MTP, draft models and vision

The existing per-model settings and arguments are preserved:

- **OFF:** no speculative decoding arguments.
- **MTP:** `--spec-type draft-mtp --spec-draft-n-max N`; an optional draft path adds
  `--spec-draft-model PATH`.
- **Draft Model:** `--spec-type draft-simple --spec-draft-model PATH
  --spec-draft-n-max N`; a draft file is required.

`SPEC_MODE`, `SPEC_DRAFT_MODEL` and `SPEC_DRAFT_TOKENS` are saved in model profiles.
The existing draft-token validation accepts integers 1 through 8. Select a mode
supported by your custom backend and model. This release does not infer alternate
flag names or change the installed application's decoding implementation.

Vision uses the first adjacent `*mmproj*.gguf`. If none is found, the existing
behavior warns and starts text-only. LoRA, reasoning budget, context, cache and
sampling settings remain available. This release does not certify MTP/vision
compatibility or claim an inference speedup.

## Commands and logs

```bash
prism-model-manager             # interactive TUI
prism-model-manager --version   # 2.0.0; alias -V
prism-model-manager --help      # alias -h
```

These are the only CLI options. Discovery, settings, status, chat, Web UI, VRAM
monitoring, benchmarks, logs and stopping a model are TUI actions.
Server Logs uses `less +F`: Ctrl-C pauses following; Shift-F resumes; q exits
when following is paused. Starting a server replaces its previous log.

## Troubleshooting and inherited limitations

- Missing backend: set `PMM_SERVER_BIN` or `SERVER_BIN` to your compatible custom
  executable and keep its required shared libraries available.
- No models: check the model directory, permissions and symlink targets.
- Unsupported arguments or out-of-memory errors: inspect the backend log and
  adjust the existing model settings. No drivers or other workloads are changed.
- Switching preserves the original flow: it stops a healthy model before opening
  the picker. Cancelling does not automatically reload it.
- Process tracking uses a saved PID and liveness check, not a process-start identity.
  Stale PID files and shared state require care; lifecycle hardening is outside
  this minimal release.
- Occupied ports are checked using HTTP health. A non-HTTP listener may only cause
  an error in the backend log. A timeout may leave the backend loading; inspect
  status and logs before retrying. Some original failure paths return success.

Benchmarks load models and consume GPU resources. The LoRA A/B benchmark uses
loopback port 18080 and its own text/LoRA arguments. Its heuristic scores are not
an official intelligence or safety evaluation. The original LM Studio-related
external launcher was part of the removed integration; no separate inference
backend was replaced or reconfigured.

## Development and verification

```bash
bash -n bin/prism-model-manager install.sh uninstall.sh tests/test.sh
shellcheck -x -P SCRIPTDIR bin/prism-model-manager install.sh uninstall.sh tests/test.sh
bash tests/test.sh
```

The focused release tests use temporary HOME and install prefixes. Backend launch,
HTTP and process commands are mocked; they do not load models or signal services.
They check configuration precedence, CLI behavior, profiles, discovery, exact
inference arguments, installation and preserved reference-function hashes.
The former tests targeted a different implementation and have been replaced;
unsupported CLI features were not added to satisfy them. See `TESTING.md` for
actual results and remaining limits. Review staged content before publication;
ignore rules cannot protect private files already tracked by Git.
