#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install -e '.[dev]'
python3 -m PyInstaller --noconfirm --clean --windowed --onedir --name AutoClipStudio --collect-all yt_dlp --collect-all pysubs2 scripts/launch.py
echo 'Built: dist/AutoClipStudio/AutoClipStudio'
