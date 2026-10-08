@echo off
python -m pip install -e ".[dev]"
python -m PyInstaller --noconfirm --clean --windowed --onedir --name AutoClipStudio --collect-all yt_dlp --collect-all pysubs2 scripts\launch.py
pause
