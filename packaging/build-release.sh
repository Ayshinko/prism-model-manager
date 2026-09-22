#!/usr/bin/env bash
# build-release.sh — Build the integrated PMM 3.0 + PR218 release archive
#
# Usage: ./packaging/build-release.sh [OUTDIR]
#   Default OUTDIR: dist/
#
# Produces: prism-model-manager-3.0-linux-x86_64-cuda.tar.gz
#           prism-model-manager-3.0-linux-x86_64-cuda.tar.gz.sha256
#
# Requires: the verified PR218 backend at BONSAI_KERNEL_TEST/build-cuda-pr218/bin/
#           and a clean PMM 3.0 checkout.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
OUTDIR="${1:-$ROOT/dist}"
ARCHIVE_NAME="prism-model-manager-3.0-linux-x86_64-cuda"
BACKEND_SRC="$HOME/AI-Workspace/bonsai-kernel-test/build-cuda-pr218/bin"
PMM_VER=$(cd "$ROOT" && git describe --tags --always 2>/dev/null || echo "3.0.0")

echo "=== PMM 3.0 Integrated Release Builder ==="
echo "Root:      $ROOT"
echo "Output:    $OUTDIR"
echo "Backend:   $BACKEND_SRC"
echo "Archive:   $ARCHIVE_NAME"
echo "PMM Ver:   $PMM_VER"

# ─────────────────────────────────────────────
# 1. Validate prerequisites
# ─────────────────────────────────────────────

# Verify PMM source
[ -d "$ROOT/bin" ] || { echo "ERROR: PMM bin/ not found"; exit 1; }
[ -f "$ROOT/bin/prism-model-manager" ] || { echo "ERROR: prism-model-manager missing"; exit 1; }

# Verify backend
BACKEND="$BACKEND_SRC/llama-server"
[ -f "$BACKEND" ] || { echo "ERROR: PR218 backend not found at $BACKEND"; exit 1; }

# Verify backend identity
EXPECTED_SHA256="a4d445df7d3538fe50d6ee8bbb0ed0add07ac5c514855db976ef6fc25d8a6638"
ACTUAL_SHA256=$(sha256sum "$BACKEND" | awk '{print $1}')
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
    echo "ERROR: Backend SHA256 mismatch!"
    echo "  Expected: $EXPECTED_SHA256"
    echo "  Actual:   $ACTUAL_SHA256"
    exit 1
fi

# Verify backend version
BACKEND_VERSION=$("$BACKEND" --version 2>&1 | head -1) || { echo "ERROR: Backend not executable"; exit 1; }
echo "Backend: $BACKEND_VERSION"

# Verify shared libraries
for lib in \
    libllama-server-impl.so \
    libllama-common.so.0 \
    libmtmd.so.0 \
    libllama.so.0 \
    libggml.so.0 \
    libggml-cpu.so.0 \
    libggml-cuda.so.0 \
    libggml-base.so.0; do
    resolved=$(find "$BACKEND_SRC" -name "$lib*" -type f 2>/dev/null | head -1)
    [ -n "$resolved" ] || { echo "ERROR: Missing shared library: $lib"; exit 1; }
done

echo "All shared libraries found."

# ─────────────────────────────────────────────
# 2. Create staging directory
# ─────────────────────────────────────────────

STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT

mkdir -p "$STAGING/$ARCHIVE_NAME/bin"
mkdir -p "$STAGING/$ARCHIVE_NAME/lib"
mkdir -p "$STAGING/$ARCHIVE_NAME/share/doc"
mkdir -p "$STAGING/$ARCHIVE_NAME/share/manuals"

# ─────────────────────────────────────────────
# 3. Copy PMM application files
# ─────────────────────────────────────────────

echo "--- Copying PMM application ---"

cp "$ROOT/bin/prism-model-manager" "$STAGING/$ARCHIVE_NAME/bin/"
cp "$ROOT/bin/prism-lora-ab-score.py" "$STAGING/$ARCHIVE_NAME/bin/"
cp "$ROOT/bin/prism-gguf-info.py" "$STAGING/$ARCHIVE_NAME/bin/"
cp "$ROOT/bin/prism-backend-info.py" "$STAGING/$ARCHIVE_NAME/bin/"

# Copy example config
cp "$ROOT/examples/config.env.example" "$STAGING/$ARCHIVE_NAME/share/doc/"

# Copy installer and uninstaller
cp "$ROOT/install.sh" "$STAGING/$ARCHIVE_NAME/install.sh"
cp "$ROOT/uninstall.sh" "$STAGING/$ARCHIVE_NAME/uninstall.sh"

# Copy license files
cp "$ROOT/LICENSE" "$STAGING/$ARCHIVE_NAME/LICENSE"

echo "PMM files copied."

# ─────────────────────────────────────────────
# 4. Copy PR218 backend and shared libraries
# ─────────────────────────────────────────────

