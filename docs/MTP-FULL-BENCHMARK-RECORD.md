# Ternary Bonsai 2 27B PTQ1_0 MTP Q8_0 — Full MTP Benchmark Record

**Model:** `Ternary-Bonsai-2-27B-PTQ1_0-MTP-Q8_0-fixed.gguf`
**Backend:** Prism llama.cpp fork, build `10718`, commit `3443ddece` (PR #218 + Hadamard inverse fix)
**GPU:** NVIDIA GeForce RTX 4070 SUPER, 12 GB (12,282 MiB total), driver 610.57.04, Ada (sm_89)
**Date:** 2026-09-22

## Verified methodology (all configs)

- One validated warm-up + **three** measured `/completion` runs per configuration.
- **Median** reported over the 3 measured runs (never the maximum).
- 500 generated tokens per measured run (`n_predict=500`, `stop_type=limit`).
- Parameter set: context **40960**, KV cache **q8_0/q8_0**, Flash Attention **on**, GPU layers **99** (`-ngl 99`, all layers on GPU), batch **2048**, ubatch **512**, temperature **0**, seed **42**, `--reasoning-effort medium`, `--jinja`.
- **Batch Invariant OFF** (main draft-length comparison baseline). `GGML_CUDA_BATCH_INVARIANT` is unset for all rows below.
- Strict validation: HTTP 2xx, response schema, exact token target, expected `speculative.types`, **zero CUDA errors**, **zero CPU fallback**, no early stop.
- VRAM reported as absolute `nvidia-smi` samples after each response (single process, no other GPU workload). VRAM is flat during generation; peak ≈ load-time allocation.
- The single fit warning present on all MTP rows is the auto-tuner aborting because `-ngl 99` is user-forced — it does not move layers to CPU (`cpu_fallback=0` in every measured run).

## Short-context results (56-token prompt → actual context 556)

| MTP | n-max | Median gen tok/s | Per-run (3 runs) | Median acceptance | Per-run accept | Draft gen/accepted | Median VRAM after (MiB) | Note |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| OFF | — | **58.469** | 58.469/58.480/58.418 | N/A | N/A | N/A | 8729 | non-speculative |
| 1 | 1 | **80.741** | 80.784/80.741/80.688 | 76.596% | — | 282/216 | 10065 | best per-GB value |
| 2 | 2 | **91.178** | 91.131/91.178/91.364 | 65.127% | — | 433/282 | 10663 | **fastest** |
| 3 | 3 | **83.534** | 83.909/82.639/83.534 | 56.781% | — | 553/314 | 11169 | lower acceptance |
| 4 | 4 | **69.314** | 68.295/69.615/69.314 | 46.485% | — | 697/324 | 11771 | acceptance collapse |

Short-context speed is **not** representative of long-context (occupied-context) speed — see below.

## Long-context results (17,531-token prompt → actual context 18,031)

| MTP | n-max | Median gen tok/s | Median acceptance | Median VRAM after (MiB) | Note |
|---|---:|---:|---:|---:|---|
| OFF | — | **45.889** | N/A | 8791 | non-speculative |
| 1 | 1 | **60.875** | 61.688% | 10058 | |
| 2 | 2 | **69.140** | 68.974% | 10578 | **fastest long-context** |
| 3 | 3 | **67.038** | 56.295% | 11177 | |
| 4 | 4 | **56.192** | 42.547% | 11773 | VRAM nears 12 GB |

All long-context runs used the deterministic prompt tokenizing to **17,531 tokens**, generating 500 tokens, for an estimated actual context of **18,031** tokens within a 40,960-token context window.

## Long-context per-run detail (PR #218)

| Config | run | gen tok/s | prompt_ms | draft gen/acc | accept % | VRAM after (MiB) |
|---|---:|---:|---:|---:|---:|---:|
| D2-MTP2 | 1 | 69.140 | 28342 | — | 68.974 | 10583 |
| D2-MTP2 | 2 | 69.290 | 28647 | — | 68.974 | 10578 |
| D2-MTP2 | 3 | 67.744 | 28916 | — | 68.974 | 10576 |
| D3-MTP3 | 1 | 68.854 | 28657 | — | 56.295 | 11177 |
| D3-MTP3 | 2 | 67.034 | 28580 | — | 56.295 | 11191 |
| D3-MTP3 | 3 | 67.038 | 29138 | — | 56.295 | 11173 |
| D4-MTP4 | 1 | 54.932 | 29162 | — | 42.547 | 11773 |
| D4-MTP4 | 2 | 56.192 | 28655 | — | 42.547 | 11768 |
| D4-MTP4 | 3 | 59.637 | 26856 | — | 42.547 | 11783 |

## Short-context per-run detail (PR #218, new MTP 3/4)

| Config | run | gen tok/s | prompt_ms | draft gen/acc | accept % | VRAM after (MiB) |
|---|---:|---:|---:|---:|---:|---:|
| G-MTP3 | 1 | 83.909 | 160.75 | 553/314 | 56.781 | 11163 |
| G-MTP3 | 2 | 82.639 | 161.84 | — | 56.781 | 11169 |
| G-MTP3 | 3 | 83.534 | 163.82 | — | 56.781 | 11171 |
| H-MTP4 | 1 | 68.295 | 169.33 | 697/324 | 46.485 | 11773 |
| H-MTP4 | 2 | 69.615 | 159.88 | — | 46.485 | 11765 |
| H-MTP4 | 3 | 69.314 | 161.55 | — | 46.485 | 11771 |

## Interpretation

- **MTP is a large benefit**: MTP1 ≈ +38% short / +33% long over MTP-off; MTP2 ≈ +56% short / +51% long over MTP-off.
- **Draft length 2 is optimal**: n-max=2 is the fastest in both short (91.2) and long (69.1) context. Going to n-max=3 or 4 reduces both acceptance and speed, and adds VRAM.
- **Long context is not the same number as short context**: all long-context speeds are ~15–24% lower than the matching short-context numbers because the entire 17.5K-token KV/prompt is resident and re-read each step.
- **What actually contributes**: combining the PTQ1_0 backbone with the ProCreations r3-mtp adapted MTP head, the PR #218 PTQ1_0 CUDA kernel (by sudoingsx / PrismML PR #218), and running on the Prism fork with the Hadamard-inverse fix.

## Raw artifacts

- Short MTP 3/4: `bonsai-kernel-test/results/mtp34-runs/` (summary `mtp34-summary-20260922-095850.txt`)
- Long MTP 2/3/4: `bonsai-kernel-test/results/long-context-mtp234-runs/` (summary `long-context-mtp234-summary-20260922-100120.txt`)
- Full short A–F: `bonsai-kernel-test/results/benchmark-analysis-20260922-043448.md`
- Full long A/C/D: `bonsai-kernel-test/results/long-context-analysis-20260922-085443.md`
- Aggregator: `bonsai-kernel-test/aggregate_mtp234.py`
- Scripts: `bonsai-kernel-test/mtp34_benchmark.sh`, `bonsai-kernel-test/long_context_mtp234.sh`

## Model identity for all rows

- File SHA256: `4c21bfcfa7e643d32179db409751941c5d1f7fcf188901c286e37d3913809cd1`
- 6,397,969,728 bytes.
- Backbone `prism-ml/Ternary-Bonsai-2-27B-gguf` PTQ1_0 @ `6ed5e12b...`; MTP head `ProCreations/Ternary-Bonsai-2-27B-MTP` r3-mtp @ `efffdea64c1f9...`.