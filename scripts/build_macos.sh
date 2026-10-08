#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Support Homebrew tools when launched from Finder rather than a login shell.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS .app must be built on macOS of the target architecture." >&2
  exit 1
fi
if [[ ! -f .venv/bin/python ]]; then
  echo "Run scripts/setup_macos.sh first." >&2
  exit 1
fi
.venv/bin/python -m pip install 'pyinstaller>=6,<7'
EXTRAS=()
if .venv/bin/python -c 'import cv2' >/dev/null 2>&1; then
  EXTRAS+=(--collect-all cv2)
fi
if .venv/bin/python -c 'import faster_whisper' >/dev/null 2>&1; then
  EXTRAS+=(--collect-all faster_whisper --collect-all ctranslate2)
fi
.venv/bin/python -m PyInstaller \
  --noconfirm --clean --windowed --onedir \
  --name AutoClipStudio \
  --osx-bundle-identifier dev.autoclip.studio \
  --hidden-import PySide6.QtMultimedia \
  --hidden-import PySide6.QtMultimediaWidgets \
  --collect-all yt_dlp \
  --collect-all yt_dlp_ejs \
  --collect-all pysubs2 \
  "${EXTRAS[@]}" \
  scripts/launch.py
printf '\nApp bundle: dist/AutoClipStudio.app\n'
echo 'FFmpeg is NOT bundled: install via brew install ffmpeg.'
echo 'This local bundle is not Developer ID signed/notarized for public distribution.'