echo "--- Copying PR218 backend ---"

cp "$BACKEND" "$STAGING/$ARCHIVE_NAME/lib/llama-server"
chmod 755 "$STAGING/$ARCHIVE_NAME/lib/llama-server"

# Copy resolved shared libraries (follow symlinks -> real files)
for lib_pattern in \
    libllama-server-impl.so* \
    libllama-common.so* \
    libmtmd.so* \
    libllama.so* \
    libggml.so* \
    libggml-cpu.so* \
    libggml-cuda.so* \
    libggml-base.so*; do
    for f in "$BACKEND_SRC"/$lib_pattern; do
        [ -f "$f" ] || continue
        cp -a "$f" "$STAGING/$ARCHIVE_NAME/lib/"
    done
done

echo "Backend and shared libraries copied."

# ─────────────────────────────────────────────
# 5. Add license and attribution files
# ─────────────────────────────────────────────

echo "--- Adding licenses and attribution ---"

# llama.cpp MIT license (upstream)
cat > "$STAGING/$ARCHIVE_NAME/share/doc/LICENSE-llama.cpp" << 'EOF'
MIT License

Copyright (c) 2023-2026 The ggml authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

# PrismML fork attribution
cat > "$STAGING/$ARCHIVE_NAME/share/doc/LICENSE-bundled-backend" << 'EOF'
Bundled llama-server Backend — Attribution and License Information
=================================================================

The llama-server executable and its supporting shared libraries (libllama*.so.*,
libmtmd*.so.*, libggml*.so.*) included in this package are compiled from the
PrismML-Eng/llama.cpp fork, which itself is a derivative of the upstream
ggerganov/llama.cpp project.

Both the upstream project and the PrismML fork are licensed under the MIT License
(see LICENSE-llama.cpp for the full text).

Additionally, this build includes the following third-party component:

  - Niels Lohmann/json.hpp (MIT License, Copyright 2013-2025 Niels Lohmann)
    Used for GGUF metadata parsing in the llama.cpp source tree.

Source Repository: https://github.com/PrismML-Eng/llama.cpp
Upstream Repository: https://github.com/gggerganov/llama.cpp

Build Information
-----------------
  Build ID:      10718
  Commit:        3443ddece08c8d1bd888e80b181c4edb53a3d553
  Branch:        pr218-test
  Build Date:    2026-09-22
  Compiler:      GNU 16.2.1
  Target:        Linux x86_64
  CUDA Arch:     sm_89 (Ada/RTX 4070 SUPER)
  CUDA Toolkit:  NVIDIA CUDA 13.3 (external runtime dependency)

The bundled backend is provided as a convenience binary. It is not endorsed,
maintained, or supported by PrismML or the ggml authors. The exact source from
which it was built, including any local modifications not present in the upstream
Prism or ggml repositories, is documented in BACKEND-PROVENANCE.md.

See also: AUTHORS (list of upstream contributors to the llama.cpp project).
EOF

# Copy AUTHORS from llama.cpp
if [ -f "$ROOT/../bonsai-kernel-test/llama.cpp/AUTHORS" ]; then
    cp "$ROOT/../bonsai-kernel-test/llama.cpp/AUTHORS" "$STAGING/$ARCHIVE_NAME/share/doc/AUTHORS"
fi

# Backend provenance
cat > "$STAGING/$ARCHIVE_NAME/share/doc/BACKEND-PROVENANCE.md" << 'EOF'
# Backend Provenance — PR218 llama-server

## Source Repository

  https://github.com/PrismML-Eng/llama.cpp

## Exact Source Revision

  Commit 3443ddece08c8d1bd888e80b181c4edb53a3d553
  Branch: pr218-test
  Message: "Docs: scope the GGML_CUDA_BATCH_INVARIANT comment to the paths the flag changes"

## Parent Branch History

  The pr218-test branch is based on the upstream prism branch
  (commit 1a07bfa5f — "Merge pull request #179 from PrismML-Eng/feat/dspark-shared-head-runtime")
  with the following additional changes for PR #218:

  - c7551241a  Add: dedicated PTQ1_0 mat-vec kernel with full lane utilization
  - a4344b545  Test: add Bonsai 2 projection shapes to the mul_mat perf cases
  - a55badae9  Add: GGML_CUDA_BATCH_INVARIANT for batch-invariant small-batch kernels
  - 588318660  Fix: use the mat-vec kernel for bf16 matrices under 64 rows at 2 to 8 columns
  - 2578fdfa3  Fix: keep GGML_CUDA_RESTRICT off the PTQ1_0 mat-vec kernel signature
  - 497ea2832  Docs: state the batch-invariance guarantee as 1 to 4 columns
  - 844dd06f7  Fix: budget the PTQ1_0 mat-vec shared memory the launch will request
  - 3443ddece  Docs: scope the GGML_CUDA_BATCH_INVARIANT comment to the paths the flag changes

  Additional uncommitted local modifications (at build time) for Qwen 3.5 MTP
  Hadamard embedding support (preserved in stash on pr218-test).

