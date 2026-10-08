"""Orchestrator: yt-dlp → captions/ASR → heatmap ranking → optional LLM."""
import hashlib
import json
from pathlib import Path
import shutil

from . import youtube
from .config import get_secret
from .hardware import hardware_report, effective_profile, profile_defaults
from .media import probe_video
from .transcript import load_subtitles, transcribe_groq, transcribe_local
from .highlights import candidates_from_signals, rerank_with_llm


def _json(path, value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def analyze(input_value, subtitle_path, authorized, settings, log, cancel=lambda: False):
    url_mode = input_value.strip().startswith(('https://','http://'))
    work_id = hashlib.sha256(input_value.strip().encode('utf-8')).hexdigest()[:12]
    workspace = Path(settings.downloads_dir).expanduser() / 'projects' / work_id
    workspace.mkdir(parents=True,exist_ok=True)
    metadata = {}
    if url_mode:
        if not authorized:
            raise ValueError('Untuk mengunduh sumber YouTube, konfirmasi hak/izin pemrosesan.')
        log('yt-dlp: mengambil informasi YouTube dan heatmap ...')
        metadata = youtube.inspect_url(input_value,cancel)
        files = [p for p in workspace.glob('source_*') if p.suffix.lower() in youtube.VIDEO_SUFFIXES]
        if files:
            source = max(files,key=lambda p:p.stat().st_size)
            log('Menggunakan video unduhan yang sudah tersimpan.')
        else:
            log('yt-dlp: menyiapkan file video yang diizinkan ...')
            source = youtube.download_authorized(input_value,workspace,metadata['id'],
                                                 settings.language,cancel,log)
    else:
        source = Path(input_value).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError('Pilih file video lokal yang ada.')
    properties = probe_video(source,settings.ffprobe)
    duration = properties['duration']
    if duration <= 0:
        raise ValueError('Durasi video tidak valid.')
    if not metadata:
        metadata = {'title':source.stem,'duration':duration,'heatmap':[], 'chapters':[]}
    else:
        metadata['duration'] = duration
    profile = effective_profile(settings,hardware_report())
    preset = profile_defaults(profile)
    log(f'Profil: {profile}, video: {int(duration)} detik, heatmap: {len(metadata.get("heatmap",[]))} poin')
    cached = workspace / 'transcript.json'
    segments = []
    if subtitle_path:
        log('Memuat subtitle pengguna ...')
        segments = load_subtitles(subtitle_path, settings.ffmpeg)
    elif cached.exists():
        segments = json.loads(cached.read_text(encoding='utf-8'))
        log('Menggunakan transkrip dari cache.')
    elif settings.speech != 'none':
        if url_mode and settings.speech in ('auto', 'subtitles'):
            sub = youtube.fetch_best_subtitle(input_value, workspace, metadata,
                                              settings.language, cancel, log)
        else:
            sub = None
        if sub:
            try:
                segments = load_subtitles(sub, settings.ffmpeg)
                log(f'Subtitle yt-dlp: {sub.name}')
            except Exception as ex:
                log(f'Subtitle tidak terbaca: {ex}')
        if not segments and settings.speech != 'subtitles':
            from .config import get_secret
            groq = get_secret('groq')
            if settings.speech == 'groq' or (settings.speech == 'auto' and groq):
                segments = transcribe_groq(source,workspace,duration,settings,groq,log,cancel)
            elif settings.speech in ('local','auto'):
                try:
                    segments = transcribe_local(source,workspace,duration,settings,preset,log,cancel)
                except RuntimeError as ex:
                    if settings.speech == 'local':
                        raise
                    log(f'Transkripsi offline tidak tersedia: {ex}. Analisis tanpa subtitle.')
    if segments:
        _json(cached,segments)
    else:
        log('Tidak ada transkrip. Fallback heatmap/chapters/timeline; caption tidak tersedia.')
    pool = candidates_from_signals(duration,metadata.get('heatmap',[]),segments,
                                   metadata.get('chapters',[]),
                                   count=max(12,settings.max_clips*3),length=settings.clip_length)
    if settings.ai_provider != 'off':
        log('AI: menilai kandidat klip berdasarkan percakapan ...')
        try:
            provider_secret = get_secret(settings.ai_provider)
            pool = rerank_with_llm(pool,segments,settings,provider_secret,log)
        except Exception as ex:
            log(f'AI gagal, menggunakan ranking lokal: {str(ex)[:240]}')
    # No highly-overlapping final suggestions.
    chosen = []
    for c in sorted(pool,key=lambda c:c.score,reverse=True):
        if all(max(0,min(c.end,other.end)-max(c.start,other.start)) < .45*settings.clip_length
               for other in chosen):
            chosen.append(c)
        if len(chosen) >= settings.max_clips:
            break
    clips = [c.data() for c in sorted(chosen,key=lambda c:c.start)]
    analysis = {'source':str(source),'workspace':str(workspace),'metadata':metadata,
                'segments':segments,'clips':clips,'duration':duration,'profile':profile}
    _json(workspace/'analysis.json',analysis)
    log(f'Selesai: {len(clips)} kandidat klip, {len(segments)} baris transkrip.')
    return analysis
