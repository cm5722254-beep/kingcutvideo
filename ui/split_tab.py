"""
Split Tab for King Video Cutter.
Supports auto-splitting long videos by duration, parts, file size, or silence.
Includes video drag & drop, file metadata inspector, preview player with cut markers,
fast/precise modes, presets, dual progress bars, and execution controls.
"""

import os
import subprocess
from typing import Optional, List

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup, QComboBox,
    QSpinBox, QDoubleSpinBox, QLineEdit, QProgressBar,
    QFileDialog, QMessageBox, QFrame, QGroupBox, QScrollArea
)

from core.ffmpeg_utils import probe_video, format_duration, format_file_size, scan_video_files
from core.splitter import SplitWorker
from core.queue_manager import queue_manager
from core.settings import settings
from core.logger import logger
from core.i18n import t, subscribe_language_change
from ui.preview_player import VideoPreviewPlayer

class VideoDropArea(QFrame):
    """Drag & Drop zone for input video or folder."""
    def __init__(self, on_file_selected, on_folder_selected=None, parent=None):
        super().__init__(parent)
        self.on_file_selected = on_file_selected
        self.on_folder_selected = on_folder_selected
        self.setAcceptDrops(True)
        self.setProperty("card", True)
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(6)

        self.lbl_icon = QLabel("🎬", self)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setStyleSheet("font-size: 32px;")
        layout.addWidget(self.lbl_icon)

        self.lbl_text = QLabel(t("drag_drop_video"), self)
        self.lbl_text.setAlignment(Qt.AlignCenter)
        self.lbl_text.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(self.lbl_text)

        self.lbl_file = QLabel(t("no_video_selected"), self)
        self.lbl_file.setAlignment(Qt.AlignCenter)
        self.lbl_file.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(self.lbl_file)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._browse_file()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                if os.path.isdir(path) and self.on_folder_selected:
                    self.on_folder_selected(path)
                elif os.path.isfile(path):
                    self.on_file_selected(path)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("browse_video_btn"), "", t("video_filter")
        )
        if path:
            self.on_file_selected(path)

    def set_selected_filename(self, filename: str):
        self.lbl_file.setText(f"📁 {filename}")
        self.lbl_file.setStyleSheet("font-size: 12px; color: #f59e0b; font-weight: bold;")

    def retranslate_ui(self):
        self.lbl_text.setText(t("drag_drop_video"))


class SplitTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_video_path: Optional[str] = None
        self.video_info: Optional[dict] = None
        self.worker: Optional[SplitWorker] = None
        self.is_paused = False

        self._init_ui()
        subscribe_language_change(self.retranslate_ui)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Upper Area: Drop Area & Video Info Card
        top_hbox = QHBoxLayout()
        top_hbox.setSpacing(10)

        self.drop_area = VideoDropArea(self.on_video_selected, self.on_folder_selected, self)
        self.drop_area.setMinimumHeight(90)
        top_hbox.addWidget(self.drop_area, 3)

        # Video metadata card
        self.info_card = QFrame(self)
        self.info_card.setProperty("card", True)
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(4)

        self.lbl_info_title = QLabel("Video Details", self)
        self.lbl_info_title.setStyleSheet("font-weight: bold; color: #f59e0b;")
        info_layout.addWidget(self.lbl_info_title)

        self.lbl_info_dur = QLabel("Duration: --:--:--", self)
        self.lbl_info_res = QLabel("Resolution: --", self)
        self.lbl_info_codec = QLabel("Codec: --", self)
        self.lbl_info_size = QLabel("Size: --", self)

        for lbl in (self.lbl_info_dur, self.lbl_info_res, self.lbl_info_codec, self.lbl_info_size):
            lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
            info_layout.addWidget(lbl)

        top_hbox.addWidget(self.info_card, 2)
        main_layout.addLayout(top_hbox)

        # Middle Content Area: Left = Preview Player, Right = Settings Cards
        content_hbox = QHBoxLayout()
        content_hbox.setSpacing(10)

        # Left Column: Video Preview Player
        self.player_card = QFrame(self)
        self.player_card.setProperty("card", True)
        player_layout = QVBoxLayout(self.player_card)
        player_layout.setContentsMargins(10, 10, 10, 10)
        player_layout.setSpacing(6)

        self.lbl_preview_title = QLabel(t("preview_title"), self)
        self.lbl_preview_title.setStyleSheet("font-weight: bold; color: #f59e0b;")
        player_layout.addWidget(self.lbl_preview_title)

        self.player = VideoPreviewPlayer(self)
        player_layout.addWidget(self.player)

        self.lbl_cut_summary = QLabel(t("cut_points_none"), self)
        self.lbl_cut_summary.setStyleSheet("font-size: 11px; color: #64748b; font-style: italic;")
        player_layout.addWidget(self.lbl_cut_summary)

        content_hbox.addWidget(self.player_card, 5)

        # Right Column: Split Options & Output Settings
        right_scroll = QScrollArea(self)
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Split Modes Group
        self.grp_mode = QGroupBox(t("mode_duration"), self)
        mode_layout = QVBoxLayout(self.grp_mode)
        mode_layout.setSpacing(8)

        mode_btn_layout = QHBoxLayout()
        self.rb_dur = QRadioButton(t("mode_duration"), self)
        self.rb_parts = QRadioButton(t("mode_parts"), self)
        self.rb_size = QRadioButton(t("mode_size"), self)
        self.rb_smart = QRadioButton(t("mode_smart"), self)
        self.rb_dur.setChecked(True)

        self.mode_group = QButtonGroup(self)
        for i, rb in enumerate((self.rb_dur, self.rb_parts, self.rb_size, self.rb_smart)):
            self.mode_group.addButton(rb, i)
            mode_btn_layout.addWidget(rb)
        mode_layout.addLayout(mode_btn_layout)

        # Mode Specific Inputs
        self.mode_inputs_frame = QFrame(self)
        self.input_layout = QGridLayout(self.mode_inputs_frame)
        self.input_layout.setContentsMargins(0, 0, 0, 0)

        # Duration Mode Inputs
        self.lbl_dur_preset = QLabel(t("duration_per_part_label"), self)
        self.combo_dur_preset = QComboBox(self)
        self.combo_dur_preset.addItems([
            t("preset_30s"), t("preset_1m"), t("preset_3m"),
            t("preset_5m"), t("preset_10m"), t("preset_custom")
        ])
        self.combo_dur_preset.setCurrentIndex(1)  # Default 1m

        self.spin_custom_dur = QSpinBox(self)
        self.spin_custom_dur.setRange(5, 86400)
        self.spin_custom_dur.setValue(60)
        self.spin_custom_dur.setSuffix(" s")
        self.spin_custom_dur.setVisible(False)

        # Parts Mode Inputs
        self.lbl_parts = QLabel(t("parts_count_label"), self)
        self.spin_parts = QSpinBox(self)
        self.spin_parts.setRange(2, 500)
        self.spin_parts.setValue(10)

        # Size Mode Inputs
        self.lbl_size = QLabel(t("size_per_part_label"), self)
        self.spin_size = QSpinBox(self)
        self.spin_size.setRange(5, 10000)
        self.spin_size.setValue(50)
        self.spin_size.setSuffix(" MB")

        # Smart Silence Inputs
        self.lbl_silence_db = QLabel(t("silence_thresh_label"), self)
        self.spin_silence_db = QSpinBox(self)
        self.spin_silence_db.setRange(-60, -10)
        self.spin_silence_db.setValue(-30)

        self.lbl_silence_dur = QLabel(t("silence_dur_label"), self)
        self.spin_silence_dur = QDoubleSpinBox(self)
        self.spin_silence_dur.setRange(0.2, 5.0)
        self.spin_silence_dur.setSingleStep(0.1)
        self.spin_silence_dur.setValue(0.5)

        self.input_layout.addWidget(self.lbl_dur_preset, 0, 0)
        self.input_layout.addWidget(self.combo_dur_preset, 0, 1)
        self.input_layout.addWidget(self.spin_custom_dur, 0, 2)
        mode_layout.addWidget(self.mode_inputs_frame)

        self.mode_group.idClicked.connect(self._on_mode_changed)
        self.combo_dur_preset.currentIndexChanged.connect(self._on_dur_preset_changed)
        self.spin_custom_dur.valueChanged.connect(self._update_cut_markers)
        self.spin_parts.valueChanged.connect(self._update_cut_markers)
        self.spin_size.valueChanged.connect(self._update_cut_markers)

        right_layout.addWidget(self.grp_mode)

        # Cutting Engine Mode Group (Fast vs Precise)
        self.grp_engine = QGroupBox("Cutting Mode", self)
        engine_layout = QVBoxLayout(self.grp_engine)
        engine_layout.setSpacing(6)

        self.rb_fast = QRadioButton(t("fast_mode_label"), self)
        self.rb_fast.setChecked(True)
        self.lbl_fast_desc = QLabel(t("fast_mode_desc"), self)
        self.lbl_fast_desc.setStyleSheet("font-size: 11px; color: #94a3b8; margin-left: 20px;")

        self.rb_precise = QRadioButton(t("precise_mode_label"), self)

        self.engine_group = QButtonGroup(self)
        self.engine_group.addButton(self.rb_fast, 0)
        self.engine_group.addButton(self.rb_precise, 1)

        engine_layout.addWidget(self.rb_fast)
        engine_layout.addWidget(self.lbl_fast_desc)
        engine_layout.addWidget(self.rb_precise)
        right_layout.addWidget(self.grp_engine)

        # Output Preset Card
        self.grp_preset = QGroupBox(t("output_preset_label"), self)
        preset_layout = QVBoxLayout(self.grp_preset)

        self.combo_preset = QComboBox(self)
        self.combo_preset.addItems([
            t("preset_original"),
            t("preset_1080p"),
            t("preset_720p"),
            t("preset_vertical")
        ])
        preset_layout.addWidget(self.combo_preset)
        right_layout.addWidget(self.grp_preset)

        # Destination Folder & Filename Pattern
        self.grp_dest = QGroupBox(t("output_folder_label"), self)
        dest_layout = QGridLayout(self.grp_dest)

        self.txt_folder = QLineEdit(self)
        self.txt_folder.setText(settings.get("default_output_dir"))
        self.btn_browse_folder = QPushButton(t("browse_folder_btn"), self)
        self.btn_browse_folder.clicked.connect(self._browse_output_dir)

        dest_layout.addWidget(self.txt_folder, 0, 0)
        dest_layout.addWidget(self.btn_browse_folder, 0, 1)

        self.lbl_pattern = QLabel(t("naming_pattern_label"), self)
        self.txt_pattern = QLineEdit(self)
        self.txt_pattern.setText(settings.get("naming_pattern"))
        dest_layout.addWidget(self.lbl_pattern, 1, 0)
        dest_layout.addWidget(self.txt_pattern, 2, 0, 1, 2)

        right_layout.addWidget(self.grp_dest)
        right_scroll.setWidget(right_content)
        content_hbox.addWidget(right_scroll, 5)

        main_layout.addLayout(content_hbox)

        # Bottom Area: Dual Progress Bars, Status & Action Buttons
        bottom_card = QFrame(self)
        bottom_card.setProperty("card", True)
        bottom_layout = QVBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(12, 10, 12, 10)
        bottom_layout.setSpacing(8)

        # Progress Bars (Part + Overall)
        progress_grid = QGridLayout()

        self.lbl_part_prog = QLabel("Part Progress", self)
        self.lbl_part_prog.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        self.bar_part = QProgressBar(self)
        self.bar_part.setValue(0)
        self.bar_part.setProperty("color", "blue")

        self.lbl_overall_prog = QLabel("Overall Progress", self)
        self.lbl_overall_prog.setStyleSheet("font-size: 11px; font-weight: bold; color: #f59e0b;")
        self.bar_overall = QProgressBar(self)
        self.bar_overall.setValue(0)

        progress_grid.addWidget(self.lbl_part_prog, 0, 0)
        progress_grid.addWidget(self.bar_part, 0, 1)
        progress_grid.addWidget(self.lbl_overall_prog, 1, 0)
        progress_grid.addWidget(self.bar_overall, 1, 1)
        bottom_layout.addLayout(progress_grid)

        # Status & ETA line
        status_hbox = QHBoxLayout()
        self.lbl_status = QLabel(t("status_idle"), self)
        self.lbl_status.setStyleSheet("font-weight: 600; color: #f8fafc;")
        status_hbox.addWidget(self.lbl_status)

        status_hbox.addStretch()

        self.lbl_stats = QLabel("ETA: --:-- | Speed: --", self)
        self.lbl_stats.setStyleSheet("font-size: 11px; color: #94a3b8;")
        status_hbox.addWidget(self.lbl_stats)
        bottom_layout.addLayout(status_hbox)

        # Buttons Bar
        btn_hbox = QHBoxLayout()
        btn_hbox.setSpacing(10)

        self.btn_start = QPushButton(t("btn_start"), self)
        self.btn_start.setProperty("variant", "primary")
        self.btn_start.setMinimumHeight(36)
        self.btn_start.clicked.connect(self.start_split)

        self.btn_pause = QPushButton(t("btn_pause"), self)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.toggle_pause)

        self.btn_cancel = QPushButton(t("btn_cancel"), self)
        self.btn_cancel.setProperty("variant", "danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_split)

        self.btn_add_queue = QPushButton(t("btn_add_to_queue"), self)
        self.btn_add_queue.clicked.connect(self.add_to_queue)

        self.btn_open_folder = QPushButton(t("btn_open_folder"), self)
        self.btn_open_folder.clicked.connect(self.open_output_folder)

        self.btn_batch_folder = QPushButton(t("split_batch_folder_btn"), self)
        self.btn_batch_folder.clicked.connect(self._browse_batch_folder)

        btn_hbox.addWidget(self.btn_start, 2)
        btn_hbox.addWidget(self.btn_pause, 1)
        btn_hbox.addWidget(self.btn_cancel, 1)
        btn_hbox.addWidget(self.btn_add_queue, 1)
        btn_hbox.addWidget(self.btn_batch_folder, 1)
        btn_hbox.addWidget(self.btn_open_folder, 1)

        bottom_layout.addLayout(btn_hbox)
        main_layout.addWidget(bottom_card)

    def _browse_batch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, t("split_batch_folder_btn"))
        if folder:
            self.on_folder_selected(folder)

    def on_folder_selected(self, folder_path: str):
        videos = scan_video_files(folder_path)
        if not videos:
            QMessageBox.information(self, t("folder_import_title"), t("folder_no_videos"))
            return

        if len(videos) == 1:
            self.on_video_selected(videos[0])
            return

        folder_name = os.path.basename(folder_path)
        msg = t("batch_split_confirm_msg").format(count=len(videos), name=folder_name)
        reply = QMessageBox.question(
            self, t("batch_split_confirm_title"), msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            params = self._get_worker_params()
            if not params:
                return
            for v in videos:
                job_params = dict(params)
                job_params["source_file"] = v
                job_params["title"] = os.path.basename(v)
                queue_manager.add_split_job(v, job_params)

            succ_msg = t("batch_split_added_msg").format(count=len(videos))
            QMessageBox.information(self, t("batch_split_confirm_title"), succ_msg)
        else:
            self.on_video_selected(videos[0])

    def on_video_selected(self, file_path: str):
        self.current_video_path = file_path
        self.drop_area.set_selected_filename(os.path.basename(file_path))

        info = probe_video(file_path)
        if not info:
            QMessageBox.critical(self, t("msg_error_title"), t("msg_file_corrupt"))
            return

        self.video_info = info
        self.lbl_info_dur.setText(f"Duration: {info['duration_str']}")
        self.lbl_info_res.setText(f"Resolution: {info['width']}x{info['height']} ({info['resolution_str']}) @ {info['fps']:.1f} fps")
        self.lbl_info_codec.setText(f"Codec: {info['video_codec']} / {info['audio_codec']}")
        self.lbl_info_size.setText(f"Size: {info['size_str']}")

        # Load into preview player
        self.player.load_video(file_path, info["duration"])
        self._update_cut_markers()

    def _on_mode_changed(self, mode_id: int):
        # Clear layout
        while self.input_layout.count():
            item = self.input_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        if mode_id == 0:  # Duration
            self.input_layout.addWidget(self.lbl_dur_preset, 0, 0)
            self.input_layout.addWidget(self.combo_dur_preset, 0, 1)
            if self.combo_dur_preset.currentIndex() == 5:
                self.input_layout.addWidget(self.spin_custom_dur, 0, 2)
        elif mode_id == 1:  # Parts
            self.input_layout.addWidget(self.lbl_parts, 0, 0)
            self.input_layout.addWidget(self.spin_parts, 0, 1)
        elif mode_id == 2:  # Size
            self.input_layout.addWidget(self.lbl_size, 0, 0)
            self.input_layout.addWidget(self.spin_size, 0, 1)
        elif mode_id == 3:  # Smart
            self.input_layout.addWidget(self.lbl_silence_db, 0, 0)
            self.input_layout.addWidget(self.spin_silence_db, 0, 1)
            self.input_layout.addWidget(self.lbl_silence_dur, 1, 0)
            self.input_layout.addWidget(self.spin_silence_dur, 1, 1)

        self._update_cut_markers()

    def _on_dur_preset_changed(self, idx: int):
        is_custom = (idx == 5)
        self.spin_custom_dur.setVisible(is_custom)
        if is_custom and self.input_layout.indexOf(self.spin_custom_dur) == -1:
            self.input_layout.addWidget(self.spin_custom_dur, 0, 2)
        self._update_cut_markers()

    def _get_current_duration_sec(self) -> float:
        idx = self.combo_dur_preset.currentIndex()
        preset_values = [30.0, 60.0, 180.0, 300.0, 600.0]
        if idx < 5:
            return preset_values[idx]
        return float(self.spin_custom_dur.value())

    def _update_cut_markers(self):
        if not self.video_info or self.video_info["duration"] <= 0:
            return

        total_dur = self.video_info["duration"]
        mode_id = self.mode_group.checkedId()
        markers: List[float] = []

        if mode_id == 0:  # Duration
            step = self._get_current_duration_sec()
            curr = step
            while curr < total_dur:
                markers.append(curr)
                curr += step
        elif mode_id == 1:  # Parts
            parts = self.spin_parts.value()
            step = total_dur / parts
            for i in range(1, parts):
                markers.append(i * step)
        elif mode_id == 2:  # Size
            total_mb = max(1.0, self.video_info["size_bytes"] / (1024 * 1024))
            target_mb = self.spin_size.value()
            parts = max(1, int(round(total_mb / target_mb)))
            step = total_dur / parts
            for i in range(1, parts):
                markers.append(i * step)

        self.player.set_cut_markers(markers)
        num_parts = len(markers) + 1
        self.lbl_cut_summary.setText(t("cut_points_summary", count=num_parts))

    def _browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, t("output_folder_label"), self.txt_folder.text())
        if folder:
            self.txt_folder.setText(folder)

    def _get_worker_params(self) -> Optional[dict]:
        if not self.current_video_path or not os.path.isfile(self.current_video_path):
            QMessageBox.warning(self, t("msg_error_title"), t("msg_select_video_first"))
            return None

        mode_id = self.mode_group.checkedId()
        mode_str = "duration"
        if mode_id == 1:
            mode_str = "parts"
        elif mode_id == 2:
            mode_str = "size"
        elif mode_id == 3:
            mode_str = "smart"

        preset_idx = self.combo_preset.currentIndex()
        preset_map = ["original", "1080p", "720p", "vertical"]
        preset_str = preset_map[preset_idx] if preset_idx < len(preset_map) else "original"

        return {
            "source_file": self.current_video_path,
            "title": os.path.basename(self.current_video_path),
            "split_mode": mode_str,
            "duration_sec": self._get_current_duration_sec(),
            "num_parts": self.spin_parts.value(),
            "target_size_mb": self.spin_size.value(),
            "silence_thresh": self.spin_silence_db.value(),
            "silence_dur": self.spin_silence_dur.value(),
            "fast_mode": self.rb_fast.isChecked(),
            "output_preset": preset_str,
            "output_dir": self.txt_folder.text().strip() or settings.get("default_output_dir"),
            "naming_pattern": self.txt_pattern.text().strip() or "{name}_Part_{index:03d}",
            "hw_accel": settings.get("hw_accel", "auto")
        }

    def start_split(self):
        params = self._get_worker_params()
        if not params:
            return

        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.btn_add_queue.setEnabled(False)
        self.bar_part.setValue(0)
        self.bar_overall.setValue(0)

        self.worker = SplitWorker(**params, parent=self)
        self.worker.sig_status.connect(self._on_worker_status)
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_finished.connect(self._on_worker_finished)
        self.worker.sig_error.connect(self._on_worker_error)
        self.worker.sig_cancelled.connect(self._on_worker_cancelled)
        self.worker.start()

    def toggle_pause(self):
        if not self.worker:
            return
        if not self.is_paused:
            self.worker.pause()
            self.is_paused = True
            self.btn_pause.setText(t("btn_resume"))
            self.lbl_status.setText("Paused")
        else:
            self.worker.resume()
            self.is_paused = False
            self.btn_pause.setText(t("btn_pause"))

    def cancel_split(self):
        if not self.worker:
            return
        reply = QMessageBox.question(
            self, t("msg_cancel_confirm"), t("msg_cancel_confirm"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.worker.cancel()

    def add_to_queue(self):
        params = self._get_worker_params()
        if params:
            job_id = queue_manager.add_split_job(self.current_video_path, params)
            QMessageBox.information(
                self, t("msg_success_title"),
                f"Job #{job_id} successfully added to batch processing queue!"
            )

    def open_output_folder(self):
        folder = self.txt_folder.text().strip() or settings.get("default_output_dir")
        os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.run(["xdg-open", folder])

    def _on_worker_status(self, text: str):
        self.lbl_status.setText(text)

    def _on_worker_progress(self, part_pct: float, overall_pct: float, eta_str: str, speed_str: str):
        self.bar_part.setValue(int(part_pct))
        self.bar_overall.setValue(int(overall_pct))
        self.lbl_stats.setText(f"{t('stat_eta', eta=eta_str)} | {t('stat_speed', speed=speed_str)}")

    def _on_worker_finished(self, files: list):
        self._reset_buttons()
        self.lbl_status.setText(t("status_completed"))
        QMessageBox.information(
            self, t("msg_success_title"),
            t("msg_split_done", count=len(files))
        )

    def _on_worker_error(self, err: str):
        self._reset_buttons()
        self.lbl_status.setText(t("status_failed"))
        QMessageBox.critical(self, t("msg_error_title"), err)

    def _on_worker_cancelled(self):
        self._reset_buttons()
        self.lbl_status.setText(t("status_cancelled"))

    def _reset_buttons(self):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText(t("btn_pause"))
        self.btn_cancel.setEnabled(False)
        self.btn_add_queue.setEnabled(True)
        self.is_paused = False

    def retranslate_ui(self):
        self.drop_area.retranslate_ui()
        self.lbl_preview_title.setText(t("preview_title"))
        self.grp_mode.setTitle(t("mode_duration"))
        self.rb_dur.setText(t("mode_duration"))
        self.rb_parts.setText(t("mode_parts"))
        self.rb_size.setText(t("mode_size"))
        self.rb_smart.setText(t("mode_smart"))
        self.lbl_dur_preset.setText(t("duration_per_part_label"))
        self.lbl_parts.setText(t("parts_count_label"))
        self.lbl_size.setText(t("size_per_part_label"))
        self.lbl_silence_db.setText(t("silence_thresh_label"))
        self.lbl_silence_dur.setText(t("silence_dur_label"))
        self.rb_fast.setText(t("fast_mode_label"))
        self.lbl_fast_desc.setText(t("fast_mode_desc"))
        self.rb_precise.setText(t("precise_mode_label"))
        self.grp_preset.setTitle(t("output_preset_label"))
        self.grp_dest.setTitle(t("output_folder_label"))
        self.btn_browse_folder.setText(t("browse_folder_btn"))
        self.lbl_pattern.setText(t("naming_pattern_label"))
        self.btn_start.setText(t("btn_start"))
        self.btn_pause.setText(t("btn_pause") if not self.is_paused else t("btn_resume"))
        self.btn_cancel.setText(t("btn_cancel"))
        self.btn_add_queue.setText(t("btn_add_to_queue"))
        self.btn_batch_folder.setText(t("split_batch_folder_btn"))
        self.btn_open_folder.setText(t("btn_open_folder"))
        self._update_cut_markers()