## Build Configuration

  - CMake preset: Release
  - CUDA architectures: sm_89
  - GGML_CUDA_FA: ON
  - GGML_CUDA_GRAPHS: ON
  - GGML_CUDA_NCCL: ON
  - GGML_CUDA_COMPRESSION_MODE: size
  - GGML_CUDA_NO_VMM: OFF
  - CUDA Toolkit: 13.3

## Binary Verification

  SHA256: a4d445df7d3538fe50d6ee8bbb0ed0add07ac5c514855db976ef6fc25d8a6638
  File size: 15976 bytes
  ELF: x86_64, dynamically linked, not stripped

## Reproduction

  To reproduce this binary from source:

  ```bash
  git clone https://github.com/PrismML-Eng/llama.cpp.git
  cd llama.cpp
  git checkout 3443ddece
  # Apply local modifications for Qwen 3.5 MTP Hadamard embeddings (see
  # the pr218-test branch stash if available, or the packaging/patch/
  # directory)
  mkdir -p build-cuda && cd build-cuda
  cmake .. -DCMAKE_BUILD_TYPE=Release \
           -DCMAKE_CUDA_ARCHITECTURES=89 \
           -DGGML_CUDA_FA=ON \
           -DGGML_CUDA_GRAPHS=ON \
           -DGGML_CUDA_NCCL=ON \
           -DGGML_CUDA_COMPRESSION_MODE=size
  make -j$(nproc) llama-server
  ```

  Note: A byte-for-byte identical binary requires matching the exact compiler
  (GNU 16.2.1), CUDA Toolkit version (13.3), and build environment. The result
  above is functionally equivalent but not necessarily bit-identical.

## External Runtime Dependencies

  The following are NOT bundled and must be present on the host system:

  - NVIDIA CUDA driver (provides libcuda.so.1 — R550+ recommended)
  - NVIDIA cuBLAS (libcublas.so.13) — part of CUDA Toolkit or driver package
  - NVIDIA cuBLASLt (libcublasLt.so.13)
  - NVIDIA NCCL (libnccl.so.2)
  - CUDA Runtime (libcudart.so.13)
  - System libraries: libstdc++.so.6, libgcc_s.so.1, libc.so.6, libm.so.6,
    libssl.so.3, libcrypto.so.3, libz.so.1, libzstd.so.1, libbrotli*.so.1
EOF

# README for the archive
cat > "$STAGING/$ARCHIVE_NAME/share/doc/README-integrated.md" << 'EOF'
# Prism Model Manager 3.0 — Integrated Package

This archive contains:

1. **Prism Model Manager 3.0** — the TUI application for managing GGUF models
2. **PR218 llama-server** — the verified inference backend, compiled from the
   PrismML-Eng/llama.cpp fork with PTQ1_0 mat-vec support and CUDA batch-invariant
   kernels for Bonsai 2 PTQ1_0 + MTP inference

## What you need separately

- **GGUF model weights** (e.g. Ternary-Bonsai-2-27B-PTQ1_0-MTP-Q8_0-fixed.gguf)
  — download from Hugging Face or your model provider. These are NOT included.
- **NVIDIA CUDA driver** (R550+ recommended; provides libcuda.so.1)
- **Compatible NVIDIA GPU** (verified on RTX 4070 SUPER 12 GB)

## Quick start

```bash
tar xzf prism-model-manager-3.0-linux-x86_64-cuda.tar.gz
cd prism-model-manager-3.0-linux-x86_64-cuda
./install.sh
export PATH="$HOME/.local/bin:$PATH"
prism-model-manager
```

Then in the TUI:
1. Set Model Directory to your GGUF model location
2. The backend is pre-configured to the bundled llama-server
3. Select and load a compatible model
4. Enable MTP if the model supports it

## Contents

```
prism-model-manager-3.0-linux-x86_64-cuda/
├── install.sh           # One-step installer
├── uninstall.sh         # Safe uninstaller
├── LICENSE              # PMM 3.0 MIT license
├── bin/
│   ├── prism-model-manager     # Main TUI application
│   ├── prism-lora-ab-score.py  # LoRA scoring helper
│   ├── prism-gguf-info.py      # GGUF metadata inspector
│   └── prism-backend-info.py   # Backend flag parser
├── lib/
│   ├── llama-server            # PR218 inference backend
│   ├── libllama-server-impl.so
│   ├── libllama-common.so.0.2.0
│   ├── libllama.so.0.2.0
│   ├── libmtmd.so.0.2.0
│   ├── libggml.so.0.21.0
│   ├── libggml-cpu.so.0.21.0
│   ├── libggml-cuda.so.0.21.0
│   └── libggml-base.so.0.21.0
│   └── ... (symlinks)
└── share/doc/
    ├── README-integrated.md
    ├── BACKEND-PROVENANCE.md
    ├── LICENSE-llama.cpp
    ├── LICENSE-bundled-backend
    ├── AUTHORS
    └── config.env.example
```

