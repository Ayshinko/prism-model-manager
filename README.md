# Prism Model Manager

Interactive TUI launcher and model manager for PrismML Bonsai models and the Prism llama.cpp fork on Linux.

**Independent community project. Not affiliated with, endorsed by, or maintained by PrismML.**

Version **0.1.0**, licensed under the [MIT License](LICENSE).
Copyright (c) 2026 Ayshinko. Models and runtimes are not bundled and retain their
own licenses. [GitHub repository](https://github.com/Ayshinko/prism-model-manager).

Originally developed on **Omarchy / Arch Linux**. The launcher uses standard Linux
command-line tools and does not depend on Hyprland or an Omarchy desktop session.
Other distributions may work with the dependencies below; they have not been
validated by the maintainer.

## Features

- gum model filtering and menus; recursive GGUF discovery (including symlinks).
- Start/stop a managed server, health/status screen, configurable inference settings.
- Global configuration and individual model profiles, LoRA and optional vision projector.
- Live server log scrolling, chat smoke test, browser UI and NVIDIA VRAM monitor.
- Raw speed benchmark and bundled optional LoRA scale A/B scoring helper.
- Optional external TradingAgents launchers, disabled until paths are configured.
- GGUF metadata inspection with filename fallback, NVIDIA architecture detection,
  Ada PTQ1 advice and a launch-command dry run.

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

Open your terminal on Omarchy (or another Linux desktop), then:

```bash
git clone https://github.com/Ayshinko/prism-model-manager.git
cd prism-model-manager
./install.sh
export PATH="$HOME/.local/bin:$PATH"
```

For the first launch, point to your existing model directory and Prism runtime
(replace the two example paths):

```bash
PMM_MODEL_ROOT="$HOME/Models" \
PMM_SERVER_BIN="$HOME/path/to/prism/llama-server" \
prism-model-manager
```

The TUI saves these paths for subsequent launches with `prism-model-manager`.
To inspect a command before loading a model, use the same environment variables
with `prism-model-manager --dry-run "$HOME/Models/model.gguf"`.
No Omarchy themes, keybindings, terminal settings or system services are changed.

The default prefix is `$HOME/.local`. The installer refuses to overwrite existing
files. To review alongside an existing manager:

```bash
PREFIX="$HOME/.local/prism-model-manager-review" ./install.sh
"$HOME/.local/prism-model-manager-review/bin/prism-model-manager" --help
```

Uninstall using the same prefix and checkout:

```bash
PREFIX="$HOME/.local/prism-model-manager-review" ./uninstall.sh
```

Uninstall removes only installed files identical to this checkout. Modified files,
configuration, logs, models and runtimes are retained. Stop any managed server
before uninstalling; uninstall does not kill processes or restore older versions.

## Configuration and model directories

The default model directory is
`${XDG_DATA_HOME:-$HOME/.local/share}/prism-model-manager/models`.
Choose another directory in the TUI or set `PMM_MODEL_ROOT`. Files ending in
`.gguf` are scanned; projector, LoRA, kv-bias and dspark files are excluded.
Paths containing spaces are supported; newline-containing filenames are not.
Split GGUF shards are not automatically grouped: select the first shard.

Configuration lives in
`${XDG_CONFIG_HOME:-$HOME/.config}/prism-model-manager/config.env`.
Profiles are in its `model-profiles/` subdirectory. Logs and process identity
files are in `${XDG_STATE_HOME:-$HOME/.local/state}/prism-model-manager`.

The example is `examples/config.env.example`. Copy it manually only if no config
exists. The manager saves configuration from the TUI; CLI inspection does not save
configuration, but creates the private XDG directories. Config and profiles are
**trusted Bash files**, sourced as code: never use an untrusted downloaded config.
Saved values are shell-escaped and newly created files are private to the user.

For review without reading or modifying an existing installation's configuration:

```bash
XDG_CONFIG_HOME="$HOME/.config/pmm-review" \
XDG_STATE_HOME="$HOME/.local/state/pmm-review" \
PMM_MODEL_ROOT="$HOME/Models" \
PMM_SERVER_BIN="$HOME/path/to/prism/llama-server" \
./bin/prism-model-manager
```

Defaults: context 4096, GPU layers 99, Flash Attention on, batch 512, ubatch 128,
one parallel slot, f16 K/V cache. These are starting values, not a VRAM-fit
promise. Reduce context, batch/ubatch or GPU layers for larger models; use 0 GPU
layers for CPU. Quantized KV options are available but model/runtime support
varies. All inference settings remain editable in the TUI. Existing per-model
profiles take precedence over runtime defaults.

## Prism runtime

Install the [Prism llama.cpp fork](https://github.com/PrismML-Eng/llama.cpp)
separately, following its own instructions and license. Point `PMM_SERVER_BIN`
at the existing executable; no copy is necessary. Discovery order:

1. `PMM_SERVER_BIN`, then saved `SERVER_BIN`.
2. Under `PMM_PRISM_ROOT` / saved `PRISM_ROOT`: `build-cuda/bin/llama-server`,
   `build/bin/llama-server`, then `llama-server`.
3. `llama-server` on `PATH` (its fork identity is **not** assumed or verified).

The default root is `${XDG_DATA_HOME:-$HOME/.local/share}/prism-llama`.
`PMM_BENCH_BIN` overrides the benchmark executable; otherwise the sibling
`llama-bench` is used. `PMM_SCORE_BIN` can override the optional A/B helper.
`TRADINGAGENTS_EFFICIENT` and `TRADINGAGENTS_NORMAL` are optional config entries
for executable paths. This project does not install those integrations.

The server binds to loopback `127.0.0.1:8080` by default, without API authentication.
Only change `HOST` after configuring appropriate network access controls.

## Formats and GPU advice

| Format | Runtime guidance |
| --- | --- |
| PTQ1_0 | Prism fork required; preferred starting choice for Bonsai 2 on Ada |
| PQ2_0 | Prism fork required |
| Q2_0 | Depends on generation and layout; Bonsai 2 requires Prism fork |
| Q1_0 | Depends on runtime version and group layout; check the model card |

The inspector reads bounded GGUF v2/v3 metadata, never tensor payloads. It maps
`general.file_type` values 27/28/128/129 to these formats; missing/unsupported
metadata falls back to filename hints. It does not validate every tensor,
determine legacy group size, or certify compatibility. Other formats remain
selectable. A renamed file without useful metadata may be reported as unknown.

Bonsai 2 needs its activation transform even when Q2_0 weights appear loadable.
Older Q2_0 files can also use a legacy layout incompatible with newer builds.
See the [upstream format guide](https://github.com/PrismML-Eng/Bonsai-demo/blob/main/MODEL-FORMATS.md)
and [Bonsai 2 model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf).
Always verify the exact model and runtime version together.

GPU detection queries `nvidia-smi` compute capability and reports each GPU:
8.9 is Ada; common Ampere, Hopper, Turing and Blackwell capabilities are also
labelled. Unknown capabilities or unavailable drivers are reported without
blocking the TUI. PTQ1 advice is a starting point; actual speed depends on the
model, build and workload. Detection does not automatically change GPU selection.

## Commands and logs

```bash
prism-model-manager --scan
prism-model-manager --gpu
prism-model-manager --info "$HOME/Models/model.gguf"
prism-model-manager --dry-run "$HOME/Models/model.gguf"
prism-model-manager --logs
```

Dry-run validates paths and core numeric parameters, loads the model profile and
prints a shell-escaped command without executing it. The TUI and dry-run share
the command builder. It cannot prove CUDA availability or runtime flag support.

Server Logs uses `less +F`: it automatically follows appended lines. Press Ctrl-C
to pause following and scroll, Shift-F to resume, then Ctrl-C and q to exit.
Starting a new server replaces the previous log. The manager only stops a process
whose saved PID and Linux process start time match. An external server is not
adopted. Stop an older manager's server with that older manager before switching.

## Troubleshooting

- **Missing gum/jq/less:** install the dependencies and check `PATH`.
- **No models:** check `MODEL_ROOT`, permissions and symlink targets.
- **llama-server missing:** set an executable `PMM_SERVER_BIN`; keep the runtime's
  shared libraries beside it as required by its distribution.
- **Unknown quant type / legacy layout / gibberish:** use a matching Prism build
  and model; see the format guide, especially for Bonsai 2 and old Q2_0 files.
- **CUDA out of memory:** lower context, batch/ubatch or GPU layers; stop other
  workloads yourself. The manager does not kill unrelated GPU applications.
- **NVIDIA unavailable:** check the driver outside this app; detection failure
  does not imply no physical NVIDIA card exists.
- **Unsupported flag / cache / Flash Attention:** check your runtime's `--help`
  and adjust settings. Runtime variants are not interchangeable.
- **Port occupied:** stop the known owner or change `PORT`; unknown owners are
  not stopped automatically. A non-HTTP listener may only show in the server log.
- **Load timeout:** the server may still be loading; inspect logs/status before
  retrying. A recorded live process prevents a duplicate manager launch.

Benchmarks deliberately load models and may be expensive. They are manual actions;
the A/B benchmark uses loopback port 18080. Its small heuristic scoring suite is
not an official intelligence or safety evaluation.

## Development and verification

```bash
shellcheck -x -P SCRIPTDIR bin/prism-model-manager install.sh uninstall.sh tests/test.sh
bash tests/test.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
```

Tests use temporary HOME/XDG directories, synthetic GGUF headers and fake commands.
They cover scan filtering, config/profile round trips, command construction,
GPU fallback, log following invocation, process lifecycle and install/uninstall.
No model, live API, benchmark or GPU inference is used. Interactive terminal
rendering and actual inference need a later manual check on a working GPU host.

`.gitignore` excludes model weights, runtime binaries, configs, logs, credentials
and backups. Review staged content before publishing; ignore rules alone do not
protect already tracked files. See `TESTING.md` for this candidate's validation.
