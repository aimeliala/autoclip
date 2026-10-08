# AutoClip Studio v0.2.1 · Desktop-first YouTube & AI Clipper

**Status:** v0.2.1 source code, Windows / Linux / **macOS (Intel dan Apple Silicon)** menggunakan PySide6 + Python. Bukan hosted SaaS atau installer siap distribusi. Preview video QtMultimedia dan dynamic face reframe sudah diintegrasikan, tetapi **belum** merupakan deteksi active speaker berbasis suara. Belum dapat dites pada mesin macOS sesungguhnya dalam lingkungan build Linux ini.

## Fitur yang sudah diimplementasikan

- **yt-dlp wajib:** YouTube metadata, `heatmap` Most Replayed (jika tersedia), chapters, daftar subtitle, unduhan video yang pengguna berhak/diizinkan proses, dan subtitle tracks.
- **Input:** URL YouTube atau file video lokal; opsi subtitle `.srt`, `.vtt`, `.ass` dari pengguna.
- **Audio:** utamakan subtitle yang sudah ada; fallback Groq Whisper V3 Turbo/V3 atau faster-whisper CPU INT8. Audio dipotong per 10 menit untuk mengurangi ukuran request.
- **Pilihan klip:** skor heatmap + pembukaan chapter + sinyal tekstual, peringkat offline; dapat di-rerank dengan **OpenRouter**, **Kie.ai** (endpoint model-specific yang sesuai docs), atau **Ollama** lokal.
- **Output:** banyak kandidat klip, edit waktu awal/akhir, pilih via checkbox, ekspor MP4 9:16 dengan caption burn-in (jika ada transkrip).
- **Dynamic face reframe v0.2:** tracking wajah dengan OpenCV pada frame interval (CPU), smoothing dan interpolasi pergerakan kamera dalam filter FFmpeg sendcmd; fallback center crop bila tidak ada wajah. Tidak menjanjikan active-speaker audiovisual.
- **Preview & timeline v0.2:** QtMultimedia preview MP4, play/pause, seek, pilih kandidat, tombol Set IN/OUT, fallback membuka video di external player.
- **Settings:** pilihan provider/model, API keys via sistem keychain (`keyring`) atau memori sesi, folder ekspor, mode hardware otomatis berdasarkan CPU dan RAM, kualitas rendering.
- **UX:** dark theme, UI responsif melalui QThread, progress, log, graph heatmap, preview frame, dan open output folder.

## Persyaratan

- Windows 10/11 x64, Linux desktop x86_64, atau macOS Intel/Apple Silicon (Python 3.11/3.12 dan FFmpeg).
- Python **3.11 atau 3.12** direkomendasikan (macOS: Homebrew `python@3.12`, `ffmpeg`).
- **FFmpeg dan FFprobe** terpasang di `PATH` (FFmpeg perlu filter `subtitles` / libass bila captions diaktifkan).
- Internet untuk URL YouTube atau API cloud. *Mode file lokal + offline dapat digunakan tanpa API key, setelah model Whisper diunduh sekali.*
- RAM 4 GB: profil Economy dan perangkat bisa melambat saat first-run mengunduh model Whisper; RAM 8–16 GB: Balanced; 32 GB: Quality bila CPU juga memadai.
- Karena `faster-whisper` perlu mengunduh modelnya pada eksekusi awal, sebaiknya sediakan ruang disk dan koneksi internet. Agar hemat waktu saat tanpa Groq, bisa memilih subtitle yang sudah tersedia.

## Jalankan di macOS (Intel atau Apple Silicon)

Lihat [MACOS_QUICKSTART.md](MACOS_QUICKSTART.md) untuk walkthrough lengkap.

```bash
# Install Homebrew terlebih dahulu jika belum terpasang
brew install python@3.12 ffmpeg deno
cd autoclip-studio
./scripts/setup_macos.sh
.venv/bin/python -m autoclip_studio --doctor
./scripts/run_macos.sh
```

**Penting untuk yt-dlp:** gunakan `yt-dlp[default]` (sudah termasuk dependensi aplikasi) dan Deno untuk dukungan YouTube terkini.

Untuk captions, FFmpeg harus memiliki filter `subtitles` (libass). Jika build
Homebrew `ffmpeg` tidak mendukungnya, jalankan `brew install ffmpeg-full`, lalu
isi **FFmpeg executable** di pengaturan dengan hasil `brew --prefix ffmpeg-full`
ditambah `/bin/ffmpeg` (Apple Silicon biasanya
`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`). Periksa dukungan dengan
`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg -hide_banner -h filter=subtitles`.
Alternatifnya, nonaktifkan captions untuk ekspor tanpa subtitle.

