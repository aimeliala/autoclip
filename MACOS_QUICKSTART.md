# AutoClip Studio 0.2 — Menjalankan pada macOS

**Status:** Source code yang dapat diinstal dan dijalankan langsung di macOS Intel atau Apple Silicon dengan Python dan FFmpeg. Berkas `.app` terkompilasi **belum disediakan**, karena bundling macOS harus dikerjakan di Mac. UI macOS dan backend multimedia harus divalidasi pada Mac sebenarnya.

## Pemasangan awal (Terminal di Mac)

```bash
# Jika Homebrew sudah terpasang:
brew install python@3.12 ffmpeg deno

# Setelah mengekstrak ZIP, masuk ke folder projek:
cd /path/to/autoclip-studio
chmod +x scripts/*.sh 'Launch AutoClip Studio.command'
./scripts/setup_macos.sh
./scripts/run_macos.sh
```

Cek kebutuhan sistem sebelum membuka GUI:

```bash
.venv/bin/python -m autoclip_studio --doctor
```

Untuk memulai kembali, double-click **Launch AutoClip Studio.command** atau jalankan `./scripts/run_macos.sh`. Saat pertama kali macOS mungkin meminta persetujuan Terminal/aplikasi lokal sesuai pengaturan keamanan sistem. Bila `.command` tidak dijalankan melalui Finder, gunakan Terminal.

## Fitur ringan dan modul tambahan

Instalasi awal menggunakan layanan subtitle yang tersedia, analisis heatmap, aturan highlight offline, dan AI API opsional (Groq/OpenRouter/Kie). Transkripsi lokal serta tracking wajah opsional agar Mac Intel RAM 8/16 GB tidak perlu mengunduh model besar saat pertama run.

```bash
# CPU ASR offline (opsional, lebih berat)
.venv/bin/python -m pip install -e '.[local-asr]'

# Dynamic face tracking melalui OpenCV (opsional)
.venv/bin/python -m pip install -e '.[vision]'

# Development & tests
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

Pengaturan default **Smart Crop** dapat aktif, tetapi bila OpenCV tidak dipasang hasil otomatis fallback ke center crop. Di Pengaturan pilih Speech = `Subtitle yang tersedia` untuk memulai tanpa API/key, atau gunakan Groq untuk transkripsi sumber tanpa subtitle. Mode `Auto` bisa mengunduh faster-whisper jika tak ada subtitle atau key Groq; untuk Mac Intel hemat gunakan `Subtitle yang tersedia` atau API Groq.

### Preview dan timeline

Setelah memilih video dan mengklik **Analisis & pilih klip**, pilih baris kandidat, tekan **Play**, geser timeline, gunakan **Set IN / Set OUT**, lalu ekspor. Media player memakai codec QtMultimedia sistem. Bila MP4 tertentu tidak kompatibel, gunakan **Buka video** untuk membuka player macOS. FFmpeg tetap digunakan saat rendering dan dapat memproses lebih banyak codec daripada player Qt.

### Build .app secara lokal di Mac

```bash
./scripts/build_macos.sh
open dist/AutoClipStudio.app
```

PyInstaller membuat `.app` dari OS build itu sendiri, umumnya untuk arsitektur CPU Mac yang dipakai (arm64 atau x86_64). Untuk didistribusikan ke pengguna lain, tambahkan Developer ID code signing dan notarization Apple. **FFmpeg tidak dibundel**: setiap Mac memerlukan FFmpeg di PATH, atau sesuaikan distribusi binary/lisensi kemudian.

**Tidak termasuk:** model active-speaker audiovisual (perpindahan crop mengikuti pembicara dengan identitas suara), belum diverifikasi pada hardware Mac dan API/YouTube live. Heatmap publik dari yt-dlp bersifat best-effort, bukan API resmi.

## Persyaratan yt-dlp (YouTube)

Untuk dukungan YouTube penuh pada yt-dlp versi baru, perlu `yt-dlp[default]` beserta komponen `yt-dlp-ejs` dan runtime JavaScript Deno. Paket Python sudah disetel ke `yt-dlp[default]`; periksa Deno dengan `deno --version`. yt-dlp tetap library wajib, namun heatmap video publik tidak selalu tersedia.

## Test offline tanpa API key

```bash
./scripts/create_demo.sh
```

Buka `demo/demo-podcast.mp4` sebagai file lokal dan `demo/demo-podcast.srt` sebagai subtitle terpisah. Dalam **Pengaturan**, pilih transkripsi `Subtitle yang tersedia` dan provider AI `Off`, lalu analisis dan ekspor. Hasil demo ini menggunakan sinyal timeline/transkrip, bukan heatmap YouTube.

## Otomatis membuat .app di GitHub Actions

Setelah mengunggah source ke repository GitHub, buka **Actions → Build macOS desktop apps → Run workflow**. Workflow memiliki dua target: macOS ARM (Apple Silicon) dan Intel. Jika workflow berhasil, tersedia ZIP bundle `.app` yang belum ditandatangani melalui **Artifacts**. Workflow ini belum dijalankan di lingkungan pembuatan source saat ini.

## Pembaruan v0.2.1: HTTP 429 subtitle

Jika log menunjukkan `Unable to download video subtitles ... HTTP Error 429`,
upgrade ke source v0.2.1 ini. Unduhan video dan subtitle sudah dipisahkan.
Subtitle dibaca hanya ketika mode transkripsi `Auto` atau `Subtitle yang
tersedia`; error subtitle tidak menghentikan job. Saat `Auto` dipilih,
Groq (bila key tersedia) atau faster-whisper lokal akan menjadi fallback.
Hindari mengulang request subtitle ketika terkena 429; aplikasi menerapkan
cooldown setidaknya 1 jam untuk unduhan subtitle.

Untuk upgrade dari v0.2: ekstrak source baru, lalu jalankan kembali
`./scripts/setup_macos.sh` dan `./scripts/run_macos.sh`. Settings dan API key
pada keychain pengguna tidak disimpan dalam folder source ZIP.
