#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Support Homebrew tools when launched from Finder rather than a login shell.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS only. For Linux/Windows use python -m autoclip_studio." >&2
  exit 1
fi
if [[ ! -f .venv/bin/python ]]; then
  echo "Run ./scripts/setup_macos.sh first." >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  echo "Install FFmpeg: brew install ffmpeg" >&2
  exit 1
fi
exec .venv/bin/python -m autoclip_studio