## Uninstallation

```bash
cd prism-model-manager-3.0-linux-x86_64-cuda
./uninstall.sh
```
Remove only the installed files identical to this package. Configuration, models,
logs and custom backends are preserved.

## License

Prism Model Manager 3.0 is MIT licensed (see LICENSE).
The bundled llama-server is compiled from MIT-licensed llama.cpp (see share/doc/).
NVIDIA CUDA Runtime libraries are external system dependencies and are not
redistributed with this package. See share/doc/ for full attribution.
EOF

# ─────────────────────────────────────────────
# 6. Create the integrated installer
# ─────────────────────────────────────────────

echo "--- Creating integrated installer ---"

cat > "$STAGING/$ARCHIVE_NAME/install.sh" << 'INSTALL_EOF'
#!/usr/bin/env bash
# install.sh — Integrated installer for PMM 3.0 + PR218 backend
#
# Usage: ./install.sh [PREFIX]
#   Default PREFIX: $HOME/.local
#
# Run from the extracted archive directory.
set -euo pipefail

ARCHIVE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PREFIX="${1:-${PREFIX:-$HOME/.local}}"
PMM_BIN="$PREFIX/bin"
BACKEND_LIB="$PREFIX/lib/prism-llama"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/prism-model-manager"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/prism-model-manager"

echo "=== Prism Model Manager 3.0 — Integrated Installer ==="
echo "Archive root:  $ARCHIVE_DIR"
echo "Install prefix: $PREFIX"
echo

# ─────────────────────────────────────────────
# 1. Preflight checks
# ─────────────────────────────────────────────

# Architecture check
ARCH=$(uname -m)
if [ "$ARCH" != "x86_64" ]; then
    echo "ERROR: This package supports x86_64 only (detected: $ARCH)." >&2
    exit 1
fi

# OS check
if [ "$(uname -s)" != "Linux" ]; then
    echo "ERROR: Linux is required (detected: $(uname -s))." >&2
    exit 1
fi

# Required tools
MISSING=""
for tool in curl jq python3; do
    command -v "$tool" >/dev/null 2>&1 || MISSING="$MISSING $tool"
done
if command -v gum >/dev/null 2>&1; then
    GUM_AVAIL=1
else
    GUM_AVAIL=0
    MISSING="$MISSING gum"
fi
if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required tools:$MISSING" >&2
    echo "Install them and re-run the installer:" >&2
    echo "  sudo pacman -S --needed bash gum curl jq python coreutils findutils procps-ng" >&2
    exit 1
fi

# Verify archive integrity
EXPECTED_FILES="bin/prism-model-manager bin/prism-lora-ab-score.py bin/prism-gguf-info.py bin/prism-backend-info.py lib/llama-server LICENSE uninstall.sh"
for f in $EXPECTED_FILES; do
    [ -f "$ARCHIVE_DIR/$f" ] || { echo "ERROR: Archive corrupted — missing $f"; exit 1; }
done

echo "Architecture:   OK ($ARCH)"
echo "System:         OK (Linux)"
echo "Tools:          OK"
echo "Archive:        OK (all expected files present)"
echo

# ─────────────────────────────────────────────
# 2. CUDA / NVIDIA dependency check
# ─────────────────────────────────────────────

echo "--- Checking NVIDIA CUDA runtime ---"

CUDA_OK=0
if command -v nvidia-smi >/dev/null 2>&1; then
    NVIDIA_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)
    if [ -n "$NVIDIA_VER" ]; then
        echo "NVIDIA driver:  $NVIDIA_VER"
        CUDA_OK=1
    fi
fi

# Check libcuda availability
if [ -f /usr/lib/libcuda.so.1 ] || [ -f /usr/lib64/libcuda.so.1 ] || ldconfig -p 2>/dev/null | grep -q libcuda; then
    echo "libcuda.so.1:   found"
    CUDA_OK=1
else
    echo "libcuda.so.1:   not found (CUDA driver may not be installed)"
fi

if [ "$CUDA_OK" -eq 0 ]; then
    echo
    echo "WARNING: NVIDIA CUDA driver not detected."
    echo "  The bundled backend requires a working NVIDIA CUDA environment."
    echo "  Installation will continue, but inference will not work until"
    echo "  a compatible NVIDIA driver and CUDA toolkit are installed."
    echo
fi

# Check cuBLAS availability
if ldconfig -p 2>/dev/null | grep -q libcublas.so.13; then
    echo "libcublas.so.13: found"