**Install opsional** bila ingin fitur offline/transkripsi dan tracking wajah (menambah ukuran instalasi):

```bash
.venv/bin/python -m pip install -e '.[local-asr,vision]'
```

Untuk membangun aplikasi macOS lokal, `./scripts/build_macos.sh` membuat `dist/AutoClipStudio.app` di Mac. Tidak dapat cross-compile `.app` dari Linux dan belum codesigned/notarized untuk distribusi. Finder `.app` akan mencari FFmpeg di path Homebrew standar.

## Jalankan di Windows (PowerShell)

```powershell
cd autoclip-studio
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
# Pastikan ffmpeg.exe dan ffprobe.exe tersedia melalui PATH
python -m autoclip_studio
```

Instalasi FFmpeg bisa dilakukan menggunakan package manager tepercaya atau binary build yang lisensinya sesuai kebutuhan. Cek:

```powershell
ffmpeg -version
ffprobe -version
```

## Jalankan di Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg python3-venv
cd autoclip-studio
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
python -m autoclip_studio
```

Jika Qt gagal berjalan karena plugin `xcb`, instal paket sistem yang diperlukan untuk versi distro/Qt Anda. Di Linux, penyimpanan kunci persisten membutuhkan layanan Secret Service/keyring. Tanpa itu, API key hanya aktif selama aplikasi terbuka.

## Cara penggunaan

1. Buka **Pengaturan**, pilih profil **Auto** (rekomendasi hardware ditampilkan). Atur `AI pemilih klip`: `Off` untuk skor lokal, OpenRouter/Kie/Ollama untuk analisis teks berbasis LLM.
2. Pilih mode transkripsi: `Auto` memprioritaskan file subtitle (YouTube) → Groq bila key tersedia → faster-whisper lokal. Jika ingin menekan biaya, pilih `Subtitle yang tersedia`, atau import `.srt` milik sendiri.
3. Tempel URL YouTube lalu klik **Cek heatmap** untuk metadata saja. Bila ingin mengunduh dan memproses video, konfirmasi Anda berhak/diizinkan mengunduhnya. Atau masukkan file lokal.
4. Klik **Analisis & pilih klip**, lalu edit waktu rekomendasi pada tabel.
5. Centang klip dan klik **Export klip terpilih**. File tersimpan di `<Output folder>/projects/<hash>/exports/`.

Heatmap **tidak selalu tersedia** dan bukan API resmi YouTube; bila tidak ada, ranking memakai transkrip/chapters/timeline. AI tidak mengklaim prediksi viral pasti. Pengunduhan YouTube/akses metadata harus sesuai kebijakan dan persetujuan yang berlaku. Jangan gunakan untuk mengambil materi tanpa hak/izin.

## Penyedia AI

| Tugas | Provider | Konfigurasi |
|---|---|---|
| Speech | Groq | `GROQ_API_KEY`, `whisper-large-v3-turbo` atau `whisper-large-v3` |
| Speech | Lokal CPU | faster-whisper `base`/`small` INT8 sesuai profil |
| Rerank/titles | OpenRouter | `OPENROUTER_API_KEY`, model ID disetel pengguna, default `qwen/qwen3.5-flash` (cek ID aktual pada provider) |
| Rerank/titles | Kie.ai | `KIE_API_KEY`; **model dipilih melalui endpoint URL**, default endpoint dokumentasi `gemini-3-flash/v1/chat/completions`. Jika model lain, ganti endpoint mengikuti docs model tersebut |
| Rerank/titles | Ollama | Server Ollama lokal (`http://127.0.0.1:11434`) dan nama model yang sudah di-pull |

**Keamanan API:** prefer kredensial pribadi tiap pengguna. Settings JSON tidak berisi API keys; keychain tidak selalu tersedia (terutama Linux headless). Bila membangun SaaS berbayar nanti, pindahkan akses key milik operator ke backend proxy terautentikasi.

## Build untuk Windows/Linux/macOS

Build **pada masing-masing OS**, bukan Windows binary dari Linux atau sebaliknya.

```powershell
# Windows CMD
scripts\build_windows.bat
```

```bash
# Linux
./scripts/build_linux.sh
```

