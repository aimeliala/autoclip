#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Support Homebrew tools when launched from Finder rather than a login shell.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This setup script must run on macOS." >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  echo "FFmpeg missing. Install Homebrew then run: brew install ffmpeg" >&2
  exit 1
fi
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert (3,11) <= sys.version_info[:2] <= (3,13)' >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Please install Python 3.12: brew install python@3.12" >&2
  exit 1
fi
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e .
if ! command -v deno >/dev/null 2>&1; then
  echo "NOTICE: yt-dlp full YouTube support needs Deno. Install with: brew install deno"
fi
echo "Core installed. Optional offline transcription: .venv/bin/python -m pip install -e '.[local-asr]'"
echo "Optional face tracking: .venv/bin/python -m pip install -e '.[vision]'"
echo "Run diagnostics: .venv/bin/python -m autoclip_studio --doctor"
echo "Run: ./scripts/run_macos.sh"
