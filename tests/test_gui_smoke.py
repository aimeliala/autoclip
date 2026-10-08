"""Actual Qt widget construction test when PySide6 and an offscreen backend exist."""
import os
import pytest


def test_studio_constructs_and_has_timeline(tmp_path, monkeypatch):
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    import autoclip_studio.app as desktop
    from autoclip_studio.config import Settings
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    monkeypatch.setattr(desktop, 'load_settings', lambda: Settings(downloads_dir=str(tmp_path)))
    monkeypatch.setattr(desktop, 'get_secret', lambda _: '')
    monkeypatch.setattr(desktop, 'hardware_report', lambda: {
        'ram_gb': 16, 'cpu_logical': 8, 'cpu_physical': 4, 'cpu': 'Test',
        'gpu': 'Test', 'platform': 'Darwin', 'recommended': 'balanced'
    })
    qt = QApplication.instance() or QApplication([])
    window = desktop.StudioWindow()
    assert window.stack.count() == 3
    assert window.timeline_slider.minimum() == 0
    assert window.face_check.isChecked()
    assert window.media_player is None or window.media_player.duration() >= 0
    window.close()
