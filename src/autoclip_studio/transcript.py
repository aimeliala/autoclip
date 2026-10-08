"""Subtitle-first transcription. Paid API and CPU Whisper are fallbacks."""
from pathlib import Path
import json
import requests

from .media import extract_audio_parts, run_process


def load_subtitles(path, ffmpeg='ffmpeg'):
    import pysubs2
    path = Path(path)
    try:
        subs = pysubs2.load(str(path))
    except Exception:
        srt = path.with_suffix('.converted.srt')
        run_process([ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-i', str(path), str(srt)])
        subs = pysubs2.load(str(srt))
    segments = []
    for line in subs:
        text = line.plaintext.strip().replace('\n', ' ')
        if text and line.end > line.start:
            segments.append({'start': round(line.start/1000, 3),
                             'end': round(line.end/1000, 3), 'text': text})
    return segments


def transcribe_groq(source, folder, duration, settings, api_key, log, cancel=lambda: False):
    if not api_key:
        raise ValueError('API key Groq belum diisi di Pengaturan.')
    parts = extract_audio_parts(source, Path(folder)/'audio', settings.ffmpeg, duration, cancel)
    output = []
    for index, (offset, path) in enumerate(parts):
        if cancel():
            raise RuntimeError('Operasi dibatalkan.')
        log(f'Transkripsi Groq: audio {index+1}/{len(parts)}')
        with open(path, 'rb') as fp:
            response = requests.post('https://api.groq.com/openai/v1/audio/transcriptions',
                                     headers={'Authorization': f'Bearer {api_key}'},
                                     data=[('model', settings.groq_model),
                                           ('language', settings.language),
                                           ('response_format', 'verbose_json'),
                                           ('timestamp_granularities[]', 'segment'),
                                           ('timestamp_granularities[]', 'word')],
                                     files={'file': (path.name, fp, 'audio/mpeg')}, timeout=180)
        if not response.ok:
            raise RuntimeError(f'Groq HTTP {response.status_code}: {response.text[:350]}')
        data = response.json()
        raw_segments = data.get('segments') or []
        if raw_segments:
            for s in raw_segments:
                if s.get('text', '').strip():
                    output.append({'start': round(offset + float(s['start']), 3),
                                   'end': round(offset + float(s['end']), 3),
                                   'text': s['text'].strip()})
        else:
            words = data.get('words') or []
            for start in range(0, len(words), 6):
                group = words[start:start+6]
                if group:
                    output.append({'start': offset + float(group[0]['start']),
                                   'end': offset + float(group[-1]['end']),
                                   'text': ' '.join(w.get('word', '').strip() for w in group)})
    return sorted(output, key=lambda s: s['start'])


def transcribe_local(source, folder, duration, settings, profile_config, log, cancel=lambda: False):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError('Untuk transkripsi offline: pip install -e ".[local-asr]"') from exc
    parts = extract_audio_parts(source, Path(folder)/'audio', settings.ffmpeg, duration, cancel)
    model_name = profile_config['whisper_model']
    log(f'Memuat faster-whisper {model_name} INT8 (CPU)')
    model = WhisperModel(model_name, device='cpu', compute_type='int8',
                         cpu_threads=profile_config['cpu_threads'])
    results = []
    for index, (offset, path) in enumerate(parts):
        if cancel():
            raise RuntimeError('Operasi dibatalkan.')
        log(f'Transkripsi lokal {index+1}/{len(parts)}')
        segments, _ = model.transcribe(str(path), language=settings.language,
                                       vad_filter=True, beam_size=3)
        for s in segments:
            if s.text.strip():
                results.append({'start': round(offset + s.start, 3),
                                'end': round(offset + s.end, 3), 'text': s.text.strip()})
    return results


def srt_for_clip(segments, start, end, target):
    import pysubs2
    subs = pysubs2.SSAFile()
    for s in segments:
        left, right = max(float(s['start']), start), min(float(s['end']), end)
        if right <= left or not s['text'].strip():
            continue
        subs.events.append(pysubs2.SSAEvent(start=max(0, int((left-start)*1000)),
                                          end=int((right-start)*1000), text=s['text']))
    if subs.events:
        subs.save(str(target), format_='srt')
        return True
    return False
