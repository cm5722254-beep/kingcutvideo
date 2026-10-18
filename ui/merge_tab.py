"""
Merge Tab for King Video Cutter.
Supports combining multiple video clips into one long video.
Features drag-and-drop file reordering, natural sorting (1, 2, 10),
clip preview player, optional transitions, background music, intro/outro,
and execution progress controls.
"""

import os
import subprocess
from typing import List, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QFrame, QGroupBox, QLineEdit,
    QProgressBar, QCheckBox, QSlider, QDoubleSpinBox, QComboBox,
    QAbstractItemView
)

from core.ffmpeg_utils import probe_video, natural_sort_key, format_duration, scan_video_files
from core.merger import MergeWorker
from core.queue_manager import queue_manager
from core.settings import settings
from core.logger import logger
from core.i18n import t, subscribe_language_change
from ui.preview_player import VideoPreviewPlayer

class MergeClipsTable(QTableWidget):
    """Table supporting drag & drop row reordering and external file/folder drops."""
    def __init__(self, on_order_changed, on_paths_dropped=None, parent=None):
        super().__init__(0, 5, parent)
        self.on_order_changed = on_order_changed
        self.on_paths_dropped = on_paths_dropped
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDragDropOverwriteMode(False)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAcceptDrops(True)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
            if paths and self.on_paths_dropped:
                self.on_paths_dropped(paths)
        else:
            super().dropEvent(event)
            self.on_order_changed()



class MergeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clip_list: List[dict] = []  # List of probe info dicts
        self.worker: Optional[MergeWorker] = None
        self.is_paused = False

        self._init_ui()
        subscribe_language_change(self.retranslate_ui)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.setAcceptDrops(True)

        # Upper Controls Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_add_clips = QPushButton(t("merge_add_clips"), self)
        self.btn_add_clips.setProperty("variant", "primary")
        self.btn_add_clips.clicked.connect(self._browse_clips)

        self.btn_add_folder = QPushButton(t("merge_add_folder"), self)
        self.btn_add_folder.clicked.connect(self._browse_folder)

        self.btn_full_movie = QPushButton(t("merge_full_movie_btn"), self)
        self.btn_full_movie.setStyleSheet(
            "background-color: #d97706; color: white; font-weight: bold; border-radius: 6px; padding: 6px 12px;"
        )
        self.btn_full_movie.clicked.connect(self._prepare_full_movie)

        self.btn_sort = QPushButton(t("merge_sort_natural"), self)
        self.btn_sort.clicked.connect(self._sort_clips_natural)

        self.btn_move_up = QPushButton(t("merge_move_up"), self)
        self.btn_move_up.clicked.connect(self._move_clip_up)

        self.btn_move_down = QPushButton(t("merge_move_down"), self)
        self.btn_move_down.clicked.connect(self._move_clip_down)

        self.btn_remove = QPushButton(t("merge_remove_clip"), self)
        self.btn_remove.setProperty("variant", "danger")
        self.btn_remove.clicked.connect(self._remove_selected_clip)

        self.btn_clear = QPushButton(t("merge_clear_clips"), self)
        self.btn_clear.clicked.connect(self._clear_all_clips)

        toolbar.addWidget(self.btn_add_clips)
        toolbar.addWidget(self.btn_add_folder)
        toolbar.addWidget(self.btn_full_movie)
        toolbar.addWidget(self.btn_sort)
        toolbar.addWidget(self.btn_move_up)
        toolbar.addWidget(self.btn_move_down)
        toolbar.addWidget(self.btn_remove)
        toolbar.addWidget(self.btn_clear)
        toolbar.addStretch()

        main_layout.addLayout(toolbar)

        # Middle Content: Left = Clips Table, Right = Mini Player & Advanced Options
        content_hbox = QHBoxLayout()
        content_hbox.setSpacing(10)

        # Table Card
        table_card = QFrame(self)
        table_card.setProperty("card", True)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_layout.setSpacing(6)

        self.table = MergeClipsTable(self._on_table_reordered, self.add_paths, self)
        self.table.setHorizontalHeaderLabels([
            t("table_col_idx"),
            t("table_col_filename"),
            t("table_col_duration"),
            t("table_col_res"),
            t("table_col_size")
        ])
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 90)
        self.table.itemSelectionChanged.connect(self._on_clip_selected)
        table_layout.addWidget(self.table)

        self.lbl_table_summary = QLabel(t("merge_empty_hint"), self)
        self.lbl_table_summary.setStyleSheet("font-size: 11px; color: #94a3b8; font-style: italic;")
        table_layout.addWidget(self.lbl_table_summary)

        content_hbox.addWidget(table_card, 6)

        # Right Card: Mini Player + Options
        right_card = QFrame(self)
        right_card.setProperty("card", True)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)

        # Mini Clip Preview Player
        self.lbl_player_title = QLabel("Clip Preview", self)
        self.lbl_player_title.setStyleSheet("font-weight: bold; color: #f59e0b;")
        right_layout.addWidget(self.lbl_player_title)

        self.preview_player = VideoPreviewPlayer(self)
        self.preview_player.setFixedHeight(180)
        right_layout.addWidget(self.preview_player)

        # Merge Options Group
        self.grp_options = QGroupBox("Merge Options", self)
        opt_grid = QGridLayout(self.grp_options)
        opt_grid.setSpacing(6)

        # Output Name & Folder
        self.lbl_out_name = QLabel(t("merge_output_name"), self)
        self.txt_out_name = QLineEdit("Merged_Video.mp4", self)
        opt_grid.addWidget(self.lbl_out_name, 0, 0)
        opt_grid.addWidget(self.txt_out_name, 0, 1, 1, 2)

        self.lbl_folder = QLabel(t("output_folder_label"), self)
        self.txt_folder = QLineEdit(self)
        self.txt_folder.setText(settings.get("default_output_dir"))
        self.btn_browse_folder = QPushButton(t("browse_folder_btn"), self)
        self.btn_browse_folder.clicked.connect(self._browse_output_dir)
        opt_grid.addWidget(self.lbl_folder, 1, 0)
        opt_grid.addWidget(self.txt_folder, 1, 1)
        opt_grid.addWidget(self.btn_browse_folder, 1, 2)

        # Transitions
        self.chk_transition = QCheckBox(t("merge_transitions"), self)
        self.spin_transition = QDoubleSpinBox(self)
        self.spin_transition.setRange(0.5, 3.0)
        self.spin_transition.setValue(1.0)
        self.spin_transition.setSuffix(" s")
        self.spin_transition.setEnabled(False)
        self.chk_transition.toggled.connect(self.spin_transition.setEnabled)
        opt_grid.addWidget(self.chk_transition, 2, 0, 1, 2)
        opt_grid.addWidget(self.spin_transition, 2, 2)

        # Background Music (BGM)
        self.chk_bgm = QCheckBox(t("merge_bgm"), self)
        self.txt_bgm = QLineEdit(self)
        self.txt_bgm.setPlaceholderText("Select MP3/WAV/AAC...")
        self.txt_bgm.setEnabled(False)
        self.btn_browse_bgm = QPushButton("...", self)
        self.btn_browse_bgm.setEnabled(False)
        self.btn_browse_bgm.clicked.connect(self._browse_bgm)
        self.chk_bgm.toggled.connect(self._toggle_bgm)

        opt_grid.addWidget(self.chk_bgm, 3, 0)
        opt_grid.addWidget(self.txt_bgm, 3, 1)
        opt_grid.addWidget(self.btn_browse_bgm, 3, 2)

        # Intro Video
        self.lbl_intro = QLabel(t("merge_intro"), self)
        self.txt_intro = QLineEdit(self)
        self.btn_browse_intro = QPushButton("...", self)
        self.btn_browse_intro.clicked.connect(self._browse_intro)
        opt_grid.addWidget(self.lbl_intro, 4, 0)
        opt_grid.addWidget(self.txt_intro, 4, 1)
        opt_grid.addWidget(self.btn_browse_intro, 4, 2)

        # Outro Video
        self.lbl_outro = QLabel(t("merge_outro"), self)
        self.txt_outro = QLineEdit(self)
        self.btn_browse_outro = QPushButton("...", self)
        self.btn_browse_outro.clicked.connect(self._browse_outro)
        opt_grid.addWidget(self.lbl_outro, 5, 0)
        opt_grid.addWidget(self.txt_outro, 5, 1)
        opt_grid.addWidget(self.btn_browse_outro, 5, 2)

        # Per-clip Trim
        self.chk_trim = QCheckBox(t("merge_trim_clips"), self)
        self.chk_trim.toggled.connect(self._toggle_trim)
        opt_grid.addWidget(self.chk_trim, 6, 0, 1, 3)

        trim_widget = QWidget(self)
        trim_layout = QHBoxLayout(trim_widget)
        trim_layout.setContentsMargins(0, 0, 0, 0)
        trim_layout.setSpacing(6)

        self.lbl_trim_start = QLabel(t("merge_trim_start_lbl"), self)
        self.spin_trim_start = QDoubleSpinBox(self)
        self.spin_trim_start.setRange(0.0, 60.0)
        self.spin_trim_start.setValue(0.0)
        self.spin_trim_start.setSuffix(" s")
        self.spin_trim_start.setEnabled(False)

        self.lbl_trim_end = QLabel(t("merge_trim_end_lbl"), self)
        self.spin_trim_end = QDoubleSpinBox(self)
        self.spin_trim_end.setRange(0.0, 60.0)
        self.spin_trim_end.setValue(0.0)
        self.spin_trim_end.setSuffix(" s")
        self.spin_trim_end.setEnabled(False)

        trim_layout.addWidget(self.lbl_trim_start)
        trim_layout.addWidget(self.spin_trim_start)
        trim_layout.addWidget(self.lbl_trim_end)
        trim_layout.addWidget(self.spin_trim_end)
        opt_grid.addWidget(trim_widget, 7, 0, 1, 3)

        right_layout.addWidget(self.grp_options)
        content_hbox.addWidget(right_card, 5)

        main_layout.addLayout(content_hbox)

        # Bottom Area: Progress Bar, Status & Action Buttons
        bottom_card = QFrame(self)
        bottom_card.setProperty("card", True)
        bottom_layout = QVBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(12, 10, 12, 10)
        bottom_layout.setSpacing(8)

        self.bar_progress = QProgressBar(self)
        self.bar_progress.setValue(0)
        bottom_layout.addWidget(self.bar_progress)

        status_hbox = QHBoxLayout()
        self.lbl_status = QLabel(t("status_idle"), self)
        self.lbl_status.setStyleSheet("font-weight: 600; color: #f8fafc;")
        status_hbox.addWidget(self.lbl_status)

        status_hbox.addStretch()

        self.lbl_stats = QLabel("ETA: --:-- | Speed: --", self)
        self.lbl_stats.setStyleSheet("font-size: 11px; color: #94a3b8;")
        status_hbox.addWidget(self.lbl_stats)
        bottom_layout.addLayout(status_hbox)

        btn_hbox = QHBoxLayout()
        btn_hbox.setSpacing(10)

        self.btn_start = QPushButton(t("merge_btn_start"), self)
        self.btn_start.setProperty("variant", "primary")
        self.btn_start.setMinimumHeight(36)
        self.btn_start.clicked.connect(self.start_merge)

        self.btn_pause = QPushButton(t("btn_pause"), self)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.toggle_pause)

        self.btn_cancel = QPushButton(t("btn_cancel"), self)
        self.btn_cancel.setProperty("variant", "danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_merge)

        self.btn_add_queue = QPushButton(t("btn_add_to_queue"), self)
        self.btn_add_queue.clicked.connect(self.add_to_queue)

        self.btn_open_folder = QPushButton(t("btn_open_folder"), self)
        self.btn_open_folder.clicked.connect(self.open_output_folder)

        btn_hbox.addWidget(self.btn_start, 2)
        btn_hbox.addWidget(self.btn_pause, 1)
        btn_hbox.addWidget(self.btn_cancel, 1)
        btn_hbox.addWidget(self.btn_add_queue, 1)
        btn_hbox.addWidget(self.btn_open_folder, 1)

        bottom_layout.addLayout(btn_hbox)
        main_layout.addWidget(bottom_card)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
            if paths:
                self.add_paths(paths)

    def _browse_clips(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, t("merge_add_clips"), "", t("video_filter")
        )
        if files:
            self.add_paths(files)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, t("merge_add_folder"))
        if folder:
            self.add_paths([folder])

    def add_paths(self, paths: List[str]):
        new_files: List[str] = []
        for p in paths:
            if os.path.isdir(p):
                new_files.extend(scan_video_files(p))
            elif os.path.isfile(p):
                new_files.extend(scan_video_files(p))

        if not new_files:
            QMessageBox.information(self, t("folder_import_title"), t("folder_no_videos"))
            return

        existing_paths = {c["path"] for c in self.clip_list}
        added_count = 0
        for f in new_files:
            if f not in existing_paths:
                info = probe_video(f)
                if info:
                    self.clip_list.append(info)
                    existing_paths.add(f)
                    added_count += 1

        self._refresh_table()
        if added_count > 0:
            logger.info(f"Imported {added_count} video clips into merge list.")

    def _refresh_table(self):
        self.table.setRowCount(len(self.clip_list))
        total_dur = 0.0
        for row, clip in enumerate(self.clip_list):
            item_idx = QTableWidgetItem(str(row + 1))
            item_idx.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_idx)

            self.table.setItem(row, 1, QTableWidgetItem(clip["filename"]))

            item_dur = QTableWidgetItem(clip["duration_str"])
            item_dur.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item_dur)

            item_res = QTableWidgetItem(clip["resolution_str"])
            item_res.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_res)

            item_size = QTableWidgetItem(clip["size_str"])
            item_size.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, item_size)

            total_dur += clip.get("duration", 0.0)

        if self.clip_list:
            total_str = format_duration(total_dur)
            self.lbl_table_summary.setText(f"{len(self.clip_list)} clips | Total duration: {total_str}")
        else:
            self.lbl_table_summary.setText(t("merge_empty_hint"))

    def _on_clip_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            idx = selected_rows[0].row()
            if 0 <= idx < len(self.clip_list):
                clip = self.clip_list[idx]
                self.preview_player.load_video(clip["path"], clip["duration"])

    def _sort_clips_natural(self):
        self.clip_list.sort(key=lambda c: natural_sort_key(c["filename"]))
        self._refresh_table()

    def _move_clip_up(self):
        row = self.table.currentRow()
        if row > 0:
            self.clip_list[row], self.clip_list[row - 1] = self.clip_list[row - 1], self.clip_list[row]
            self._refresh_table()
            self.table.selectRow(row - 1)

    def _move_clip_down(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.clip_list) - 1:
            self.clip_list[row], self.clip_list[row + 1] = self.clip_list[row + 1], self.clip_list[row]
            self._refresh_table()
            self.table.selectRow(row + 1)

    def _remove_selected_clip(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.clip_list):
            del self.clip_list[row]
            self._refresh_table()

    def _clear_all_clips(self):
        self.clip_list.clear()
        self._refresh_table()
        self.preview_player.stop()

    def _on_table_reordered(self):
        # Synchronize clip_list order with table
        new_list = []
        for row in range(self.table.rowCount()):
            filename = self.table.item(row, 1).text()
            found = next((c for c in self.clip_list if c["filename"] == filename), None)
            if found:
                new_list.append(found)
        if len(new_list) == len(self.clip_list):
            self.clip_list = new_list
        self._refresh_table()

    def _toggle_trim(self, checked: bool):
        self.spin_trim_start.setEnabled(checked)
        self.spin_trim_end.setEnabled(checked)

    def _prepare_full_movie(self):
        if not self.clip_list:
            self._browse_folder()
            if not self.clip_list:
                return

        self._sort_clips_natural()

        first_name = self.clip_list[0].get("filename", "Drama")
        import re
        clean_title = re.sub(r'[\(\[\{].*?[\)\]\}]', '', first_name)
        clean_title = re.sub(r'[_\-\s]*(ep(isode)?|part|ភាគ|\d+).*', '', clean_title, flags=re.I).strip()
        if not clean_title or len(clean_title) < 2:
            clean_title = "Drama_Series"
        output_name = f"Full_Movie_{clean_title}.mp4"
        self.txt_out_name.setText(output_name)

        # Lossless fast stream copy settings
        self.chk_transition.setChecked(False)
        self.chk_bgm.setChecked(False)

        total_dur = sum(c.get("duration", 0.0) for c in self.clip_list)
        total_str = format_duration(total_dur)
        msg = t("full_movie_ready_msg").format(
            count=len(self.clip_list),
            duration=total_str,
            name=output_name
        )
        QMessageBox.information(self, t("full_movie_ready_title"), msg)
        self.btn_start.setFocus()

    def _toggle_bgm(self, checked: bool):
        self.txt_bgm.setEnabled(checked)
        self.btn_browse_bgm.setEnabled(checked)

    def _browse_bgm(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("merge_bgm"), "", "Audio Files (*.mp3 *.wav *.aac *.m4a *.flac)"
        )
        if path:
            self.txt_bgm.setText(path)

    def _browse_intro(self):
        path, _ = QFileDialog.getOpenFileName(self, t("merge_intro"), "", t("video_filter"))
        if path:
            self.txt_intro.setText(path)

    def _browse_outro(self):
        path, _ = QFileDialog.getOpenFileName(self, t("merge_outro"), "", t("video_filter"))
        if path:
            self.txt_outro.setText(path)

    def _browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, t("output_folder_label"), self.txt_folder.text())
        if folder:
            self.txt_folder.setText(folder)

    def _get_worker_params(self) -> Optional[dict]:
        if len(self.clip_list) < 2:
            QMessageBox.warning(self, t("msg_error_title"), t("msg_select_two_videos"))
            return None

        out_name = self.txt_out_name.text().strip() or "Merged_Video.mp4"
        if not out_name.lower().endswith(".mp4"):
            out_name += ".mp4"

        out_folder = self.txt_folder.text().strip() or settings.get("default_output_dir")
        out_path = os.path.join(out_folder, out_name)

        return {
            "input_files": [c["path"] for c in self.clip_list],
            "output_path": out_path,
            "add_transition": self.chk_transition.isChecked(),
            "transition_dur": self.spin_transition.value(),
            "bgm_file": self.txt_bgm.text().strip() if self.chk_bgm.isChecked() else None,
            "bgm_volume": 0.25,
            "intro_file": self.txt_intro.text().strip() or None,
            "outro_file": self.txt_outro.text().strip() or None,
            "hw_accel": settings.get("hw_accel", "auto"),
            "output_preset": "original",
            "trim_start": self.spin_trim_start.value() if self.chk_trim.isChecked() else 0.0,
            "trim_end": self.spin_trim_end.value() if self.chk_trim.isChecked() else 0.0
        }

    def start_merge(self):
        params = self._get_worker_params()
        if not params:
            return

        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.btn_add_queue.setEnabled(False)
        self.bar_progress.setValue(0)

        self.worker = MergeWorker(**params, parent=self)
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

    def cancel_merge(self):
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
            job_id = queue_manager.add_merge_job(
                params["input_files"], params["output_path"], params
            )
            QMessageBox.information(
                self, t("msg_success_title"),
                f"Merge Job #{job_id} successfully added to batch queue!"
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

    def _on_worker_progress(self, overall_pct: float, eta_str: str, speed_str: str):
        self.bar_progress.setValue(int(overall_pct))
        self.lbl_stats.setText(f"{t('stat_eta', eta=eta_str)} | {t('stat_speed', speed=speed_str)}")

    def _on_worker_finished(self, out_file: str):
        self._reset_buttons()
        self.lbl_status.setText(t("status_completed"))
        QMessageBox.information(self, t("msg_success_title"), t("msg_merge_done"))

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
        self.btn_add_clips.setText(t("merge_add_clips"))
        self.btn_add_folder.setText(t("merge_add_folder"))
        self.btn_full_movie.setText(t("merge_full_movie_btn"))
        self.btn_sort.setText(t("merge_sort_natural"))
        self.btn_move_up.setText(t("merge_move_up"))
        self.btn_move_down.setText(t("merge_move_down"))
        self.btn_remove.setText(t("merge_remove_clip"))
        self.btn_clear.setText(t("merge_clear_clips"))
        self.table.setHorizontalHeaderLabels([
            t("table_col_idx"),
            t("table_col_filename"),
            t("table_col_duration"),
            t("table_col_res"),
            t("table_col_size")
        ])
        self.lbl_out_name.setText(t("merge_output_name"))
        self.lbl_folder.setText(t("output_folder_label"))
        self.btn_browse_folder.setText(t("browse_folder_btn"))
        self.chk_transition.setText(t("merge_transitions"))
        self.chk_bgm.setText(t("merge_bgm"))
        self.lbl_intro.setText(t("merge_intro"))
        self.lbl_outro.setText(t("merge_outro"))
        self.chk_trim.setText(t("merge_trim_clips"))
        self.lbl_trim_start.setText(t("merge_trim_start_lbl"))
        self.lbl_trim_end.setText(t("merge_trim_end_lbl"))
        self.btn_start.setText(t("merge_btn_start"))
        self.btn_pause.setText(t("btn_pause") if not self.is_paused else t("btn_resume"))
        self.btn_cancel.setText(t("btn_cancel"))
        self.btn_add_queue.setText(t("btn_add_to_queue"))
        self.btn_open_folder.setText(t("btn_open_folder"))
        self._refresh_table()
