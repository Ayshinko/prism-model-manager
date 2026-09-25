#!/usr/bin/env python3
"""PMM model format detection helper.

Detects model format, architecture, and compatibility with available backends.
Output is JSON for consumption by the PMM shell script.

Accepts a path argument (file or directory). Returns:
  format: 'gguf' | 'hf' (HuggingFace safe tensors) | 'mirai_s' | 'unknown'
  name: human-readable model name
  architecture: model architecture string
  parameters_b: estimated parameter count in billions
  quantization: quantization format if known
  context_length: maximum context length if known
  file_count: number of relevant weight files
  total_size_gib: total size of weight files in GiB
  compatible_backends: list of backends that can serve this model
  recommended_backend: best-match backend
  reason: explanation string
"""
import json
import os
import re
import sys
from pathlib import Path


def read_json_safe(path, max_size=1024 * 1024):
    """Read and parse a JSON file, with size limit."""
    try:
        if os.path.getsize(path) > max_size:
            return None
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None


def get_gguf_info(path):
    """Read GGUF metadata (delegates to prism-gguf-info.py)."""
    import subprocess

    # Find the gguf info script
    script_dir = Path(__file__).resolve().parent
    gguf_info = script_dir / 'prism-gguf-info.py'

    if not gguf_info.exists():
        # Try relative to the calling context
        gguf_info = Path(os.environ.get('PMM_BIN_DIR', '')) / 'prism-gguf-info.py'

    if not gguf_info.exists():
        return None

    try:
        result = subprocess.run(
            [sys.executable, str(gguf_info), path],
            capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def detect_gguf(path):
    """Detect and describe a GGUF model."""
    info = get_gguf_info(path)
    if not info:
        return None

    name = info.get('general.name', os.path.basename(path))
    arch = info.get('general.architecture', 'unknown')
    quant = info.get('quantization', 'Unknown')
    ctx = info.get(f'{arch}.context_length', 0) if arch != 'unknown' else 0
    ftype = info.get('general.file_type')

    # Estimate parameter count from file size
    size_mb = os.path.getsize(path) / (1024 * 1024)
    params_b = round(size_mb / 500, 1) if size_mb > 0 else 0

    compatible = ['llama.cpp']
    recommended = 'llama.cpp'

    # Check for Bonsai / Prism-specific formats
    if 'PTQ1_0' in quant or 'PQ2_0' in quant or name.upper().find('BONSAI') >= 0:
        compatible = ['llama.cpp']
        recommended = 'llama.cpp'

    return {
        'format': 'gguf',
        'name': name,
        'architecture': arch,
        'parameters_b': params_b,
        'quantization': quant,
        'context_length': ctx,
        'file_count': 1,
        'file_sizes_mib': [round(os.path.getsize(path) / (1024 * 1024), 1)],
        'total_size_mib': round(size_mb, 1),
        'compatible_backends': compatible,
        'recommended_backend': recommended,
        'reason': f'GGUF format: {arch}, {quant}',
    }


def detect_hf_directory(path: Path):
    """Detect and describe a HuggingFace model directory with safe tensors."""
    config_path = path / 'config.json'
    model_index_path = path / 'model.safetensors.index.json'

    if not config_path.exists():
        return None

    config = read_json_safe(str(config_path))
    if not config:
        return {'format': 'hf_unreadable', 'reason': 'config.json present but unreadable'}

    arch = config.get('model_type', 'unknown')
    name = config.get('_name_or_path', path.name)
    params_b = config.get('num_parameters', 0)

    # Try to get context length
    max_ctx = (config.get('max_position_embeddings') or
               config.get('max_sequence_length') or 0)
    if isinstance(max_ctx, str):
        try:
            max_ctx = int(max_ctx)
        except (ValueError, TypeError):
            max_ctx = 0

    # Detect quantization from config
    quant = 'Unknown'
    torch_dtype = config.get('torch_dtype', 'unknown')
    quantization_config = config.get('quantization_config', {})
    if quantization_config:
        quant_method = quantization_config.get('quant_method', '')
        if quant_method:
            quant = f'{quant_method} ({torch_dtype})'
    else:
        quant = torch_dtype

    # Find all weight files
    weight_files = []
    total_size = 0
    for ext in ['.safetensors', '.bin', '.pt']:
        for f in sorted(path.glob(f'*{ext}')):
            try:
                sz = os.path.getsize(f) / (1024 * 1024)
                weight_files.append({'name': f.name, 'size_mib': round(sz, 1)})
                total_size += sz
            except OSError:
                pass

    # Check for Mirai S (vllm subdirectory with plugin wheel)
    mirai_s = False
    vllm_dir = path / 'vllm'
    if vllm_dir.is_dir() and vllm_dir.exists():
        plugin_wheels = list(vllm_dir.glob('mirai_s-*.whl'))
        if plugin_wheels:
            mirai_s = True
            name = f'{name} (Mirai S)'

    # Determine compatible backends
    compatible = []
    vllm_architectures = {
        'qwen2', 'llama', 'mistral', 'mixtral', 'gemma', 'gemma2', 'phi3',
        'phi', 'falcon', 'starcoder2', 'deepseek_v2', 'deepseek_v3', 'baichuan',
        'internlm', 'command_r', 'dbrx', 'olmo', 'qwen2_moe', 'stablelm',
        'cohere', 'nemotron', 'exaone', 'minicpm', 'opt', 'bloom',
    }

    # Only precise architectures — never assume breadth coverage
    if arch.lower() in vllm_architectures:
        compatible.append('vllm')
    else:
        compatible.append('llama.cpp')

    recommended = 'vllm' if 'vllm' in compatible else 'llama.cpp'

    if mirai_s:
        compatible = ['vllm']
        recommended = 'vllm'
        plugin = 'Mirai S'
    else:
        plugin = 'None'

    return {
        'format': 'mirai_s' if mirai_s else 'hf',
        'name': name,
        'architecture': arch,
        'parameters_b': params_b if params_b else round(total_size / 500, 1) if total_size else 0,
        'quantization': quant,
        'context_length': max_ctx,
        'file_count': len(weight_files),
        'file_sizes_mib': [f['size_mib'] for f in weight_files],
        'total_size_mib': round(total_size, 1),
        'compatible_backends': compatible,
        'recommended_backend': recommended,
        'plugin_supported': 'Mirai S' if mirai_s else None,
        'reason': (
            f'HuggingFace model: {arch}'
            f'{", Mirai S plugin detected" if mirai_s else ""}'
        ),
    }


def detect(path_str):
    """Detect model format from the given path."""
    path = Path(path_str)

    if not path.exists():
        return {'format': 'not_found', 'reason': f'Path does not exist: {path}'}

    # Check for GGUF file
    if path.is_file() and path.suffix.lower() == '.gguf':
        result = detect_gguf(str(path))
        if result:
            return result
        return {'format': 'gguf', 'reason': 'GGUF file detected but metadata unreadable'}

    # Check for GGUF shard (first shard)
    if path.is_file():
        m = re.match(r'(.+)-(\d{5})-of-(\d{5})\.gguf$', path.name, re.IGNORECASE)
        if m:
            result = detect_gguf(str(path))
            if result:
                return result
            return {'format': 'gguf_shard', 'reason': f'GGUF shard: {m.group(2)} of {m.group(3)}'}

    # Check for directory (HuggingFace / Mirai S)
    if path.is_dir():
        result = detect_hf_directory(path)
        if result:
            return result

        # Check for GGUF files inside directory
        gguf_files = list(path.glob('*.gguf'))
        if gguf_files:
            # Detect first GGUF
            result = detect_gguf(str(gguf_files[0]))
            if result:
                result['file_count'] = len(gguf_files)
                return result
            return {'format': 'gguf_dir', 'reason': f'Directory containing {len(gguf_files)} GGUF file(s)'}

        return {'format': 'unknown_dir', 'reason': 'Directory does not contain recognized model files'}

    if path.is_file():
        ext = path.suffix.lower()
        if ext in ('.bin', '.pt', '.safetensors', '.pth'):
            return {'format': 'weight_file', 'reason': f'Standalone weight file ({ext}). Needs a directory with config.json.'}

        return {'format': 'unknown_file', 'reason': f'Unrecognized file type: {ext}'}

    return {'format': 'unknown', 'reason': 'Could not determine model format'}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: prism-model-detect.py <path>'}), file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    result = detect(path)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == '__main__':
    main()