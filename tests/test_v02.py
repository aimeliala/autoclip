"""Regression tests for macOS-ready lightweight engine and dynamic reframe."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

import pytest

from autoclip_studio.config import config_root
from autoclip_studio.media import probe_video
from autoclip_studio.smart_reframe import camera_x_at, smooth_positions, write_crop_commands


def test_camera_track_interpolation_and_bounds():
    assert camera_x_at([(0, 90), (2, 290)], 0, 320, 100) == 40
    assert camera_x_at([(0, 90), (2, 290)], 1, 320, 100) == 140
    assert camera_x_at([(0, 90), (2, 290)], 3, 320, 100) == 220
    assert camera_x_at([], 0, 320, 100) == 110


def test_camera_track_speed_limit():
    trajectory = smooth_positions([(0, 40), (0.5, 600), (1, 300)], width=800,
                                  alpha=1, max_speed_ratio=.2)
    assert len(trajectory) == 3
    assert trajectory[1][1] == pytest.approx(120)
    assert trajectory[2][1] == pytest.approx(200)


def test_ffmpeg_dynamic_crop_command_file(tmp_path):
    result = write_crop_commands([(0, 90), (1, 220)], width=320,
                                 crop_width=100, duration=1.5, output=tmp_path/'pan.cmd')
    lines = result.read_text().strip().splitlines()
    assert len(lines) >= 2
    assert lines[0].startswith('0.000 crop@pan x')
    assert lines[-1].endswith(';')
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    # Commands must parse correctly as a real runtime crop filter.
    video = tmp_path/'moving.mp4'
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',
                    '-f','lavfi','-i','testsrc2=size=320x180:rate=8',
                    '-t','1.5','-vf',
                    'setpts=PTS-STARTPTS,sendcmd=f=pan.cmd,crop@pan=100:180:40:0,scale=180:320',
                    '-c:v','mpeg4',str(video)], cwd=tmp_path,check=True)
    assert probe_video(video)['height'] == 320


def test_render_uses_moving_crop_when_track_present(tmp_path, monkeypatch):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    import autoclip_studio.render as rendering
    from autoclip_studio.config import Settings
    from autoclip_studio.hardware import profile_defaults
    source = tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',
                    '-f','lavfi','-i','testsrc2=size=320x180:rate=10',
                    '-t','2','-c:v','mpeg4','-q:v','4',str(source)],check=True)
    monkeypatch.setattr(rendering,'sample_face_track',
                        lambda *args, **kwargs: [(0, 90), (2, 240)])
    analysis = {'source':str(source),'workspace':str(tmp_path),'segments':[]}
    settings = Settings(smart_crop=True,captions=False,output_resolution=720)
    out = rendering.render_clips(analysis,[{'start':0,'end':1.7}],
                                 settings,profile_defaults('economy'),lambda _:None)
    assert out[0].is_file() and out[0].stat().st_size > 1000
    assert (tmp_path/'exports'/'.render_01'/'pan.cmd').exists()
    assert probe_video(out[0])['width'] == 720


def test_mac_config_uses_application_support(monkeypatch):
    import autoclip_studio.config as conf
    monkeypatch.setattr(conf.platform,'system',lambda: 'Darwin')
    assert 'Library/Application Support/AutoClip Studio' in str(conf.config_root())
