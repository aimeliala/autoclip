"""PySide6 desktop interface for AutoClip Studio (Windows / Linux / macOS)."""
import sys
import threading
from pathlib import Path
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QLabel, QPushButton, QLineEdit,
    QHBoxLayout, QVBoxLayout, QGridLayout, QFormLayout, QComboBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QPlainTextEdit,
    QFileDialog, QStackedWidget, QFrame, QCheckBox, QSpinBox,
    QProgressBar, QMessageBox, QHeaderView, QScrollArea, QSizePolicy, QSlider
)
from .config import Settings, get_secret, set_secret, load_settings, save_settings
from .hardware import hardware_report, effective_profile
from .youtube import inspect_url
from .pipeline import analyze
from .render import render_clips
from .highlights import format_time, parse_time

THEME = """
QWidget { background: #0B1020; color: #E9EEFC; font-family: 'Segoe UI', 'DejaVu Sans', sans-serif; font-size: 12px; }
QMainWindow { background: #090F1D; }
QFrame#sidebar { background: #11192C; border-right: 1px solid #24334F; }
QFrame#card { background: #151F34; border: 1px solid #28364F; border-radius: 14px; }
QFrame#soft { background: #101B30; border: 1px solid #273650; border-radius: 11px; }
QLabel#title { color: white; font-size: 26px; font-weight: 750; }
QLabel#subtitle { color: #A1AFCB; font-size: 12px; }
QLabel#h2 { color: #F1F5FF; font-size: 16px; font-weight: 700; }
QLabel#muted { color: #99A8C3; }
QLabel#tag { background: #173A3D; color: #6EE7C0; padding: 6px 10px; border-radius: 9px; }
QPushButton { border: 1px solid #30405D; background: #202D47; color: #EFF4FE;
              border-radius: 9px; padding: 10px 14px; font-weight: 600; }
QPushButton:hover { background: #2B3D5E; border-color: #617FA8; }
QPushButton:pressed { background: #182840; }
QPushButton:disabled { background: #1A2436; color: #61708C; border-color: #263147; }
QPushButton#primary { background: #20BCA0; color: #061A21; border: 1px solid #20BCA0; }
QPushButton#primary:hover { background: #4DD8BA; }
QPushButton#nav { border: none; text-align: left; background: transparent; color: #A9B8D6;
                  font-size: 13px; padding: 13px 18px; }
QPushButton#nav:hover { background: #24324D; color: white; }
QPushButton#nav:checked { background: #183D47; border-left: 3px solid #2CE0BE; color: white; }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {
  background: #0E172A; border: 1px solid #34435E; border-radius: 8px;
  padding: 9px 11px; color: #F0F4FD; selection-background-color: #1BB89B;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #20BCA0; }
QComboBox QAbstractItemView { background: #192640; color: white; selection-background-color: #245F68; }
QCheckBox { spacing: 8px; color: #C8D3E9; }
QCheckBox::indicator { width: 16px; height: 16px; }
QTableWidget { background: #111B2E; border: 1px solid #283850; border-radius: 10px;
    gridline-color: #293751; alternate-background-color: #18243B; }
QTableWidget::item { padding: 7px; }
QTableWidget::item:selected { background: #204756; color: white; }
QHeaderView::section { background: #1C2942; color: #B6C7E1; padding: 9px;
    border: 0px; border-right: 1px solid #293851; font-weight: 700; }
QScrollArea { border: none; }
QScrollBar:vertical { width: 9px; background: #101827; }
QScrollBar::handle:vertical { background: #3A4C69; border-radius: 4px; min-height: 20px; }
QProgressBar { border: 1px solid #2D3A56; background: #111B2E; color: white;
    border-radius: 7px; height: 13px; text-align: center; }
QProgressBar::chunk { background: #21C8A5; border-radius: 6px; }
"""


def label(text, name=None, wrap=False):
    x = QLabel(text)
    if name: x.setObjectName(name)
    x.setWordWrap(wrap)
    return x


def card_layout(layout=None):
    frame = QFrame()
    frame.setObjectName('card')
    box = layout or QVBoxLayout()
    box.setContentsMargins(17,16,17,16)
    box.setSpacing(10)
    frame.setLayout(box)
    return frame, box