Di Windows/Linux, PyInstaller output berada di `dist/AutoClipStudio/`. Di macOS, `scripts/build_macos.sh` menghasilkan `dist/AutoClipStudio.app`. **FFmpeg tidak dibundel**, jadi pengguna perlu memasangnya sendiri atau distributor harus membundel binary yang lisensinya sesuai. Build offline besar karena PySide6/ct2/OpenCV; di Windows pertimbangkan code signing sebelum mendistribusikan installer.

## Struktur sumber

```text
src/autoclip_studio/
  app.py         # Qt UI: Studio, timeline, Pengaturan, Panduan
  config.py      # settings JSON + keychain API keys
  hardware.py    # deteksi CPU, RAM, rekomendasi profil
  youtube.py     # yt-dlp: metadata, heatmap, download, subtitle
  media.py       # FFmpeg, FFprobe, crop primitives
  smart_reframe.py # CPU face tracking, smooth track, FFmpeg sendcmd
  transcript.py  # subtitle + Groq/faster-whisper
  highlights.py  # heatmap ranking + LLM OpenRouter/Kie/Ollama
  pipeline.py    # end-to-end source → analyze candidates
  render.py      # FFmpeg 9:16 + SRT burn-in
  doctor.py      # Offline startup diagnostics (--doctor)
  __main__.py
scripts/
  build_windows.bat
  build_linux.sh
  setup_macos.sh
  run_macos.sh
  build_macos.sh
  launch.py
  package_windows.ps1
 tests/
```

## Keterbatasan MVP

- **Auto close-up belum speaker-aware.** Reframe dinamis bisa mengikuti posisi wajah dalam clip, tetapi tidak menentukan identitas pembicara lewat suara. Model audiovisual active-speaker terpisah belum diimplementasikan.
- Heatmap `yt-dlp` dapat kosong, rusak, atau berubah ketika YouTube berubah; bukan endpoint resmi. Subtitle otomatis YouTube juga sering berubah format/aksesnya.
- Preview dasar dan timeline IN/OUT sudah ada, tetapi belum NLE multitrack; belum ada GPU-accelerated model, pembayaran SaaS, atau job queue terdistribusi.
- Perbandingan waktu proses pada perangkat Ryzen/X280 perlu benchmark sungguhan; deteksi hardware adalah heuristik, bukan pengujian kecepatan.
- Render FFmpeg menghasilkan video 720p/1080p dan mengenkode ulang, sehingga laptop 4 GB dapat lambat.
- Kredensial harus disimpan dengan keychain atau env, bukan commit ke repository.

## Test

```bash
pip install -e '.[dev]'
pytest -q
```

Test unit untuk scoring/crop/settings dan test FFmpeg integrasi lokal ada di folder `tests/`. Tes GUI native macOS, endpoint provider, serta YouTube live memerlukan lingkungan desktop macOS dan akses valid. Di Linux, tes core, integrasi FFmpeg, dan crop dinamis dapat berjalan secara offline.

Diagnostik tanpa membuka UI: `python -m autoclip_studio --doctor`.

## Fix v0.2.1 — HTTP 429 saat mengunduh subtitle YouTube

Sebelumnya yt-dlp meminta video dan beberapa subtitle (`id`, `en`) bersamaan,
sehingga HTTP 429 subtitle dapat menghentikan job walaupun video sudah ada.
Sekarang:

- Metadata/heatmap, unduhan video, dan unduhan subtitle merupakan operasi **terpisah**.
- Unduhan video yang diizinkan tidak meminta subtitle dan tidak gagal akibat error subtitle.
- Caption diunduh hanya bila mode `Auto` atau `Subtitle yang tersedia` aktif;
  dipilih **satu track** manual atau automatic bahasa asli bila tersedia.
- Tidak meminta subtitle hasil terjemahan otomatis tanpa memastikan bahasa asli,
  untuk mengurangi request dan risiko 429.
- Saat 429, pengambilan subtitle dihentikan selama sekitar 60 menit secara lokal,
  tanpa mencoba menghindari rate limit YouTube. Analisis lanjut dengan Groq
  atau faster-whisper (jika tersedia), atau heatmap/chapters tanpa caption.
- Jika sudah ada transkrip di cache, subtitle tidak diminta ulang.

**Langkah setelah pembaruan:** jalankan kembali analisis pada video yang sama.
File video yang sudah diunduh akan digunakan kembali dari workspace sehingga
semestinya tidak perlu download ulang. Jika memilih `Auto`, isi API Groq atau
install ekstra `local-asr` untuk transkripsi fallback. Mode `Subtitle yang tersedia`
tidak menjalankan transkripsi otomatis, sehingga jika track kosong atau 429,
analisis tetap jalan tanpa caption.
