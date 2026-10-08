"""CPU-friendly temporal face reframe for vertical exports.

This is visual face tracking, NOT verified audio/visual active-speaker identification.
The clip remains usable without OpenCV or when faces cannot be detected.
"""
from __future__ import annotations

from pathlib import Path
import bisect
import math


def smooth_positions(observations, width, *, alpha=0.38, max_speed_ratio=0.23):
    """Keep stable face identity, suppress jitter, and limit camera movement."""
    if not observations:
        return []
    ordered = sorted(observations, key=lambda p: p[0])
    last_t, last_x = float(ordered[0][0]), min(width, max(0., float(ordered[0][1])))
    out = [(last_t, last_x)]
    for t, x in ordered[1:]:
        t = float(t)
        if t <= last_t:
            continue
        x = min(width, max(0., float(x)))
        candidate = last_x + alpha * (x - last_x)
        limit = width * max_speed_ratio * (t - last_t)
        value = max(last_x - limit, min(last_x + limit, candidate))
        out.append((t, value))
        last_t, last_x = t, value
    return out


def camera_x_at(track, at, source_width, crop_width):
    """Interpolate a camera center on a time-relative track."""
    if not track:
        return (source_width - crop_width) // 2
    times = [t for t, _ in track]
    index = bisect.bisect_right(times, at)
    if index == 0:
        center = track[0][1]
    elif index == len(track):
        center = track[-1][1]
    else:
        ta, xa = track[index - 1]
        tb, xb = track[index]
        fraction = (at - ta) / (tb - ta) if tb > ta else 0
        center = xa + (xb - xa) * fraction
    x = round(center - crop_width / 2)
    return max(0, min(source_width - crop_width, x))


def sample_face_track(source, start, end, *, interval=1.2, max_frames=150, cancel=lambda: False):
    """Sample decoded frames at bounded rate with OpenCV's bundled Haar cascade.

    Returns time-relative (seconds, face-center-x) points. Memory is bounded to
    one decoded frame; no cloud requests. Tracking prioritizes the previous face.
    """
    try:
        import cv2
    except ImportError:
        return []
    capture = cv2.VideoCapture(str(source))
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    detector = cv2.CascadeClassifier(cascade_path)
    if not capture.isOpened() or detector.empty():
        capture.release()
        return []
    points = []
    last_center = None
    missing = 0
    duration = max(0., float(end) - float(start))
    steps = max(1, min(max_frames, math.ceil(duration / interval)))
    try:
        for idx in range(steps + 1):
            if cancel():
                raise RuntimeError('Operasi dibatalkan.')
            rel_t = duration * idx / steps
            capture.set(cv2.CAP_PROP_POS_MSEC, (start + rel_t) * 1000)
            ok, frame = capture.read()
            if not ok:
                continue
            fh, fw = frame.shape[:2]
            if fw < 1 or fh < 1:
                continue
            ratio = min(1.0, 512 / fw)
            resized = cv2.resize(frame, None, fx=ratio, fy=ratio) if ratio != 1 else frame
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=4,
                                              minSize=(25, 25))
            centers = [((x + w / 2) / ratio, w * h) for x, y, w, h in faces]
            if centers:
                if last_center is not None and missing < 3:
                    closest = min(centers, key=lambda item: abs(item[0] - last_center))
                    # Avoid switching faces when a distant participant takes over.
                    if abs(closest[0] - last_center) < fw * 0.3:
                        chosen = closest
                    else:
                        chosen = (last_center, 0)
                else:
                    chosen = max(centers, key=lambda item: item[1])
                last_center = float(chosen[0])
                missing = 0
            else:
                missing += 1
            if last_center is not None:
                points.append((round(rel_t, 3), last_center))
    finally:
        capture.release()
    return smooth_positions(points, fw) if points else []


def write_crop_commands(track, *, width, crop_width, duration, output, fps=5):
    """Generate sendcmd data to interpolate camera movement without Python per-frame rendering.

    Caller must set cwd to output.parent and use `sendcmd=f=pan.cmd,crop@pan=...`.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not track:
        return None
    lines = []
    last_x = None
    frame_count = max(1, math.ceil(duration * fps))
    for step in range(frame_count):
        t = step / fps
        x = camera_x_at(track, t, width, crop_width)
        if last_x is None or x != last_x:
            # FFmpeg 0 timestamp is valid, and names explicitly target the crop instance.
            lines.append(f'{t:.3f} crop@pan x {x};')
            last_x = x
    output.write_text('\n'.join(lines) + '\n', encoding='ascii')
    return output
