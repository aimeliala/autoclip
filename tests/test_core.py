from pathlib import Path
import json
import os
import subprocess
import sys
import types
import pytest
from autoclip_studio.config import Settings, save_settings, load_settings
from autoclip_studio.highlights import heatmap_score, candidates_from_signals, parse_time
from autoclip_studio.media import crop_rectangle, probe_video
from autoclip_studio.hardware import profile_defaults, effective_profile


def test_weighted_heatmap():
    x = [{'start_time':0,'end_time':10,'value':.2},
         {'start_time':10,'end_time':20,'value':.8}]
    assert heatmap_score(x,5,15) == .5
    assert heatmap_score(x,30,40) == 0


def test_scoring_selects_replay():
    points=[{'start_time':i*5,'end_time':(i+1)*5,'value':1 if i in (8,9) else .05}
            for i in range(24)]
    result=candidates_from_signals(120, points, [],count=2,length=20)
    assert any(30<=c.start<=50 for c in result)
    assert len(result) == 2


def test_short_video_has_candidate():
    res=candidates_from_signals(6,[],[],count=5,length=50)
    assert len(res)==1
    assert res[0].start==0
    assert res[0].end==6


def test_crop_bounds():
    x,y,w,h=crop_rectangle(1920,1080,1900,500)
    assert x+w<=1920 and y+h<=1080 and abs(w/h-.5625)<.005
    x,y,w,h=crop_rectangle(1080,1920)
    assert x>=0 and y>=0 and w<=1080 and h<=1920


def test_time_parsing():
    assert parse_time('01:02:03') == 3723
    assert parse_time('01:23') == 83
    with pytest.raises(ValueError):parse_time('1:2:3:4')


def test_settings_does_not_persist_secrets(tmp_path):
    settings=Settings()
    settings.profile='economy'
    p=tmp_path/'config.json'
    save_settings(settings,p)
    assert load_settings(p).profile=='economy'
    assert 'api_key' not in p.read_text()


def test_hardware_profiles():
    assert profile_defaults('economy')['resolution']==720
    assert effective_profile(Settings(),{'recommended':'balanced'})=='balanced'


def test_ffmpeg_roundtrip(tmp_path):
    # Test offline rendering, no network or provider keys.
    if not __import__('shutil').which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    video=tmp_path/'sample.mp4'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi',
                    '-i','testsrc2=size=320x180:rate=8','-f','lavfi',
                    '-i','sine=frequency=300:sample_rate=16000', '-t','2',
                    '-c:v','mpeg4','-q:v','5','-c:a','aac',str(video)],check=True)
    meta=probe_video(video)
    assert meta['width']==320 and meta['duration']>=1.9
    from autoclip_studio.render import render_clips
    prefs=Settings(smart_crop=False,captions=False, output_resolution=720)
    analysis={'source':str(video),'workspace':str(tmp_path),
              'segments':[]}
    paths=render_clips(analysis,[{'start':0,'end':1.0}],prefs,profile_defaults('economy'),print)
    assert paths[0].exists() and paths[0].stat().st_size>5000
    assert probe_video(paths[0])['width']==720


def test_local_pipeline_end_to_end_without_api(tmp_path, monkeypatch):
    """Offline file path through pipeline: no youtube calls or API credentials."""
    import types
    monkeypatch.setitem(sys.modules,'yt_dlp',types.ModuleType('yt_dlp'))
    from autoclip_studio.pipeline import analyze
    video=tmp_path/'offline.mp4'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi',
                    '-i','testsrc2=size=320x180:rate=8','-t','4',
                    '-c:v','mpeg4','-q:v','6',str(video)],check=True)
    settings=Settings(downloads_dir=str(tmp_path/'data'),speech='none',
                      ai_provider='off',max_clips=3)
    report=analyze(str(video),'',False,settings,lambda _:None)
    assert report['clips']
    assert Path(report['workspace'],'analysis.json').is_file()
    assert report['metadata']['heatmap']==[]
