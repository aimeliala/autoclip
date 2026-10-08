"""Local FFmpeg vertical export with optional captions and CPU face-centred framing."""
from pathlib import Path
import json
from .media import run_process, crop_rectangle, face_center, probe_video, require_subtitle_filter
from .smart_reframe import sample_face_track, write_crop_commands
from .transcript import srt_for_clip


def render_clips(analysis, clips, settings, profile_settings, log, cancel=lambda: False):
    source = Path(analysis['source'])
    if not source.exists():
        raise FileNotFoundError(f'File video tidak ditemukan: {source}')
    dimensions = probe_video(source, settings.ffprobe)
    out_dir = Path(analysis['workspace']) / 'exports'
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    subtitles_checked = False
    for i, c in enumerate(clips, 1):
        if cancel():
            raise RuntimeError('Operasi dibatalkan.')
        start, end = float(c['start']), float(c['end'])
        if not (0 <= start < end <= dimensions['duration']+.5):
            raise ValueError(f'Clip {i}: timestamp di luar durasi video.')
        target = out_dir / f'clip_{i:02d}_{int(start)}s.mp4'
        # Dynamic face tracking uses a small sampled stream rather than a heavy
        # per-frame model. If no face is detected, gracefully fall back to center crop.
        x, y, w, h = crop_rectangle(dimensions['width'], dimensions['height'])
        track = []
        if settings.smart_crop:
            log(f'Clip {i}/{len(clips)}: melacak wajah secara temporal (CPU)...')
            duration = end - start
            interval = max(0.55, min(2.0, duration / max(2, profile_settings['vision_samples'])))
            track = sample_face_track(source, start, end, interval=interval, cancel=cancel)
            if track:
                x, y, w, h = crop_rectangle(dimensions['width'], dimensions['height'], track[0][1], None)
            else:
                log('Wajah tidak ditemukan; memakai center crop.')
        resolution = min(int(settings.output_resolution), profile_settings['resolution'])
        if settings.profile != 'auto':
            resolution = int(settings.output_resolution)
        render_work = out_dir / f'.render_{i:02d}'
        render_work.mkdir(parents=True, exist_ok=True)
        subtitle_file = render_work / 'captions.srt'
        with_subtitles = settings.captions and srt_for_clip(analysis.get('segments',[]),
                                                             start,end,subtitle_file)
        if with_subtitles and not subtitles_checked:
            require_subtitle_filter(settings.ffmpeg)
            subtitles_checked = True
        if track and dimensions['width'] > w:
            write_crop_commands(track, width=dimensions['width'], crop_width=w,
                                duration=end-start, output=render_work/'pan.cmd')
            crop_filter = f'sendcmd=f=pan.cmd,crop@pan={w}:{h}:{x}:{y}'
        else:
            crop_filter = f'crop={w}:{h}:{x}:{y}'
        filters = ['setpts=PTS-STARTPTS', crop_filter,
                   f'scale={resolution}:{round(resolution*16/9)//2*2}:flags=bicubic', 'setsar=1']
        if with_subtitles:
            filters.append("subtitles=filename=captions.srt:force_style='FontName=Arial,FontSize=22,Outline=2,Shadow=0,MarginV=95,Alignment=2'")
        args = [settings.ffmpeg, '-y', '-hide_banner', '-loglevel', 'error',
                '-ss',str(start),'-i',str(source),'-t',str(end-start),
                '-map','0:v:0','-map','0:a:0?', '-vf',','.join(filters),
                '-c:v','libx264','-preset','veryfast','-crf','23',
                '-pix_fmt','yuv420p','-c:a','aac','-b:a','128k',
                '-movflags','+faststart',str(target.absolute())]
        log(f'Render clip {i}/{len(clips)} → {target.name}')
        run_process(args,cwd=render_work,cancel=cancel)
        results.append(target)
    return results
