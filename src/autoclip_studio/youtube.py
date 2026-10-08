"""yt-dlp adapter: YouTube metadata/heatmap, authorized video, best-effort captions.

Keep subtitles separate from video download. A subtitle HTTP 429 must never
cause an already downloaded video to be discarded.
"""
from pathlib import Path
import json
import time

import yt_dlp

VIDEO_SUFFIXES = {'.mp4', '.mkv', '.webm', '.mov'}
SUBTITLE_SUFFIXES = {'.vtt', '.srt', '.ass'}
SUBTITLE_COOLDOWN_SECONDS = 3600


def inspect_url(url, cancel=lambda: False):
    if not url.startswith(('https://www.youtube.com/', 'https://youtube.com/', 'https://youtu.be/',
                           'https://m.youtube.com/')):
        raise ValueError('Hanya URL YouTube HTTPS yang didukung.')
    if cancel():
        raise RuntimeError('Operasi dibatalkan.')
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'noplaylist': True,
                           'skip_download': True, 'extract_flat': False}) as ydl:
        raw = ydl.extract_info(url, download=False)
    if not raw:
        raise ValueError('Metadata YouTube tidak tersedia.')
    return {
        'id': raw.get('id'), 'title': raw.get('title', 'Untitled'),
        'duration': raw.get('duration') or 0,
        'heatmap': raw.get('heatmap') or [], 'chapters': raw.get('chapters') or [],
        'subtitles_available': list((raw.get('subtitles') or {}).keys()),
        'auto_captions_available': list((raw.get('automatic_captions') or {}).keys()),
        'original_language': raw.get('language') or '',
        'webpage_url': raw.get('webpage_url') or url,
    }


def download_authorized(url, folder, video_id='', language='id', cancel=lambda: False, log=lambda x: None):
    """Download authorized video only. Subtitle retrieval is a separate operation."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    def hook(d):
        if cancel():
            raise RuntimeError('Operasi dibatalkan.')
        if d.get('status') == 'finished':
            log('Unduhan video selesai, menyiapkan file...')

    options = {
        'quiet': True, 'no_warnings': True, 'noplaylist': True,
        'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
        'merge_output_format': 'mp4', 'outtmpl': str(folder / 'source_%(id)s.%(ext)s'),
        # No writesubtitles/writeautomaticsub: a subtitle 429 must not fail video.
        'writesubtitles': False, 'writeautomaticsub': False,
        'progress_hooks': [hook], 'retries': 2, 'fragment_retries': 2,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])
    choices = [p for p in folder.glob('source_*') if p.suffix.lower() in VIDEO_SUFFIXES]
    if video_id:
        choices = [p for p in choices if p.stem == 'source_' + video_id]
    if not choices:
        raise FileNotFoundError('Video hasil yt-dlp tidak ditemukan. Cek FFmpeg dan akses video.')
    return max(choices, key=lambda p: p.stat().st_size)


def find_subtitle(folder, language='id', video_id=''):
    folder = Path(folder)
    # Never mix captions from unrelated video IDs in an existing workspace.
    stem = f'source_{video_id}.' if video_id else 'source_'
    files = [p for p in folder.glob(f'{stem}*') if p.suffix.lower() in SUBTITLE_SUFFIXES]
    if not files:
        return None

    def rank(p):
        n = p.name.lower()
        return (0 if f'.{language}.' in n else 1 if '.id.' in n else 2 if '.en.' in n else 3,
                0 if p.suffix == '.srt' else 1, len(n))

    return sorted(files, key=rank)[0]


def select_caption_track(metadata, preferred='id'):
    """Select one track, prioritize human captions; avoid translated auto-captions.

    The metadata's 'language' can be empty, so do not guess whether an
    automatically translated caption is the video's original audio language.
    """
    manual = metadata.get('subtitles_available') or []
    auto = metadata.get('auto_captions_available') or []
    original = metadata.get('original_language') or ''
    # Prefer a manually supplied transcript in the preferred language,
    # then the video's original language, then English when available.
    for lang in dict.fromkeys([preferred, 'id', original, 'en']):
        if lang and lang in manual:
            return lang, 'manual'
    # For automatic captions, select only original-language auto captions.
    # Otherwise YouTube may generate on-demand translations, often HTTP 429.
    if original and original in auto:
        return original, 'automatic'
    return None


def _cooldown_path(folder):
    # Shared among workspace projects of one AutoClip Studio installation.
    return Path(folder).parent / '.subtitle_rate_limit.json'


def subtitle_cooldown_remaining(folder, now=None):
    path = _cooldown_path(folder)
    if not path.is_file():
        return 0
    try:
        until = float(json.loads(path.read_text(encoding='utf-8'))['until'])
        return max(0, int(until - (time.time() if now is None else now)))
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def _record_subtitle_rate_limit(folder):
    path = _cooldown_path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'until': time.time() + SUBTITLE_COOLDOWN_SECONDS}), encoding='utf-8')


def fetch_best_subtitle(url, folder, metadata, language='id',
                        cancel=lambda: False, log=lambda x: None):
    """Best-effort subtitle fetch. Return None on unavailable/429, never retry 429.

    The caller must keep processing with Groq/local Whisper if the subtitle
    cannot be fetched. Never try to evade a provider's rate limits.
    """
    folder = Path(folder)
    video_id = metadata.get('id') or ''
    existing = find_subtitle(folder, language, video_id)
    if existing:
        log(f'Menggunakan subtitle tersimpan: {existing.name}')
        return existing
    selection = select_caption_track(metadata, language)
    if not selection:
        log('Subtitle original/manual tidak tersedia; lewati terjemahan otomatis YouTube.')
        return None
    remaining = subtitle_cooldown_remaining(folder)
    if remaining:
        log(f'Pengambilan subtitle ditunda akibat HTTP 429 sebelumnya (~{(remaining+59)//60} menit).')
        return None
    if cancel():
        raise RuntimeError('Operasi dibatalkan.')
    lang, kind = selection
    log(f'Mengambil satu track subtitle {lang} ({kind}) secara terpisah...')
    options = {
        'quiet': True, 'no_warnings': True, 'noplaylist': True,
        'skip_download': True,
        'outtmpl': str(folder / 'source_%(id)s.%(ext)s'),
        'writesubtitles': kind == 'manual',
        'writeautomaticsub': kind == 'automatic',
        'subtitleslangs': [lang],
        'subtitlesformat': 'vtt/best',
        'retries': 0, 'fragment_retries': 0,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as exc:
        message = str(exc)
        if '429' in message or 'Too Many Requests' in message:
            _record_subtitle_rate_limit(folder)
            log('Subtitle dibatasi YouTube (HTTP 429). Tidak mengulang permintaan; lanjut fallback transkripsi.')
        else:
            log(f'Gagal mengambil subtitle ({message[:160]}). Lanjut fallback transkripsi.')
        return None
    return find_subtitle(folder, lang, video_id)