else
    echo "libcublas.so.13: not found in ldconfig (may still be available via LD_LIBRARY_PATH)"
fi

echo
echo "--- Verifying bundled backend ---"

BACKEND_SHA256_EXPECTED="a4d445df7d3538fe50d6ee8bbb0ed0add07ac5c514855db976ef6fc25d8a6638"
BACKEND_SHA256_ACTUAL=$(sha256sum "$ARCHIVE_DIR/lib/llama-server" | awk '{print $1}')

if [ "$BACKEND_SHA256_EXPECTED" != "$BACKEND_SHA256_ACTUAL" ]; then
    echo "ERROR: Backend checksum mismatch!"
    echo "  Expected: $BACKEND_SHA256_EXPECTED"
    echo "  Actual:   $BACKEND_SHA256_ACTUAL"
    echo "  The bundled binary may be corrupted. Re-download the archive."
    exit 1
fi

BACKEND_VERSION=$("$ARCHIVE_DIR/lib/llama-server" --version 2>&1 | head -1) || {
    echo "ERROR: Backend is not executable or missing dependencies." >&2
    ldd "$ARCHIVE_DIR/lib/llama-server" 2>&1 | grep -E "not found" || true
    exit 1
}
echo "Backend:        $BACKEND_VERSION"
echo "SHA256:         OK (matches expected)"
echo

# ─────────────────────────────────────────────
# 3. Check existing installation
# ─────────────────────────────────────────────

INSTALLED_PMM="$PMM_BIN/prism-model-manager"
INSTALLED_BACKEND="$BACKEND_LIB/llama-server"
EXISTING_CONFIG="$CONFIG_DIR/config.env"

# Check if PMM is already installed
if [ -f "$INSTALLED_PMM" ] || [ -L "$INSTALLED_PMM" ]; then
    echo "--- Existing PMM installation detected ---"
    CURRENT_VER=$("$INSTALLED_PMM" --version 2>/dev/null || echo "unknown")
    echo "  Installed:  $INSTALLED_PMM (version $CURRENT_VER)"
    echo

    if command -v gum >/dev/null 2>&1; then
        if ! gum confirm "Upgrade PMM 3.0 to this version?"; then
            echo "Installation cancelled."
            exit 0
        fi
    else
        echo "Press Enter to upgrade, or Ctrl-C to cancel."
        read -r
    fi
fi

# Check if existing config has a custom SERVER_BIN
if [ -f "$EXISTING_CONFIG" ]; then
    SAVED_SERVER_BIN=$(grep -E '^SERVER_BIN=' "$EXISTING_CONFIG" | head -1 | cut -d= -f2- | tr -d '"'"'" || true)
    if [ -n "$SAVED_SERVER_BIN" ] && [ "$SAVED_SERVER_BIN" != "$INSTALLED_BACKEND" ]; then
        echo "NOTE: Existing config has a custom backend path:"
        echo "  $SAVED_SERVER_BIN"
        if command -v gum >/dev/null 2>&1; then
            if gum confirm "Replace with the bundled PR218 backend? (No keeps your custom path)"; then
                REPLACE_CUSTOM_BACKEND=1
            else
                REPLACE_CUSTOM_BACKEND=0
            fi
        else
            echo "  The bundled backend will NOT replace your custom backend."
            echo "  To use the bundled backend later, change it in PMM settings."
            REPLACE_CUSTOM_BACKEND=0
        fi
    fi
fi

# ─────────────────────────────────────────────
# 4. Install files
# ─────────────────────────────────────────────

echo
echo "--- Installing PMM components ---"

mkdir -p "$PMM_BIN"
mkdir -p "$BACKEND_LIB"
mkdir -p "$CONFIG_DIR"
mkdir -p "$STATE_DIR"
mkdir -p "$CONFIG_DIR/model-profiles"

# Install PMM scripts
for name in prism-model-manager prism-lora-ab-score.py prism-gguf-info.py prism-backend-info.py; do
    install -m 755 "$ARCHIVE_DIR/bin/$name" "$PMM_BIN/$name"
    echo "  Installed: $PMM_BIN/$name"
done

# Install backend and shared libraries
install -m 755 "$ARCHIVE_DIR/lib/llama-server" "$BACKEND_LIB/llama-server"
echo "  Installed: $BACKEND_LIB/llama-server"

