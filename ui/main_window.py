"""
Main Application Window for King Video Cutter (ស្ដេចកាត់វីដេអូ).
Coordinates top navigation bar, quick language toggle (ខ្មែរ | EN),
theme toggle, settings modal, and big feature tabs (Split, Merge, Queue).
"""

import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QStatusBar,
    QApplication, QFrame
)

from core.i18n import t, set_language, get_current_language, subscribe_language_change, get_base_dir
from core.settings import settings
from core.ffmpeg_utils import get_working_video_encoder
from core.disk_utils import get_disk_free_space
from ui.theme import get_stylesheet
from ui.split_tab import SplitTab
from ui.merge_tab import MergeTab
from ui.queue_tab import QueueTab
from ui.settings_dialog import SettingsDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1120, 780)
        self.setMinimumSize(960, 680)

        # App Icon
        icon_path = os.path.join(get_base_dir(), "assets", "icons", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._init_ui()
        self._detect_gpu_badge()
        self._update_disk_status()

        # Timer to refresh disk space every 10 seconds
        self.disk_timer = QTimer(self)
        self.disk_timer.timeout.connect(self._update_disk_status)
        self.disk_timer.start(10000)

        subscribe_language_change(self.retranslate_ui)
        self.retranslate_ui()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(16, 12, 16, 12)
        root_layout.setSpacing(10)

        # Header Bar
        header_frame = QFrame(self)
        header_frame.setProperty("card", True)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(12)

        # Logo / Icon
        self.lbl_logo = QLabel(self)
        icon_path = os.path.join(get_base_dir(), "assets", "icons", "app_icon.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_logo.setPixmap(pix)
        else:
            self.lbl_logo.setText("👑")
            self.lbl_logo.setStyleSheet("font-size: 28px;")
        header_layout.addWidget(self.lbl_logo)

        # App Title & Subtitle
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.lbl_title = QLabel(t("app_title"), self)
        self.lbl_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #f59e0b;")
        self.lbl_subtitle = QLabel(t("app_subtitle"), self)
        self.lbl_subtitle.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_vbox.addWidget(self.lbl_title)
        title_vbox.addWidget(self.lbl_subtitle)
        header_layout.addLayout(title_vbox)

        header_layout.addStretch()

        # Hardware Acceleration Badge
        self.lbl_gpu_badge = QLabel("💻 CPU", self)
        self.lbl_gpu_badge.setStyleSheet(
            "background-color: #1e293b; color: #38bdf8; border: 1px solid #334155; "
            "border-radius: 6px; padding: 4px 10px; font-weight: bold; font-size: 11px;"
        )
        header_layout.addWidget(self.lbl_gpu_badge)

        # Quick Language Toggle Button: "ខ្មែរ | EN"
        self.btn_lang_toggle = QPushButton(self._get_lang_toggle_label(), self)
        self.btn_lang_toggle.setStyleSheet("font-weight: bold; font-size: 12px; padding: 6px 12px;")
        self.btn_lang_toggle.setToolTip("Switch Language / ប្តូរភាសា")
        self.btn_lang_toggle.clicked.connect(self._toggle_language)
        header_layout.addWidget(self.btn_lang_toggle)

        # Theme Toggle Button (🌙 Dark / ☀️ Light)
        curr_theme = settings.get("theme", "dark")
        self.btn_theme_toggle = QPushButton("☀️ Light" if curr_theme == "dark" else "🌙 Dark", self)
        self.btn_theme_toggle.setStyleSheet("font-weight: bold; font-size: 12px; padding: 6px 12px;")
        self.btn_theme_toggle.clicked.connect(self._toggle_theme)
        header_layout.addWidget(self.btn_theme_toggle)

        # Settings Button
        self.btn_settings = QPushButton("⚙️ " + t("nav_settings"), self)
        self.btn_settings.setStyleSheet("font-weight: bold; font-size: 12px; padding: 6px 12px;")
        self.btn_settings.clicked.connect(self._open_settings)
        header_layout.addWidget(self.btn_settings)

        root_layout.addWidget(header_frame)

        # Big Tabs
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)

        self.tab_split = SplitTab(self)
        self.tab_merge = MergeTab(self)
        self.tab_queue = QueueTab(self)

        self.tabs.addTab(self.tab_split, "✂️  " + t("tab_split_title"))
        self.tabs.addTab(self.tab_merge, "🎬  " + t("tab_merge_title"))
        self.tabs.addTab(self.tab_queue, "📋  " + t("tab_queue_title"))

        root_layout.addWidget(self.tabs)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.status_bar.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.setStatusBar(self.status_bar)

        self.lbl_status_disk = QLabel("💾 Checking storage...", self)
        self.lbl_status_disk.setStyleSheet("color: #10b981; font-weight: bold; padding-right: 12px;")
        self.status_bar.addPermanentWidget(self.lbl_status_disk)

        self.status_bar.showMessage(t("status_idle"))

    def _get_lang_toggle_label(self) -> str:
        curr = get_current_language()
        return "🌐 EN" if curr == "km" else "🌐 ខ្មែរ"

    def _toggle_language(self):
        curr = get_current_language()
        new_lang = "en" if curr == "km" else "km"
        set_language(new_lang)
        settings.set("language", new_lang)
        self.btn_lang_toggle.setText(self._get_lang_toggle_label())

    def _toggle_theme(self):
        curr = settings.get("theme", "dark")
        new_theme = "light" if curr == "dark" else "dark"
        settings.set("theme", new_theme)
        self._apply_theme(new_theme)
        self.btn_theme_toggle.setText("☀️ Light" if new_theme == "dark" else "🌙 Dark")

    def _apply_theme(self, theme: str):
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_stylesheet(theme))

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.sig_theme_changed.connect(self._apply_theme)
        dlg.exec()
        self._detect_gpu_badge()

    def _detect_gpu_badge(self):
        pref = settings.get("hw_accel", "auto")
        encoder, label = get_working_video_encoder(pref)
        if "GPU" in label:
            self.lbl_gpu_badge.setText(f"🚀 {label}")
            self.lbl_gpu_badge.setStyleSheet(
                "background-color: #064e3b; color: #34d399; border: 1px solid #059669; "
                "border-radius: 6px; padding: 4px 10px; font-weight: bold; font-size: 11px;"
            )
        else:
            self.lbl_gpu_badge.setText(f"💻 CPU ({encoder})")
            self.lbl_gpu_badge.setStyleSheet(
                "background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; "
                "border-radius: 6px; padding: 4px 10px; font-weight: bold; font-size: 11px;"
            )

    def _update_disk_status(self):
        out_dir = settings.get("default_output_dir")
        free_gb, drive = get_disk_free_space(out_dir)
        self.lbl_status_disk.setText(f"💾 {drive} {free_gb:.1f} GB Free")

    def retranslate_ui(self):
        self.setWindowTitle(t("app_title"))
        self.lbl_title.setText(t("app_title"))
        self.lbl_subtitle.setText(t("app_subtitle"))
        self.btn_lang_toggle.setText(self._get_lang_toggle_label())
        self.btn_settings.setText("⚙️ " + t("nav_settings"))
        self.tabs.setTabText(0, "✂️  " + t("tab_split_title"))
        self.tabs.setTabText(1, "🎬  " + t("tab_merge_title"))
        self.tabs.setTabText(2, "📋  " + t("tab_queue_title"))
        self.status_bar.showMessage(t("status_idle"))
