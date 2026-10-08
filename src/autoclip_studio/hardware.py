"""Conservative cross-platform hardware profiling; no benchmark claims."""
import os
import platform
import subprocess


def hardware_report():
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / 1024**3, 1)
        cpu_logical = psutil.cpu_count(logical=True) or 2
        cpu_physical = psutil.cpu_count(logical=False) or cpu_logical
    except ImportError:
        ram_gb, cpu_logical, cpu_physical = 8, os.cpu_count() or 2, os.cpu_count() or 2
    gpu = 'Tidak terdeteksi (CPU mode aman)'
    try:
        if platform.system() == 'Windows':
            cmd = ['powershell', '-NoProfile', '-Command',
                   '(Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name)']
        elif platform.system() == 'Darwin':
            cmd = ['system_profiler', 'SPDisplaysDataType']
        else:
            cmd = ['sh', '-c', 'command -v lspci >/dev/null && lspci | grep -Ei "VGA|3D controller" | head -1']
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
        if res.stdout.strip():
            if platform.system() == 'Darwin':
                lines = [line.strip() for line in res.stdout.splitlines()
                         if ('Chipset Model:' in line or 'Chip:' in line)]
                gpu = (lines[0] if lines else platform.machine())[:115]
            else:
                gpu = res.stdout.strip()[:115]
    except (OSError, subprocess.TimeoutExpired):
        pass
    recommended = 'economy' if ram_gb < 12 or cpu_physical <= 2 else ('quality' if ram_gb >= 24 and cpu_physical >= 6 else 'balanced')
    return {'ram_gb': ram_gb, 'cpu_logical': cpu_logical, 'cpu_physical': cpu_physical,
            'cpu': platform.processor() or ('Apple Silicon ' + platform.machine() if platform.system() == 'Darwin' and platform.machine() == 'arm64' else platform.machine()), 'gpu': gpu,
            'platform': platform.system(), 'recommended': recommended}


def effective_profile(settings, report):
    return report['recommended'] if settings.profile == 'auto' else settings.profile


def profile_defaults(profile):
    return {
        'economy': {'resolution': 720, 'vision_samples': 5, 'whisper_model': 'base', 'cpu_threads': 2},
        'balanced': {'resolution': 720, 'vision_samples': 9, 'whisper_model': 'small', 'cpu_threads': 4},
        'quality': {'resolution': 1080, 'vision_samples': 14, 'whisper_model': 'small', 'cpu_threads': 6},
    }[profile]
