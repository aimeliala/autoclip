"""Regression coverage: YouTube 429 must not abort otherwise successful clipping."""
from pathlib import Path
import sys
import types
import pytest

# Unit-test suite must also run in minimal CI runners without external
# downloads. The application itself requires the real yt-dlp distribution.
try:
    import yt_dlp
except ModuleNotFoundError:
    fake = types.ModuleType('yt_dlp')
    class DownloadError(Exception):
        pass
    fake.utils = types.SimpleNamespace(DownloadError=DownloadError)
    fake.YoutubeDL = None
    sys.modules['yt_dlp'] = fake

from autoclip_studio import youtube


def test_video_download_does_not_request_subtitles(tmp_path, monkeypatch):
    calls = []

    class FakeYDL:
        def __init__(self, opts):
            calls.append(opts)
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def download(self, urls):
            (tmp_path / 'source_video123.mp4').write_bytes(b'video')
            return 0

    monkeypatch.setattr(youtube.yt_dlp, 'YoutubeDL', FakeYDL)
    path = youtube.download_authorized('https://www.youtube.com/watch?v=video123', tmp_path,
                                      'video123')
    assert path.name == 'source_video123.mp4'
    assert calls[0]['writesubtitles'] is False
    assert calls[0]['writeautomaticsub'] is False


def test_select_subtitle_prefers_single_manual_or_original_auto():
    assert youtube.select_caption_track({
        'subtitles_available': ['en', 'id'],
        'auto_captions_available': ['en', 'id'], 'original_language': 'en'
    }, 'id') == ('id', 'manual')
    assert youtube.select_caption_track({
        'subtitles_available': [],
        'auto_captions_available': ['en', 'id'], 'original_language': 'en'
    }, 'id') == ('en', 'automatic')
    assert youtube.select_caption_track({
        'subtitles_available': [],
        'auto_captions_available': ['en', 'id'], 'original_language': ''
    }, 'id') is None  # avoid auto-translation guesswork


def test_caption_429_is_nonfatal_and_applies_cooldown(tmp_path, monkeypatch):
    folder = tmp_path / 'projects' / 'abc123'
    folder.mkdir(parents=True)
    class FailingYDL:
        instances = 0
        def __init__(self, opts):
            self.opts = opts
            FailingYDL.instances += 1
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def download(self, _urls):
            raise youtube.yt_dlp.utils.DownloadError(
                "Unable to download video subtitles for 'en': HTTP Error 429: Too Many Requests"
            )
    monkeypatch.setattr(youtube.yt_dlp, 'YoutubeDL', FailingYDL)
    data = {'id': 'abc123', 'subtitles_available': ['en'],
            'auto_captions_available': [], 'original_language': 'en'}
    logs = []
    assert youtube.fetch_best_subtitle('https://youtu.be/abc123',folder,data,'id',log=logs.append) is None
    assert youtube.subtitle_cooldown_remaining(folder) > 0
    assert '429' in ' '.join(logs)
    assert youtube.fetch_best_subtitle('https://youtu.be/abc123',folder,data,'id',log=logs.append) is None
    assert FailingYDL.instances == 1  # do not hammer endpoint during cooldown


def test_existing_caption_skips_requests(tmp_path, monkeypatch):
    folder=tmp_path/'projects'/'abc'
    folder.mkdir(parents=True)
    existing=folder/'source_abc.id.vtt'
    existing.write_text('WEBVTT',encoding='utf-8')
    def die(_):
        raise AssertionError('YouTube call not expected for cached captions')
    monkeypatch.setattr(youtube.yt_dlp,'YoutubeDL',die)
    assert youtube.fetch_best_subtitle('https://youtu.be/abc',folder,{'id':'abc'},'id') == existing


def test_pipeline_continues_after_subtitle_429(tmp_path, monkeypatch):
    from autoclip_studio import pipeline
    from autoclip_studio.config import Settings
    import subprocess
    if not __import__('shutil').which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    source=tmp_path/'video.mp4'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi',
                    '-i','testsrc2=size=320x180:rate=8','-t','4',
                    '-c:v','mpeg4','-q:v','6',str(source)], check=True)
    meta={'id':'abc','title':'Test','duration':4,'heatmap':[], 'chapters':[],
          'subtitles_available':['en'],'auto_captions_available':[]}
    monkeypatch.setattr(pipeline.youtube,'inspect_url',lambda *args:meta.copy())
    monkeypatch.setattr(pipeline.youtube,'download_authorized',lambda *args,**kwargs:source)
    monkeypatch.setattr(pipeline.youtube,'fetch_best_subtitle',lambda *args,**kwargs:None)
    monkeypatch.setattr(pipeline,'transcribe_local',lambda *args,**kwargs: [
        {'start':0.,'end':2.,'text':'Transkripsi fallback berhasil'}
    ])
    settings=Settings(downloads_dir=str(tmp_path/'data'),speech='auto',ai_provider='off')
    logs=[]
    result=pipeline.analyze('https://www.youtube.com/watch?v=abc','',True,settings,logs.append)
    assert result['segments'][0]['text']=='Transkripsi fallback berhasil'
    assert result['clips']
