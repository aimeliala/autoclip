#!/usr/bin/env bash
# Create a copyright-free local sample so AutoClip can be tried without API keys.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p demo
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i 'testsrc2=size=640x360:rate=24' \
  -f lavfi -i 'sine=frequency=440:sample_rate=16000' \
  -t 18 -c:v libx264 -preset ultrafast -pix_fmt yuv420p \
  -c:a aac -shortest 'demo/demo-podcast.mp4'
cat > 'demo/demo-podcast.srt' <<'SRT'
1
00:00:00,000 --> 00:00:06,000
Demo AutoClip Studio: sebuah video pengujian lokal.

2
00:00:06,000 --> 00:00:12,000
Bagaimana kita memilih potongan video yang paling menarik?

3
00:00:12,000 --> 00:00:18,000
Ini adalah subtitle uji, bukan hasil transkripsi AI.
SRT
echo 'Ready: demo/demo-podcast.mp4 and demo/demo-podcast.srt'