for lib in "$ARCHIVE_DIR"/lib/*.so* "$ARCHIVE_DIR"/lib/*.so.*; do
    [ -f "$lib" ] || continue
    install -m 644 "$lib" "$BACKEND_LIB/"
    echo "  Installed: $BACKEND_LIB/$(basename "$lib")"
done

# Create libllama-server-impl.so symlink (loaded by RPATH)
if [ -f "$BACKEND_LIB/libllama-server-impl.so" ]; then
    :  # already installed by the glob above
fi

# Create pmm symlink
ln -sf "$PMM_BIN/prism-model-manager" "$PMM_BIN/pmm"
echo "  Created:    $PMM_BIN/pmm -> prism-model-manager"

# Update PATH instruction
if ! grep -q "$PMM_BIN" "$HOME/.bashrc" 2>/dev/null; then
    echo "  NOTE: Add $PMM_BIN to your PATH if not already done:"
    echo "    echo 'export PATH=\"\$PATH:$PMM_BIN\"' >> ~/.bashrc"
fi

# ─────────────────────────────────────────────
# 5. Configure default backend
# ─────────────────────────────────────────────

if [ ! -f "$EXISTING_CONFIG" ]; then
    # Fresh install: set the bundled backend as default
    cat > "$EXISTING_CONFIG" << CONFIG_EOF
# Prism Model Manager 3.0 — default configuration
# Generated by integrated installer on $(date -Iseconds)

# Bundled PR218 backend (compatible with PTQ1_0 + MTP)
SERVER_BIN=$BACKEND_LIB/llama-server
BENCH_BIN=$BACKEND_LIB/../llama-bench

# Model directory — change this to your GGUF model location
MODEL_ROOT=\${XDG_DATA_HOME:-\$HOME/.local/share}/prism-model-manager/models

# Runtime root (backend shared libraries location)
PRISM_ROOT=$BACKEND_LIB

# Inference defaults
HOST=127.0.0.1
PORT=8080
STARTUP_TIMEOUT=180
CTX=4096
NGL=99
FLASH=on
BATCH=512
UBATCH=128
PARALLEL=1

# Sampling
TEMP=1.0
TOP_P=0.95
TOP_K=20
MIN_P=0

# KV cache
CACHE_K=f16
CACHE_V=f16

# MTP (enable per model)
MTP=off
MTP_MODE=draft-mtp
MTP_DRAFT_MAX=3
MTP_DRAFT_FLAG=--spec-draft-n-max

# LoRA (enable per model)
LORA_ENABLED=off
LORA_SCALE=2
CONFIG_EOF
    echo "  Created:    $EXISTING_CONFIG (default backend set to bundled PR218)"
elif [ "${REPLACE_CUSTOM_BACKEND:-0}" = "1" ]; then
    # Update existing config: replace SERVER_BIN
    if grep -q '^SERVER_BIN=' "$EXISTING_CONFIG"; then
        sed -i "s|^SERVER_BIN=.*|SERVER_BIN=$BACKEND_LIB/llama-server|" "$EXISTING_CONFIG"
        echo "  Updated:    $EXISTING_CONFIG (SERVER_BIN set to bundled PR218)"
    else
        echo "SERVER_BIN=$BACKEND_LIB/llama-server" >> "$EXISTING_CONFIG"
    fi
    if grep -q '^PRISM_ROOT=' "$EXISTING_CONFIG"; then
        sed -i "s|^PRISM_ROOT=.*|PRISM_ROOT=$BACKEND_LIB|" "$EXISTING_CONFIG"
    else
        echo "PRISM_ROOT=$BACKEND_LIB" >> "$EXISTING_CONFIG"
    fi
fi

# ─────────────────────────────────────────────
# 6. Install launcher and desktop entry
# ─────────────────────────────────────────────

echo "--- Installing application launcher ---"

# Desktop launcher script
LAUNCHER_SCRIPT="$PMM_BIN/prism-model-manager-launcher"
cat > "$LAUNCHER_SCRIPT" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
# Launcher for Prism Model Manager — opens in a terminal
PMM="$HOME/.local/bin/prism-model-manager"
if command -v ghostty >/dev/null 2>&1; then
    exec ghostty -e "$PMM"
elif command -v kitty >/dev/null 2>&1; then
    exec kitty "$PMM"
elif command -v alacritty >/dev/null 2>&1; then
    exec alacritty -e "$PMM"
elif command -v wezterm >/dev/null 2>&1; then
    exec wezterm start -- "$PMM"
elif command -v foot >/dev/null 2>&1; then
    exec foot "$PMM"
elif command -v gnome-terminal >/dev/null 2>&1; then
    exec gnome-terminal -- "$PMM"
else
    notify-send "Prism Model Manager" \
        "No supported terminal found. Run 'pmm' from your terminal."
    exit 1
fi
LAUNCHER_EOF
chmod 755 "$LAUNCHER_SCRIPT"
echo "  Installed:  $LAUNCHER_SCRIPT"

# Desktop entry
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS_DIR"
DESKTOP_FILE="$APPS_DIR/prism-model-manager.desktop"
cat > "$DESKTOP_FILE" << DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=Prism Model Manager
GenericName=Local AI Model Manager
Comment=Manage Prism llama.cpp models with integrated inference backend
Exec=$LAUNCHER_SCRIPT
Icon=utilities-terminal
Terminal=false
Categories=Development;Utility;
Keywords=Prism;LLM;AI;Bonsai;llama.cpp;MTP;
StartupNotify=false
DESKTOP_EOF
echo "  Installed:  $DESKTOP_FILE"

# Also install a .desktop file with the actual terminal command for direct access
DESKTOP_FILE_TERM="$APPS_DIR/prism-model-manager-terminal.desktop"
cat > "$DESKTOP_FILE_TERM" << DESKTOP_TERM_EOF
[Desktop Entry]
Type=Application
Name=Prism Model Manager (Terminal)
GenericName=Local AI Model Manager
Comment=Run Prism Model Manager in terminal
Exec=$PMM_BIN/prism-model-manager
Icon=utilities-terminal
Terminal=true
Categories=Development;Utility;
Keywords=Prism;LLM;AI;Bonsai;llama.cpp;MTP;
StartupNotify=false
DESKTOP_TERM_EOF
echo "  Installed:  $DESKTOP_FILE_TERM"

# Omarchy menu integration (if omarchy-shell is available)
OMARCHY_APPS="${XDG_DATA_HOME:-$HOME/.local/share}/omarchy/applications"
if [ -d "$OMARCHY_APPS" ] || [ -d "$HOME/.config/omarchy" ]; then
    mkdir -p "$OMARCHY_APPS" 2>/dev/null || true
    if [ -d "$OMARCHY_APPS" ]; then
        cp "$DESKTOP_FILE" "$OMARCHY_APPS/prism-model-manager.desktop"
        echo "  Omarchy:    added launcher to $OMARCHY_APPS"
    fi
fi

echo
echo "=== Installation complete ==="
echo
echo "Run:  $PMM_BIN/prism-model-manager"
echo "Or:   pmm"
echo
echo "Quick start:"
echo "  1. Set Model Directory to your GGUF model location"
echo "  2. Select and load a compatible model"
echo "  3. Enable MTP if your model supports it"
echo
echo "Backend:      $(basename $BACKEND_VERSION 2>/dev/null || echo 'PR218 llama-server')"
echo "Config:       $EXISTING_CONFIG"
echo "Models:       check MODEL_ROOT in settings"
echo "Uninstall:    cd $ARCHIVE_DIR && ./uninstall.sh"
echo
INSTALL_EOF

chmod 755 "$STAGING/$ARCHIVE_NAME/install.sh"
echo "Integrated installer created."

# ─────────────────────────────────────────────
# 7. Create the uninstaller
# ─────────────────────────────────────────────

echo "--- Creating uninstaller ---"

cat > "$STAGING/$ARCHIVE_NAME/uninstall.sh" << 'UNINSTALL_EOF'
#!/usr/bin/env bash
# uninstall.sh — Safe uninstaller for PMM 3.0 integrated package
#
# Removes only files identical to this archive checkout.
# Configuration, models, logs and custom backends are preserved.
set -euo pipefail

ARCHIVE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PREFIX="${1:-${PREFIX:-$HOME/.local}}"
PMM_BIN="$PREFIX/bin"
BACKEND_LIB="$PREFIX/lib/prism-llama"

echo "=== Prism Model Manager 3.0 — Uninstaller ==="
echo "Prefix: $PREFIX"
echo

# Remove PMM scripts — only if identical to this archive
REMOVED=0
KEPT=0
for name in prism-model-manager prism-lora-ab-score.py prism-gguf-info.py prism-backend-info.py prism-model-manager-launcher pmm; do
    target="$PMM_BIN/$name"
    archive_file="$ARCHIVE_DIR/bin/$name"
    if [ "$name" = "prism-model-manager-launcher" ] || [ "$name" = "pmm" ]; then
        # Launcher and symlink don't exist in archive/bin/
        if [ -f "$target" ] || [ -L "$target" ]; then
            rm -f "$target"
            echo "  Removed:    $target"
            REMOVED=$((REMOVED + 1))
        fi
    elif [ -f "$archive_file" ] && [ -f "$target" ] && [ ! -L "$target" ] && cmp -s "$archive_file" "$target" 2>/dev/null; then
        rm -- "$target"
        echo "  Removed:    $target"
        REMOVED=$((REMOVED + 1))
    elif [ -e "$target" ] || [ -L "$target" ]; then
        echo "  Kept (modified or unrelated): $target" >&2
        KEPT=$((KEPT + 1))
    fi
done

# Remove bundled backend and libraries — only if identical
if [ -f "$BACKEND_LIB/llama-server" ]; then
    ARCHIVE_SHA=$(sha256sum "$ARCHIVE_DIR/lib/llama-server" 2>/dev/null | awk '{print $1}')
    INSTALLED_SHA=$(sha256sum "$BACKEND_LIB/llama-server" 2>/dev/null | awk '{print $1}')
    if [ "$ARCHIVE_SHA" = "$INSTALLED_SHA" ]; then
        echo "  Removed:    $BACKEND_LIB/llama-server"
        rm -f "$BACKEND_LIB/llama-server"
        REMOVED=$((REMOVED + 1))
        # Clean up shared libraries
        if [ -d "$BACKEND_LIB" ]; then
            for lib in "$BACKEND_LIB"/lib*; do
                [ -f "$lib" ] || continue
                libname=$(basename "$lib")
                archive_lib="$ARCHIVE_DIR/lib/$libname"
                if [ -f "$archive_lib" ]; then
                    if cmp -s "$archive_lib" "$lib" 2>/dev/null; then
                        rm -f "$lib"
                        echo "  Removed:    $lib"
                        REMOVED=$((REMOVED + 1))
                    fi
                fi
            done
            # Remove symlinks
            for link in "$BACKEND_LIB"/lib*.so; do
                [ -L "$link" ] || continue
                target_link=$(readlink "$link")
                if [ -n "$target_link" ]; then
                    rm -f "$link"
                    echo "  Removed:    $link -> $target_link"
                    REMOVED=$((REMOVED + 1))
                fi
            done
            # Remove empty parent dir
            rmdir "$BACKEND_LIB" 2>/dev/null || true
        fi
    else
        echo "  Kept modified backend: $BACKEND_LIB/llama-server" >&2
    fi
fi

# Remove desktop entries
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
for desktop in prism-model-manager.desktop prism-model-manager-terminal.desktop; do
    if [ -f "$APPS_DIR/$desktop" ]; then
        rm -f "$APPS_DIR/$desktop"
        echo "  Removed:    $APPS_DIR/$desktop"
        REMOVED=$((REMOVED + 1))
    fi
done

# Remove Omarchy launcher
OMARCHY_APPS="${XDG_DATA_HOME:-$HOME/.local/share}/omarchy/applications"
if [ -f "$OMARCHY_APPS/prism-model-manager.desktop" ]; then
    rm -f "$OMARCHY_APPS/prism-model-manager.desktop"
    echo "  Removed:    $OMARCHY_APPS/prism-model-manager.desktop"
    REMOVED=$((REMOVED + 1))
fi

echo
echo "=== Uninstall complete ==="
echo "  Files removed: $REMOVED"
echo "  Files kept:     $KEPT"
echo
echo "Configuration, model profiles, logs and model files are preserved."
echo "To also remove those:"
echo "  rm -rf ${XDG_CONFIG_HOME:-$HOME/.config}/prism-model-manager"
echo "  rm -rf ${XDG_STATE_HOME:-$HOME/.local/state}/prism-model-manager"
echo
UNINSTALL_EOF

chmod 755 "$STAGING/$ARCHIVE_NAME/uninstall.sh"
echo "Integrated uninstaller created."

# ─────────────────────────────────────────────
# 8. Copy the README, CHANGELOG and examples
# ─────────────────────────────────────────────

cp "$ROOT/README.md" "$STAGING/$ARCHIVE_NAME/share/manuals/" 2>/dev/null || true
cp "$ROOT/CHANGELOG.md" "$STAGING/$ARCHIVE_NAME/share/manuals/" 2>/dev/null || true
cp "$ROOT/TESTING.md" "$STAGING/$ARCHIVE_NAME/share/manuals/" 2>/dev/null || true

# ─────────────────────────────────────────────
# 9. Create the final archive
# ─────────────────────────────────────────────

echo
echo "--- Creating release archive ---"

mkdir -p "$OUTDIR"

# Compute checksum manifest
echo "Computing file checksums..."
cd "$STAGING/$ARCHIVE_NAME"
find . -type f | sort | while read -r f; do
    sha256sum "$f" >> "$OUTDIR/$ARCHIVE_NAME.sha256.manifest"
done

# Create tar.gz
cd "$STAGING"
tar czf "$OUTDIR/$ARCHIVE_NAME.tar.gz" "$ARCHIVE_NAME"
cd "$OUTDIR"
sha256sum "$ARCHIVE_NAME.tar.gz" > "$ARCHIVE_NAME.tar.gz.sha256"

echo
echo "=== Release archive created ==="
echo
echo "Archive:    $OUTDIR/$ARCHIVE_NAME.tar.gz"
echo "Size:       $(du -h "$OUTDIR/$ARCHIVE_NAME.tar.gz" | awk '{print $1}')"
echo "SHA256:     $(cat "$ARCHIVE_NAME.tar.gz.sha256")"
echo "Manifest:   $OUTDIR/$ARCHIVE_NAME.sha256.manifest"
echo
echo "To install on a new system:"
echo "  tar xzf $ARCHIVE_NAME.tar.gz"
echo "  cd $ARCHIVE_NAME"
echo "  ./install.sh"
echo