"""Subtitle capability errors and real caption export regression coverage."""
import shutil
import subprocess

import pytest

from autoclip_studio.config import Settings
from autoclip_studio.hardware import profile_defaults
from autoclip_studio.media import require_subtitle_filter, probe_video
from autoclip_studio.render import render_clips


def test_missing_subtitles_reports_fix(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 0, ' ... scale V->V Scale\n', ''))
    with pytest.raises(RuntimeError, match='brew install ffmpeg-full'):
        require_subtitle_filter('/custom/ffmpeg')


def test_caption_export(tmp_path, monkeypatch):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('ffmpeg unavailable')
    source = tmp_path / 'source.mp4'
    subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'color=c=black:size=320x180:rate=8', '-t', '1',
                    '-c:v', 'mpeg4', str(source)], check=True)
    analysis = {'source': str(source), 'workspace': str(tmp_path / "Project's folder"),
                'segments': [{'start': 0, 'end': 1, 'text': 'Caption test'}]}
    settings = Settings(smart_crop=False, captions=True, output_resolution=360)
    try:
        require_subtitle_filter(ffmpeg)
    except RuntimeError:
        # Exercise the actual failing local build, without dropping captions silently.
        with pytest.raises(RuntimeError, match='tidak memiliki filter subtitles'):
            render_clips(analysis, [{'start': 0, 'end': 1}], settings,
                         profile_defaults('economy'), lambda _: None)
        assert not list(tmp_path.rglob('clip_*.mp4'))
        return
    paths = render_clips(analysis, [{'start': 0, 'end': 1}], settings,
                         profile_defaults('economy'), lambda _: None)
    assert probe_video(paths[0])['width'] == 360
    frame = subprocess.run([ffmpeg, '-loglevel', 'error', '-i', str(paths[0]),
                            '-frames:v', '1', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'],
                           capture_output=True, check=True).stdout
    assert max(frame) > 150  # White caption glyphs appear on the black source.
