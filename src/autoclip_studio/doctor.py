"""Offline startup diagnostic; can run before Qt/ASR are installed."""
import importlib.util
import platform
import shutil
import subprocess
import sys

from .hardware import hardware_report


def run():
    print('AutoClip Studio 0.2 • System diagnostic')
    print(f'Platform: {platform.system()} {platform.machine()} • Python {platform.python_version()}')
    h = hardware_report()
    print(f"CPU: {h['cpu']} • {h['cpu_physical']} cores • RAM {h['ram_gb']} GB")
    print(f"Suggested profile: {h['recommended']}")
    required = ('PySide6', 'yt_dlp', 'requests', 'pysubs2', 'psutil', 'keyring')
    optional = ('cv2', 'faster_whisper')
    missing = []
    for name in required + optional:
        found = importlib.util.find_spec(name) is not None
        print(f"{'OK' if found else 'MISSING'} {'(optional)' if name in optional else '(required)'}: {name}")
        if name in required and not found:
            missing.append(name)
    if importlib.util.find_spec('PySide6'):
        try:
            import PySide6.QtMultimedia
            import PySide6.QtMultimediaWidgets
            print('OK: Qt Multimedia preview imports')
        except Exception as exc:
            print(f'NOTICE: Qt Multimedia preview unavailable: {exc}')
    print('OK: deno JavaScript runtime' if shutil.which('deno') else 'NOTICE: Deno missing; install for full yt-dlp YouTube support')
    for name in ('ffmpeg', 'ffprobe'):
        binary = shutil.which(name)
        print(f"{'OK' if binary else 'MISSING'}: {name} {binary or ''}")
        if not binary:
            missing.append(name)
    print('Status:', 'READY' if not missing else 'SETUP REQUIRED (' + ', '.join(missing) + ')')
    return 0 if not missing else 1


if __name__ == '__main__':
    sys.exit(run())
