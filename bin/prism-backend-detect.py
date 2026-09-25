#!/usr/bin/env python3
"""PMM backend and GPU detection helper.

Detects NVIDIA GPU, VRAM, compute capability, driver version, CUDA runtime,
Python version and ABI tag compatibility. Prints JSON for consumption by the
PMM shell script.

Output keys:
  gpu_name, gpu_count, vram_total_mib, vram_per_gpu_mib,
  compute_capability, compute_arch, driver_version,
  cuda_version, cuda_compatible,
  python_version, python_abi_tag, platform_tag,
  vllm_compatible, vllm_reason,
  llama_cuda_compatible, llama_cuda_reason,
  system_ram_gib, system_ram_available_gib
"""

import json
import os
import re
import shutil
import struct
import subprocess
import sys
from functools import lru_cache


def nvidia_smi(*args, timeout=5):
    """Run nvidia-smi and return stdout, or None on failure."""
    nvidia_smi_bin = shutil.which('nvidia-smi')
    if not nvidia_smi_bin:
        return None
    try:
        result = subprocess.run(
            [nvidia_smi_bin, *args],
            capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_nvidia_gpu_info():
    """Query GPU name, VRAM, compute capability via nvidia-smi."""
    info = nvidia_smi(
        '--query-gpu=name,memory.total,compute_cap,driver_version',
        '--format=csv,noheader,nounits')
    if not info:
        return None, 0, 0, None, None, None

    lines = info.strip().splitlines()
    if not lines:
        return None, 0, 0, None, None, None

    first = lines[0]
    parts = [p.strip() for p in first.split(',')]
    if len(parts) < 3:
        return None, 0, 0, None, None, None

    name = parts[0]
    vram = int(parts[1]) if parts[1].isdigit() else 0
    compute_cap = parts[2] if len(parts) > 2 else None
    driver = parts[3] if len(parts) > 3 else None
    count = len(lines)

    # Compute arch from compute capability
    compute_arch = 'Unknown'
    if compute_cap:
        cap_num = float(compute_cap.split('.')[0] + '.' + compute_cap.split('.')[1])
        if cap_num >= 10.0:
            compute_arch = 'Blackwell'
        elif cap_num >= 9.0:
            compute_arch = 'Hopper'
        elif cap_num >= 8.9:
            compute_arch = 'Ada Lovelace'
        elif cap_num >= 8.6:
            compute_arch = 'Ampere'
        elif cap_num >= 8.0:
            compute_arch = 'Ampere'
        elif cap_num >= 7.5:
            compute_arch = 'Turing'
        elif cap_num >= 7.0:
            compute_arch = 'Volta'
        else:
            compute_arch = 'Pre-Volta'

    return name, count, vram, compute_cap, compute_arch, driver


def get_cuda_version():
    """Detect CUDA version from nvcc or CUDA runtime library."""
    # Try nvcc
    nvcc = shutil.which('nvcc')
    if nvcc:
        try:
            result = subprocess.run(
                [nvcc, '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                m = re.search(r'release\s+(\d+\.\d+)', result.stdout)
                if m:
                    return m.group(1)
        except (OSError, subprocess.TimeoutExpired):
            pass

    # Try cuda_version from cuda.h or cuda_runtime
    for header_candidate in [
        '/usr/include/cuda.h',
        '/usr/local/cuda/include/cuda.h',
        '/opt/cuda/include/cuda.h'
    ]:
        if os.path.isfile(header_candidate):
            try:
                with open(header_candidate) as f:
                    content = f.read()
                    major_m = re.search(r'#define\s+CUDA_VERSION\s+(\d+)', content)
                    if major_m:
                        major = int(major_m.group(1))
                        # CUDA_VERSION is major*1000 + minor*10
                        minor = (major % 1000) // 10
                        major = major // 1000
                        return f'{major}.{minor}'
            except (OSError, UnicodeError):
                pass

    # Try libcuda.so version
    try:
        result = subprocess.run(
            ['sh', '-c', 'ldconfig -p 2>/dev/null | grep libcuda.so | head -1'],
            capture_output=True, text=True, timeout=3)
        if result.stdout.strip():
            m = re.search(r'libcuda\.so\.(\d+)', result.stdout)
            if m:
                # Driver version is not CUDA toolkit version, but can hint
                driver_ver = m.group(1)
    except (OSError, subprocess.TimeoutExpired):
        pass

    # Last resort: check nvidia-smi for CUDA version
    smi = nvidia_smi('--query-gpu=driver_version', '--format=csv,noheader')
    if smi:
        driver_ver = smi.strip().splitlines()[0].strip()
        # Rough mapping: driver >= 580 → CUDA 13, driver 550 → CUDA 12, etc.
        try:
            d = int(driver_ver.split('.')[0])
            if d >= 580:
                return '13.0'
            elif d >= 550:
                return '12.4'
            elif d >= 530:
                return '12.1'
            elif d >= 520:
                return '11.8'
            elif d >= 470:
                return '11.4'
        except (ValueError, IndexError):
            pass

    return None


def get_python_info():
    """Get Python version, ABI tag, platform tag."""
    v = sys.version_info
    py_version = f'{v.major}.{v.minor}.{v.micro}'
    py_short = f'{v.major}.{v.minor}'

    # Compute ABI tag
    abi_tag = f'cp{v.major}{v.minor}'

    # Platform tag
    import struct
    machine = struct.calcsize('P') * 8
    arch_map = {
        'x86_64': 'x86_64',
        'amd64': 'x86_64',
        'aarch64': 'aarch64',
        'arm64': 'aarch64',
    }
    arch = arch_map.get(os.uname().machine.lower(), os.uname().machine)

    platform_tag = f'linux_{arch}'

    return py_version, abi_tag, platform_tag, py_short


def get_vllm_wheel_url(py_short, cuda_ver, platform_tag, compute_cap):
    """Determine the correct vLLM wheel URL for this system.

    Returns (url, version, reason) tuple. reason is None if compatible.
    """
    vllm_version = '0.30.0'

    # Check compute capability
    if compute_cap:
        try:
            cap = float(compute_cap)
            if cap < 8.0:
                return (None, None,
                        f'NVIDIA compute capability {compute_cap} < 8.0 (Ampere+ required for vLLM)')
        except (ValueError):
            return (None, None, f'Cannot parse compute capability: {compute_cap}')

    # If no GPU at all
    if not compute_cap:
        return (None, None, 'No compatible NVIDIA GPU detected')

    # Determine URL based on CUDA/driver
    if cuda_ver:
        cuda_major = int(cuda_ver.split('.')[0])
        if cuda_major >= 13:
            # CUDA 13 -> standard PyPI wheel
            url = None  # Standard pip install
            return (url, vllm_version, None)
        elif cuda_major == 12:
            # CUDA 12 -> use CUDA 12.9 wheel index
            url = (
                f'https://wheels.vllm.ai/{vllm_version}/cu129'
                f' --extra-index-url https://download.pytorch.org/whl/cu129'
                f' --index-strategy unsafe-best-match'
            )
            return (url, vllm_version, None)
        else:
            return (None, None, f'CUDA {cuda_ver} is too old for vLLM {vllm_version}')

    # Driver-based fallback
    return (None, vllm_version, None)  # Unknown CUDA — try standard install


def get_llama_cuda_info():
    """Check if llama.cpp CUDA build should work on this system."""
    smi = nvidia_smi('--query-gpu=driver_version', '--format=csv,noheader')
    if smi:
        return True, None

    # Check for libcuda
    try:
        r = subprocess.run(['ldconfig', '-p'], capture_output=True, text=True, timeout=3)
        if 'libcuda.so' in r.stdout:
            return True, None
    except (OSError, subprocess.TimeoutExpired):
        pass

    return False, 'No NVIDIA driver or libcuda detected'


def get_system_ram():
    """Get system RAM in GiB."""
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    kb = int(line.split()[1])
                    total_gib = kb / (1024 * 1024)
                elif line.startswith('MemAvailable:'):
                    avail_kb = int(line.split()[1])
                    avail_gib = avail_kb / (1024 * 1024)
            return round(total_gib, 1), round(avail_gib, 1)
    except (OSError, ValueError):
        return None, None


def get_disk_space(path='/'):
    """Get disk space in GiB for a given path."""
    try:
        stat = os.statvfs(path)
        free = stat.f_bavail * stat.f_frsize / (1024**3)
        total = stat.f_blocks * stat.f_frsize / (1024**3)
        return round(total, 1), round(free, 1)
    except OSError:
        return None, None


def main():
    result = {}

    # GPU info
    gpu_name, gpu_count, vram_total, compute_cap, compute_arch, driver_ver = get_nvidia_gpu_info()
    result['gpu_name'] = gpu_name
    result['gpu_count'] = gpu_count
    result['vram_total_mib'] = vram_total
    result['vram_per_gpu_mib'] = vram_total // max(gpu_count, 1) if gpu_count else 0
    result['compute_capability'] = compute_cap
    result['compute_arch'] = compute_arch
    result['driver_version'] = driver_ver

    # CUDA version
    cuda_ver = get_cuda_version()
    result['cuda_version'] = cuda_ver
    result['cuda_compatible'] = cuda_ver is not None

    # Python info
    py_ver, abi_tag, platform_tag, py_short = get_python_info()
    result['python_version'] = py_ver
    result['python_abi_tag'] = abi_tag
    result['platform_tag'] = platform_tag

    # vLLM compatibility
    vllm_url, vllm_ver, vllm_reason = get_vllm_wheel_url(
        py_short, cuda_ver, platform_tag, compute_cap)
    result['vllm_compatible'] = vllm_reason is None
    result['vllm_reason'] = vllm_reason
    result['vllm_pip_url'] = vllm_url
    result['vllm_version'] = vllm_ver

    # llama.cpp CUDA compatibility
    llama_ok, llama_reason = get_llama_cuda_info()
    result['llama_cuda_compatible'] = llama_ok
    result['llama_cuda_reason'] = llama_reason

    # System RAM
    ram_total, ram_avail = get_system_ram()
    result['system_ram_gib'] = ram_total
    result['system_ram_available_gib'] = ram_avail

    # Disk space at default model root
    home = os.environ.get('HOME', '/')
    disk_total, disk_free = get_disk_space(home)
    result['disk_home_total_gib'] = disk_total
    result['disk_home_free_gib'] = disk_free

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == '__main__':
    main()