class HeatmapView(QWidget):
    def __init__(self):
        super().__init__()
        self.points = []
        self.setMinimumHeight(116)
        self.setMaximumHeight(140)

    def set_points(self, points):
        self.points = points or []
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor('#101B30'))
        p.setPen(QPen(QColor('#263651'),1))
        for fraction in (.25,.5,.75):
            y = int(h*(1-fraction))
            p.drawLine(6,y,w-6,y)
        valid = [v for v in self.points if isinstance(v,dict) and 'value' in v]
        if not valid:
            p.setPen(QColor('#91A5C3'))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       'Heatmap belum tersedia untuk video ini')
            p.end()
            return
        valid.sort(key=lambda v: float(v.get('start_time') or 0))
        max_end = max(float(x.get('end_time') or 0) for x in valid) or 1
        line = QPainterPath()
        start_x = 6
        line.moveTo(start_x,h-10)
        for v in valid:
            center = (float(v.get('start_time') or 0)+float(v.get('end_time') or 0))/2
            value = max(0,min(1,float(v.get('value') or 0)))
            line.lineTo(6+(w-12)*center/max_end, h-12-(h-26)*value)
        p.setPen(QPen(QColor('#2DD9B5'),2.5))
        p.drawPath(line)
        p.end()


class Task(QThread):
    note = Signal(str)
    result = Signal(object)
    failure = Signal(str)
    def __init__(self, func):
        super().__init__()
        self.func = func
        self.stopping = threading.Event()

    def run(self):
        try:
            value = self.func(self.note.emit, self.stopping.is_set)
            if not self.stopping.is_set():
                self.result.emit(value)
            else:
                self.failure.emit('Operasi dibatalkan.')
        except Exception as ex:
            self.failure.emit(f'{type(ex).__name__}: {ex}')


class StudioWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.hardware = hardware_report()
        self.analysis = None
        self.inspected = None
        self.task = None
        self.setWindowTitle('AutoClip Studio  •  YouTube & AI Clipper')
        self.setMinimumSize(880, 640)
        self.resize(1210,820)
        self.setStyleSheet(THEME)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setSpacing(0)
        outer.setContentsMargins(0,0,0,0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName('sidebar')
        self.sidebar.setFixedWidth(215)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(11,24,11,16)
        side.setSpacing(7)
        brand = label('◈  AutoClip', 'h2')
        brand.setStyleSheet('font-size: 20px; color: #70F5D9; padding: 4px 12px 1px;')
        side.addWidget(brand)
        side.addWidget(label('     STUDIO  /  BETA', 'muted'))
        side.addSpacing(23)
        self.navs = []
        for name in ('Studio', 'Pengaturan', 'Panduan'):
            b = QPushButton('  '+name)
            b.setObjectName('nav')
            b.setCheckable(True)
            b.clicked.connect(lambda checked, index=len(self.navs):self.go(index))
            self.navs.append(b)
            side.addWidget(b)
        side.addStretch(1)
        box = QFrame()
        box.setObjectName('soft')
        bxl = QVBoxLayout(box)
        bxl.addWidget(label('PROFILE DEVICE','muted'))
        bxl.addWidget(label(f"{self.hardware['ram_gb']} GB RAM  •  {self.hardware['cpu_physical']} cores"))
        self.device_profile = label('Saran: '+self.hardware['recommended'].title(), 'tag')
        bxl.addWidget(self.device_profile)
        side.addWidget(box)
        side.addWidget(label('v0.2.0  •  macOS / Win / Linux', 'muted'))
        outer.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack,1)
        self.stack.addWidget(self.make_studio())
        self.stack.addWidget(self.make_settings())
        self.stack.addWidget(self.make_help())
        self.go(0)

    def go(self, index):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.navs): b.setChecked(i==index)

    def make_studio(self):
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(25,23,25,20)
        root.setSpacing(12)
        headline = QHBoxLayout()
        titlecol = QVBoxLayout()
        titlecol.addWidget(label('Create clips that matter.', 'title'))
        titlecol.addWidget(label('YouTube heatmap + transcript + AI. Diproses dengan biaya serendah mungkin.', 'subtitle'))
        headline.addLayout(titlecol,1)
        headline.addWidget(label('LOCAL-FIRST ENGINE', 'tag'))
        root.addLayout(headline)
        top = QHBoxLayout()
        top.setSpacing(12)
        input_box, input_layout = card_layout()
        input_layout.addWidget(label('01 / SUMBER VIDEO', 'h2'))
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText('Tempel URL YouTube atau pilih MP4 / MKV / MOV lokal ...')
        input_layout.addWidget(self.source_edit)
        actionrow = QHBoxLayout()
        self.pick_btn = QPushButton('Pilih file')
        self.pick_btn.clicked.connect(self.pick_file)
        self.inspect_btn = QPushButton('Cek heatmap')
        self.inspect_btn.clicked.connect(self.inspect)
        actionrow.addWidget(self.pick_btn)
        actionrow.addWidget(self.inspect_btn)
        actionrow.addStretch()
        input_layout.addLayout(actionrow)
        self.auth_box = QCheckBox('Saya memiliki hak/izin untuk memproses video yang diunduh dari YouTube')
        self.auth_box.setChecked(False)
        self.auth_box.setWordWrap(True) if hasattr(self.auth_box,'setWordWrap') else None
        input_layout.addWidget(self.auth_box)
        subtitle_row = QHBoxLayout()
        self.subtitle_edit = QLineEdit()
        self.subtitle_edit.setPlaceholderText('Subtitle .srt/.vtt (opsional, untuk video lokal)')
        subtitle_row.addWidget(self.subtitle_edit)
        self.subtitle_pick = QPushButton('Browse')
        self.subtitle_pick.clicked.connect(self.pick_subtitle)
        subtitle_row.addWidget(self.subtitle_pick)
        input_layout.addLayout(subtitle_row)
        top.addWidget(input_box,3)
        preview_box, preview_layout = card_layout()
        preview_layout.addWidget(label('VIDEO INFO', 'h2'))
        self.thumbnail = label('◈\n\nPreview setelah analisis', 'muted',True)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setMinimumSize(245,105)
        self.thumbnail.setStyleSheet('background: #10182A; border-radius: 8px; color: #8095B6;')
        preview_layout.addWidget(self.thumbnail,1)
        self.source_status = label('Belum ada video', 'muted')
        preview_layout.addWidget(self.source_status)
        top.addWidget(preview_box,2)
        root.addLayout(top)
        chart_box, chart_layout = card_layout()
        charthead = QHBoxLayout()
        charthead.addWidget(label('02 / MOST REPLAYED HEATMAP', 'h2'))
        charthead.addStretch()
        self.chart_sub = label('Data dari yt-dlp jika tersedia', 'muted')
        charthead.addWidget(self.chart_sub)
        chart_layout.addLayout(charthead)
        self.heatmap = HeatmapView()
        chart_layout.addWidget(self.heatmap)
        root.addWidget(chart_box)
        root.addWidget(self.make_timeline())
        clips_box, clips_layout = card_layout()
        section = QHBoxLayout()
        section.addWidget(label('04 / REKOMENDASI KLIP', 'h2'))
        section.addStretch()
        self.count_label = label('Belum dianalisis', 'muted')
        section.addWidget(self.count_label)
        clips_layout.addLayout(section)
        self.table = QTableWidget(0,6)
        self.table.setHorizontalHeaderLabels(['Pilih','Mulai','Selesai','Skor','Judul / Hook','Sumber'])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(155)
        self.table.verticalHeader().setVisible(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(4,QHeaderView.ResizeMode.Stretch)
        for col in (0,1,2,3,5): hdr.setSectionResizeMode(col,QHeaderView.ResizeMode.ResizeToContents)
        clips_layout.addWidget(self.table)
        self.table.itemSelectionChanged.connect(self.select_clip_for_preview)
        clips_layout.addWidget(label('Tips: waktu mulai/selesai bisa diedit sebelum ekspor. Centang klip yang ingin dirender.', 'muted'))
        root.addWidget(clips_box,1)
        operations = QHBoxLayout()
        self.analyze_btn = QPushButton('✦  Analisis & pilih klip')
        self.analyze_btn.setObjectName('primary')
        self.analyze_btn.clicked.connect(self.analyze)
        self.export_btn = QPushButton('▣  Export klip terpilih')
        self.export_btn.clicked.connect(self.export)
        self.export_btn.setEnabled(False)
        self.open_btn = QPushButton('Buka output')
        self.open_btn.clicked.connect(self.open_output)
        self.cancel_btn = QPushButton('Batal')
        self.cancel_btn.clicked.connect(self.cancel)
        self.cancel_btn.setEnabled(False)
        operations.addWidget(self.analyze_btn)
        operations.addWidget(self.export_btn)
        operations.addWidget(self.open_btn)
        operations.addStretch()
        operations.addWidget(self.cancel_btn)
        root.addLayout(operations)
        self.progress = QProgressBar()
        self.progress.setRange(0,100)
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.logview = QPlainTextEdit()
        self.logview.setReadOnly(True)
        self.logview.setMaximumBlockCount(400)
        self.logview.setMaximumHeight(95)
        self.logview.setPlaceholderText('Aktivitas analisis dan render akan muncul di sini ...')
        root.addWidget(self.logview)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll

    def make_settings(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(28,25,28,25)
        root.setSpacing(14)
        root.addWidget(label('Pengaturan & Device Profile', 'title'))
        root.addWidget(label('Ubah model, API key, lokasi output, kualitas ekspor, dan profil CPU/RAM.', 'subtitle'))
        hw_box, hw = card_layout()
        hw.addWidget(label('SYSTEM DETECTION', 'h2'))
        self.hw_label = label('', 'muted',True)
        hw.addWidget(self.hw_label)
        self.rec_label = label('', 'tag')
        hw.addWidget(self.rec_label)
        scan = QPushButton('Scan ulang spesifikasi')
        scan.clicked.connect(self.rescan)
        hw.addWidget(scan)
        root.addWidget(hw_box)
        model_box, model_layout = card_layout()
        model_layout.addWidget(label('MODEL & TRANSCRIPTION', 'h2'))
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.profile_combo = QComboBox()
        for text,val in [('Auto • rekomendasi PC','auto'),('Economy • ringan','economy'),
                         ('Balanced','balanced'),('Quality','quality')]: self.profile_combo.addItem(text,val)
        form.addRow('Processing profile',self.profile_combo)
        self.speech_combo = QComboBox()
        for title,val in [('Auto • subtitle → Groq → lokal','auto'),('Subtitle yang tersedia','subtitles'),
                          ('Groq Whisper API','groq'),('faster-whisper lokal CPU','local'),
                          ('Tanpa transkripsi','none')]: self.speech_combo.addItem(title,val)
        form.addRow('Transkripsi',self.speech_combo)
        self.language_combo = QComboBox()
        for lng in ('id','en'): self.language_combo.addItem('Indonesia' if lng=='id' else 'English',lng)
        form.addRow('Bahasa', self.language_combo)
        self.groq_model_combo = QComboBox()
        for v in ('whisper-large-v3-turbo','whisper-large-v3'):self.groq_model_combo.addItem(v,v)
        form.addRow('Model Groq',self.groq_model_combo)
        self.ai_combo = QComboBox()
        for name,key in [('Off • Offline rules/heatmap','off'),('OpenRouter API','openrouter'),
                         ('Kie.ai API','kie'),('Ollama • lokal','ollama')]:self.ai_combo.addItem(name,key)
        form.addRow('AI pemilih klip',self.ai_combo)
        self.model_edit = QLineEdit()
        form.addRow('OpenRouter model ID',self.model_edit)
        self.kie_edit = QLineEdit()
        form.addRow('Kie chat endpoint',self.kie_edit)
        self.ollama_edit = QLineEdit()
        form.addRow('Ollama URL',self.ollama_edit)
        self.ollama_model = QLineEdit()
        form.addRow('Ollama model',self.ollama_model)
        model_layout.addLayout(form)
        root.addWidget(model_box)
        secret_box, secret_layout = card_layout()
        secret_layout.addWidget(label('API KEYS', 'h2'))
        secret_layout.addWidget(label('Disimpan di OS Keychain bila tersedia; jika tidak, hanya untuk sesi saat ini.', 'muted',True))
        keys = QFormLayout()
        self.key_inputs = {}
        for name in ('groq','openrouter','kie'):
            x = QLineEdit()
            x.setEchoMode(QLineEdit.EchoMode.Password)
            x.setPlaceholderText('Tersimpan' if get_secret(name) else 'Belum ada API key')
            self.key_inputs[name] = x
            keys.addRow(name.title()+' API key',x)
        secret_layout.addLayout(keys)
        clearrow = QHBoxLayout()
        self.keys_clear = QPushButton('Hapus semua API key')
        self.keys_clear.clicked.connect(self.clear_keys)
        clearrow.addWidget(self.keys_clear)
        clearrow.addStretch()
        secret_layout.addLayout(clearrow)
        root.addWidget(secret_box)
        video_box, video_layout = card_layout()
        video_layout.addWidget(label('VIDEO PROCESSING', 'h2'))
        f = QFormLayout()
        self.length_spin = QSpinBox()
        self.length_spin.setRange(15,180)
        self.length_spin.setSuffix(' detik')
        f.addRow('Durasi klip',self.length_spin)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1,20)
        f.addRow('Jumlah rekomendasi',self.count_spin)
        self.res_combo = QComboBox()
        self.res_combo.addItem('720 × 1280 (cepat)',720)
        self.res_combo.addItem('1080 × 1920 (detail)',1080)
        f.addRow('Resolusi output',self.res_combo)
        self.caption_check = QCheckBox('Aktifkan auto subtitle pada hasil MP4')
        f.addRow('Auto CC',self.caption_check)
        self.face_check = QCheckBox('Dynamic face tracking (crop bergerak, bukan active speaker)')
        f.addRow('Face-aware crop',self.face_check)
        self.out_edit = QLineEdit()
        f.addRow('Output folder',self.out_edit)
        self.ffmpeg_edit = QLineEdit()
        f.addRow('FFmpeg executable',self.ffmpeg_edit)
        self.ffprobe_edit = QLineEdit()
        f.addRow('FFprobe executable',self.ffprobe_edit)
        video_layout.addLayout(f)
        root.addWidget(video_box)
        save_btn = QPushButton('Simpan pengaturan')
        save_btn.setObjectName('primary')
        save_btn.clicked.connect(self.save_options)
        root.addWidget(save_btn)
        root.addStretch(1)
        scroll.setWidget(content)
        self.populate_settings()
        self.rescan()
        return scroll

    def make_help(self):
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(32,30,32,22)
        root.setSpacing(15)
        root.addWidget(label('Cara menggunakan AutoClip', 'title'))
        text = (
            '01  Tempel URL YouTube atau pilih video lokal. Untuk unduhan YouTube, pastikan memiliki hak/izin.\n\n'
            '02  Klik “Cek heatmap” untuk memeriksa ketersediaan replay chart tanpa mengunduh video.\n\n'
            '03  Pilih profil hardware dan transkripsi di Pengaturan. Mode Auto menggunakan subtitle yang tersedia, '
            'Groq bila key tersedia, kemudian faster-whisper jika terpasang.\n\n'
            '04  Klik “Analisis & pilih klip”. Aplikasi memproses transkrip, ranking heatmap, chapters, dan AI bila aktif.\n\n'
            '05  Koreksi waktu mulai/selesai, centang klip, lalu klik “Export klip terpilih”.\n\n'
            '06  Pilih klip, putar preview, geser playhead, lalu gunakan tombol Set IN/OUT untuk mengedit batas klip.\n\n'
            '07  File MP4 vertikal ada di folder proyek /exports. Dynamic face tracking bukan deteksi pembicara aktif.\n\n'
            'Batasan: heatmap adalah metadata publik best-effort, tidak tersedia untuk setiap video. '
            'Akses dan pengunduhan YouTube tunduk pada ketentuan YouTube; gunakan sumber yang berhak diproses.\n\n'
            'API keys tidak disimpan dalam file JSON. Linux membutuhkan keyring/secret service untuk penyimpanan persisten. '
            'Untuk pemakaian publik, jangan menyebarkan key perusahaan dalam binary klien.\n\n'
            'Troubleshoot: pastikan FFmpeg + FFprobe terpasang dan berada di PATH. '
            'Untuk ASR offline: pip install -e ".[local-asr]"; untuk smart crop: pip install -e ".[vision]". '
            'Sebagian build FFmpeg harus memiliki filter subtitles (libass).'
        )
        card,box=card_layout()
        box.addWidget(label('QUICK START','h2'))
        para = label(text,None,True)
        para.setAlignment(Qt.AlignmentFlag.AlignTop)
        para.setStyleSheet('font-size: 13px; line-height: 1.5;')
        box.addWidget(para)
        root.addWidget(card)
        root.addStretch()
        return content

    def _combo_set(self, combo, value):
        index=combo.findData(value)
        if index>=0: combo.setCurrentIndex(index)

    def populate_settings(self):
        s=self.settings
        for combo,val in ((self.profile_combo,s.profile),(self.speech_combo,s.speech),
                          (self.language_combo,s.language),(self.groq_model_combo,s.groq_model),
                          (self.ai_combo,s.ai_provider),(self.res_combo,s.output_resolution)):
            self._combo_set(combo,val)
        for line, val in ((self.model_edit,s.ai_model),(self.kie_edit,s.kie_endpoint),
                          (self.ollama_edit,s.ollama_url),(self.ollama_model,s.ollama_model),
                          (self.out_edit,s.downloads_dir),(self.ffmpeg_edit,s.ffmpeg),
                          (self.ffprobe_edit,s.ffprobe)):
            line.setText(val)
        self.length_spin.setValue(s.clip_length)
        self.count_spin.setValue(s.max_clips)
        self.caption_check.setChecked(s.captions)
        self.face_check.setChecked(s.smart_crop)

    def save_options(self):
        s=self.settings
        s.profile=self.profile_combo.currentData()
        s.speech=self.speech_combo.currentData()
        s.language=self.language_combo.currentData()
        s.groq_model=self.groq_model_combo.currentData()
        s.ai_provider=self.ai_combo.currentData()
        s.ai_model=self.model_edit.text().strip()
        s.kie_endpoint=self.kie_edit.text().strip()
        s.ollama_url=self.ollama_edit.text().strip()
        s.ollama_model=self.ollama_model.text().strip()
        s.clip_length=self.length_spin.value()
        s.max_clips=self.count_spin.value()
        s.output_resolution=self.res_combo.currentData()
        s.captions=self.caption_check.isChecked()
        s.smart_crop=self.face_check.isChecked()
        s.downloads_dir=self.out_edit.text().strip()
        s.ffmpeg=self.ffmpeg_edit.text().strip() or 'ffmpeg'
        s.ffprobe=self.ffprobe_edit.text().strip() or 'ffprobe'
        save_settings(s)
        ephemeral=[]
        for name,edit in self.key_inputs.items():
            if edit.text():
                if not set_secret(name,edit.text().strip()):
                    ephemeral.append(name)
                edit.clear()
                edit.setPlaceholderText('Tersimpan untuk sesi ini' if name in ephemeral else 'Tersimpan di keychain')
        self.log(f'Pengaturan tersimpan. Profil aktif: {effective_profile(s,self.hardware)}')
        if ephemeral:
            QMessageBox.warning(self,'Keychain tidak tersedia',
                                'API key '+', '.join(ephemeral)+' hanya disimpan selama aplikasi berjalan. '
                                'Aktifkan OS Keychain atau gunakan environment variables.')
        else:
            QMessageBox.information(self,'Pengaturan','Pengaturan berhasil disimpan.')

    def clear_keys(self):
        for name,edit in self.key_inputs.items():
            set_secret(name,'')
            edit.clear()
            edit.setPlaceholderText('Belum ada API key')
        QMessageBox.information(self,'Keys','API key pada keychain dan sesi telah dihapus (jika tersedia).')

    def rescan(self):
        self.hardware=hardware_report()
        h=self.hardware
        self.hw_label.setText(f"OS: {h['platform']}   |   CPU: {h['cpu']}\n"
                              f"Cores: {h['cpu_physical']} fisik / {h['cpu_logical']} threads\n"
                              f"RAM: {h['ram_gb']} GB\nGPU: {h['gpu']}")
        self.rec_label.setText('Saran profil otomatis: '+h['recommended'].title())
        self.device_profile.setText('Saran: '+h['recommended'].title())

    def pick_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Pilih video',str(Path.home()),
                                        'Video (*.mp4 *.mkv *.mov *.webm *.avi);;Semua file (*)')
        if path:
            self.source_edit.setText(path)
            self.auth_box.setChecked(False)

    def pick_subtitle(self):
        path,_=QFileDialog.getOpenFileName(self,'Pilih subtitle',str(Path.home()),
                                          'Subtitles (*.srt *.vtt *.ass);;Semua file (*)')
        if path: self.subtitle_edit.setText(path)

    def log(self,message):
        self.logview.appendPlainText(str(message))

    def busy(self,yes):
        self.analyze_btn.setEnabled(not yes)
        self.inspect_btn.setEnabled(not yes)
        self.export_btn.setEnabled(not yes and self.analysis is not None)
        self.cancel_btn.setEnabled(yes)
        self.pick_btn.setEnabled(not yes)
        if yes:
            self.progress.setRange(0,0)
        else:
            self.progress.setRange(0,100)
            self.progress.setValue(100)

    def execute(self, func, result_handler):
        if self.task is not None and self.task.isRunning():
            return
        self.busy(True)
        worker = Task(func)
        self.task = worker
        worker.note.connect(self.log)
        worker.result.connect(result_handler)
        worker.failure.connect(self.on_failure)
        worker.finished.connect(lambda: self.busy(False))
        worker.start()

    def on_failure(self,error):
        self.log('ERROR: '+error)
        QMessageBox.warning(self,'Proses gagal',error[:600])

    def cancel(self):
        if self.task and self.task.isRunning():
            self.log('Meminta pembatalan (network request dapat menunggu timeout) ...')
            self.task.stopping.set()

    def inspect(self):
        url=self.source_edit.text().strip()
        if not url.startswith(('http://','https://')):
            QMessageBox.information(self,'YouTube','Masukkan URL YouTube untuk mengecek heatmap.')
            return
        self.execute(lambda log,cancel:(log('Memeriksa metadata tanpa unduh file...'),inspect_url(url,cancel))[1],
                     self.on_inspected)

    def on_inspected(self,metadata):
        self.inspected=metadata
        self.heatmap.set_points(metadata.get('heatmap',[]))
        self.chart_sub.setText(f"{len(metadata.get('heatmap',[]))} titik data")
        self.source_status.setText(f"{metadata.get('title','')[:64]} • {format_time(metadata.get('duration',0))}")
        self.log('Heatmap tersedia.' if metadata.get('heatmap') else 'Tidak ada data heatmap untuk video ini.')

    def analyze(self):
        source=self.source_edit.text().strip()
        if not source:
            QMessageBox.information(self,'Sumber video','Tempel URL YouTube atau pilih video lokal.')
            return
        self.analysis=None
        self.table.setRowCount(0)
        subtitle=self.subtitle_edit.text().strip()
        settings=Settings(**self.settings.__dict__)
        self.execute(lambda log,cancel:analyze(source,subtitle,self.auth_box.isChecked(),settings,log,cancel),
                     self.on_analysis)

    def on_analysis(self,info):
        self.analysis=info
        self.heatmap.set_points(info['metadata'].get('heatmap',[]))
        self.chart_sub.setText(f"{len(info['metadata'].get('heatmap',[]))} titik heatmap")
        self.source_status.setText(f"{info['metadata'].get('title','')[:64]} • {format_time(info['duration'])}")
        self.count_label.setText(f"{len(info['clips'])} kandidat • {len(info['segments'])} caption")
        self.table.setRowCount(len(info['clips']))
        for row,clip in enumerate(info['clips']):
            checkbox = QTableWidgetItem('')
            checkbox.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable)
            checkbox.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row,0,checkbox)
            items=(format_time(clip['start']),format_time(clip['end']),
                   f"{clip['score']:.0f}",clip['title'],clip['source'])
            for col,val in enumerate(items,1):
                item=QTableWidgetItem(val)
                if col not in (1,2):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row,col,item)
        self.log('Analisis selesai. Edit waktu dan pilih klip sebelum ekspor.')
        self.busy(False)
        self.set_preview(info['source'])

    def set_preview(self,source):
        # Load system-native Qt player when possible; keep a FFmpeg poster fallback.
        if self.media_player is not None:
            try:
                self.media_player.stop()
                self.media_player.setSource(QUrl.fromLocalFile(str(Path(source).resolve())))
                self.preview_state.setText('Klik Play untuk meninjau video. Codec mengikuti dukungan Qt/macOS.')
            except Exception as ex:
                self.preview_state.setText(f'Player tidak tersedia: {ex}')
        # Poster generation is bounded and works without a Qt multimedia backend.
        try:
            from .media import run_process
            path=Path(self.analysis['workspace'])/'preview.jpg'
            if not path.exists():
                snapshot_at = min(2.0, float(self.analysis.get('duration', 0)) / 3)
                run_process([self.settings.ffmpeg,'-y','-hide_banner','-loglevel','error',
                             '-ss',str(snapshot_at),'-i',str(source),'-frames:v','1',
                             '-vf','scale=480:-2',str(path)])
            pix=QPixmap(str(path))
            if not pix.isNull():
                self.thumbnail.setPixmap(pix.scaled(340,145,Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation))
        except Exception as ex:
            self.log(f'Preview tidak tersedia: {ex}')

    def make_timeline(self):
        panel, outer = card_layout()
        outer.addWidget(label('03 / VIDEO PREVIEW & TIMELINE', 'h2'))
        view_row = QHBoxLayout()
        self.media_player = None
        self.media_output = None
        self.preview_state = label('Pilih video untuk preview. Jika player tidak mendukung codec, buka di player eksternal.', 'muted', True)
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtMultimediaWidgets import QVideoWidget
            self.media_player = QMediaPlayer(self)
            self.media_audio = QAudioOutput(self)
            self.media_audio.setVolume(0.65)
            self.media_player.setAudioOutput(self.media_audio)
            self.media_output = QVideoWidget()
            self.media_output.setMinimumSize(340, 185)
            self.media_output.setStyleSheet('background: black; border-radius: 8px;')
            self.media_player.setVideoOutput(self.media_output)
            self.media_player.positionChanged.connect(self._media_position)
            self.media_player.durationChanged.connect(self._media_duration)
            self.media_player.errorOccurred.connect(self._media_error)
            self.media_player.playbackStateChanged.connect(self._media_state)
            view_row.addWidget(self.media_output, 2)
        except (ImportError, OSError) as ex:
            self.preview_state.setText(f'Qt Multimedia tidak tersedia: {ex}. Gunakan player eksternal.')
        controls = QVBoxLayout()
        controls.addWidget(label('Edit dari playhead', 'h2'))
        controls.addWidget(self.preview_state)
        self.timeline_position = label('00:00:00 / 00:00:00', 'muted')
        controls.addWidget(self.timeline_position)
        actionrow = QHBoxLayout()
        self.play_btn = QPushButton('▶ Play / Pause')
        self.play_btn.clicked.connect(self.toggle_video)
        self.play_btn.setEnabled(self.media_player is not None)
        actionrow.addWidget(self.play_btn)
        external = QPushButton('Buka video')
        external.clicked.connect(self.open_source_video)
        actionrow.addWidget(external)
        controls.addLayout(actionrow)
        markers = QHBoxLayout()
        mark_in = QPushButton('Set IN')
        mark_out = QPushButton('Set OUT')
        mark_in.clicked.connect(lambda: self.mark_selected_clip(1))
        mark_out.clicked.connect(lambda: self.mark_selected_clip(2))
        markers.addWidget(mark_in)
        markers.addWidget(mark_out)
        controls.addLayout(markers)
        controls.addStretch()
        view_row.addLayout(controls, 1)
        outer.addLayout(view_row)
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.sliderReleased.connect(self._seek_from_slider)
        outer.addWidget(self.timeline_slider)
        return panel

    def _media_error(self, error, message):
        if message:
            self.preview_state.setText('Preview gagal: ' + str(message)[:160] + '. Gunakan Buka video.')

    def _media_state(self, state):
        if self.media_player is None:
            return
        from PySide6.QtMultimedia import QMediaPlayer
        self.play_btn.setText('Ⅱ Pause' if state == QMediaPlayer.PlaybackState.PlayingState else '▶ Play')

    def _media_position(self, ms):
        if not self.timeline_slider.isSliderDown():
            self.timeline_slider.setValue(max(0, int(ms)))
        duration_ms = self.media_player.duration() if self.media_player else 0
        self.timeline_position.setText(f'{format_time(ms/1000)} / {format_time(duration_ms/1000)}')

    def _media_duration(self, ms):
        self.timeline_slider.setRange(0, max(0, int(ms)))

    def _seek_from_slider(self):
        if self.media_player is not None:
            self.media_player.setPosition(self.timeline_slider.value())

    def toggle_video(self):
        if not self.media_player or not self.analysis:
            return
        from PySide6.QtMultimedia import QMediaPlayer
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def open_source_video(self):
        path = self.analysis.get('source') if self.analysis else self.source_edit.text().strip()
        if path and Path(path).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
        else:
            QMessageBox.information(self, 'Video', 'Analisis file lokal atau unduh video yang diizinkan terlebih dahulu.')

    def select_clip_for_preview(self):
        if not self.analysis or not self.media_player:
            return
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 1):
            return
        try:
            self.media_player.pause()
            self.media_player.setPosition(int(parse_time(self.table.item(row, 1).text()) * 1000))
        except (ValueError, AttributeError):
            pass

    def mark_selected_clip(self, column):
        if not self.analysis or not self.media_player:
            return
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, 'Timeline', 'Klik sebuah baris klip terlebih dahulu.')
            return
        value = self.media_player.position() / 1000.0
        other_index = 2 if column == 1 else 1
        try:
            other = parse_time(self.table.item(row, other_index).text())
        except (ValueError, AttributeError):
            return
        if column == 1 and value >= other or column == 2 and value <= other:
            QMessageBox.warning(self, 'Batas klip', 'IN harus sebelum OUT.')
            return
        self.table.item(row, column).setText(format_time(value))
        self.log(f'Klip {row + 1}: {"IN" if column == 1 else "OUT"} → {format_time(value)}')

    def export(self):
        if not self.analysis: return
        clips=[]
        for row,original in enumerate(self.analysis['clips']):
            if self.table.item(row,0).checkState() != Qt.CheckState.Checked:continue
            try:
                start=parse_time(self.table.item(row,1).text())
                end=parse_time(self.table.item(row,2).text())
                if not (0<=start<end<=self.analysis['duration']+.5):raise ValueError('waktu di luar video')
            except Exception as ex:
                QMessageBox.warning(self,'Timestamp salah',f'Baris {row+1}: {ex}')
                return
            candidate=dict(original)
            candidate.update(start=start,end=end)
            clips.append(candidate)
        if not clips:
            QMessageBox.information(self,'Pilih klip','Centang setidaknya satu klip.')
            return
        settings=Settings(**self.settings.__dict__)
        from .hardware import profile_defaults
        prof=profile_defaults(self.analysis['profile'])
        self.execute(lambda log,cancel:render_clips(self.analysis,clips,settings,prof,log,cancel),
                     self.on_exports)

    def on_exports(self,paths):
        self.log(f'{len(paths)} file klip berhasil diekspor.')
        self.busy(False)
        QMessageBox.information(self,'Ekspor selesai',
                                f'{len(paths)} klip berhasil diekspor ke:\n{paths[0].parent}')

    def open_output(self):
        output=(Path(self.analysis['workspace'])/'exports' if self.analysis
                else Path(self.settings.downloads_dir).expanduser())
        output.mkdir(parents=True,exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

    def closeEvent(self,event):
        if self.task and self.task.isRunning():
            QMessageBox.information(self,'Masih bekerja',
                                    'Batalkan proses terlebih dahulu sebelum menutup aplikasi.')
            event.ignore()
            return
        if self.media_player:
            self.media_player.stop()
        super().closeEvent(event)


def main():
    # macOS Finder-launched .app bundles may not inherit Homebrew's PATH.
    if sys.platform == 'darwin':
        import os
        parts = os.environ.get('PATH', '').split(os.pathsep)
        for brew_dir in ('/opt/homebrew/bin', '/usr/local/bin'):
            if brew_dir not in parts:
                parts.append(brew_dir)
        os.environ['PATH'] = os.pathsep.join(parts)
    app=QApplication(sys.argv)
    app.setApplicationName('AutoClip Studio')
    app.setOrganizationName('AutoClip')
    app.setFont(QFont('Arial' if sys.platform == 'darwin' else 'Segoe UI', 10))
    window=StudioWindow()
    window.show()
    sys.exit(app.exec())
