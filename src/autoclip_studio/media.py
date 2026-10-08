"""FFprobe/FFmpeg operations; bounded memory and cancellable child processes."""
import json
from pathlib import Path
import subprocess
import tempfile
import time


def probe_video(source, ffprobe='ffprobe'):
    proc = subprocess.run([ffprobe, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams',
                           str(source)], capture_output=True, text=True, timeout=25, check=True)
    data = json.loads(proc.stdout)
    video = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not video:
        raise ValueError('File tidak memiliki stream video.')
    return {
        'width': int(video.get('width') or 0), 'height': int(video.get('height') or 0),
        'duration': float(data.get('format', {}).get('duration') or video.get('duration') or 0),
    }


def run_process(args, *, cwd=None, cancel=lambda: False):
    """Capture stderr to temporary disk, avoiding subprocess pipe deadlocks."""
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen([str(a) for a in args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=err)
        while proc.poll() is None:
            if cancel():
                proc.terminate()
                try:
                    proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                raise RuntimeError('Operasi dibatalkan.')
            time.sleep(0.15)
        if proc.returncode:
            err.seek(0)
            message = err.read().decode('utf-8', errors='replace')[-2500:]
            raise RuntimeError('FFmpeg gagal: ' + message)


def require_subtitle_filter(ffmpeg='ffmpeg'):
    """Check the selected binary; FFmpeg may exit successfully for unknown filters."""
    proc = subprocess.run([str(ffmpeg), '-hide_banner', '-filters'],
                          capture_output=True, text=True, timeout=25, check=True)
    if not any(len(parts := line.split()) >= 2 and parts[1] == 'subtitles'
               for line in proc.stdout.splitlines()):
        raise RuntimeError(
            f"FFmpeg '{ffmpeg}' tidak memiliki filter subtitles (libass), "
            "yang diperlukan untuk captions. Di macOS: brew install ffmpeg-full, "
            "lalu atur FFmpeg executable ke hasil brew --prefix ffmpeg-full "
            "ditambah /bin/ffmpeg. Atau nonaktifkan captions untuk ekspor tanpa subtitle.")


def extract_audio_parts(source, folder, ffmpeg='ffmpeg', duration=0, cancel=lambda: False):
    """10-minute MP3 mono chunks to keep API uploads below common size limits."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if duration <= 0:
        raise ValueError('Durasi video tidak valid.')
    results = []
    for index in range(int((duration - 0.001) // 600) + 1):
        start = index * 600
        path = folder / f'audio_{index:03d}.mp3'
        if not path.exists():
            run_process([ffmpeg, '-y', '-hide_banner', '-loglevel', 'error',
                         '-ss', str(start), '-i', str(source), '-t', str(min(600, duration-start)),
                         '-vn', '-ac', '1', '-ar', '16000', '-b:a', '48k', str(path)], cancel=cancel)
        results.append((start, path))
    return results


def crop_rectangle(width, height, center_x=None, center_y=None):
    if width < 1 or height < 1:
        raise ValueError('Resolusi video tidak valid.')
    ratio = 9 / 16
    if width / height >= ratio:
        h, w = height, int(height * ratio)
    else:
        w, h = width, int(width / ratio)
    w, h = max(2, w - w % 2), max(2, h - h % 2)
    x = int((center_x if center_x is not None else width / 2) - w / 2)
    y = int((center_y if center_y is not None else height / 2) - h / 2)
    return (max(0, min(width - w, x)), max(0, min(height - h, y)), w, h)


def face_center(source, start, end, samples=7):
    """CPU-only single-point face-aware crop; not speaker diarization."""
    try:
        import cv2
    except ImportError:
        return None
    capture = cv2.VideoCapture(str(source))
    classifier = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    centers = []
    try:
        for i in range(samples):
            t = start + (end - start) * (i + .5) / max(1, samples)
            capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = capture.read()
            if not ok:
                continue
            height, width = frame.shape[:2]
            frame_small = cv2.resize(frame, (min(640, width), int(height * min(640, width) / width)))
            gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
            faces = classifier.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=4,
                                                 minSize=(24, 24))
            if len(faces):
                x, y, w, h = max(faces, key=lambda f: f[2]*f[3])
                factor = width / frame_small.shape[1]
                centers.append(((x + w / 2) * factor, (y + h / 2) * factor))
    finally:
        capture.release()
    if not centers:
        return None
    centers.sort(key=lambda pair: pair[0])
    return centers[len(centers)//2]
