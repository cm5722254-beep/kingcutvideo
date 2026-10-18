"""
Batch Queue Tab for King Video Cutter.
Displays all pending, active, and completed batch processing jobs with status badges and progress bars.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QProgressBar, QFrame, QAbstractItemView, QFileDialog, QMessageBox
)

from core.queue_manager import queue_manager
from core.ffmpeg_utils import scan_video_files
from core.settings import settings
from core.i18n import t, subscribe_language_change

class QueueTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        queue_manager.sig_queue_updated.connect(self._refresh_table)
        queue_manager.sig_job_status_changed.connect(self._on_job_status_changed)
        subscribe_language_change(self.retranslate_ui)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Top Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_process_all = QPushButton(t("queue_btn_start"), self)
        self.btn_process_all.setProperty("variant", "primary")
        self.btn_process_all.clicked.connect(self._process_all)

        self.btn_add_folder = QPushButton(t("queue_add_folder"), self)
        self.btn_add_folder.clicked.connect(self._add_folder_jobs)

        self.btn_stop = QPushButton("❚❚ Stop Processing", self)
        self.btn_stop.clicked.connect(self._stop_processing)

        self.btn_clear_done = QPushButton(t("queue_btn_clear"), self)
        self.btn_clear_done.clicked.connect(self._clear_done)

        self.btn_remove = QPushButton("✕ Remove Selected", self)
        self.btn_remove.setProperty("variant", "danger")
        self.btn_remove.clicked.connect(self._remove_selected)

        toolbar.addWidget(self.btn_process_all)
        toolbar.addWidget(self.btn_add_folder)
        toolbar.addWidget(self.btn_stop)
        toolbar.addWidget(self.btn_clear_done)
        toolbar.addWidget(self.btn_remove)
        toolbar.addStretch()

        main_layout.addLayout(toolbar)

        # Queue Table
        table_card = QFrame(self)
        table_card.setProperty("card", True)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(8, 8, 8, 8)

        self.table = QTableWidget(0, 5, self)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)

        self.table.setHorizontalHeaderLabels([
            t("queue_col_idx"),
            t("queue_col_type"),
            t("queue_col_file"),
            t("queue_col_status"),
            t("queue_col_progress")
        ])
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 130)

        table_layout.addWidget(self.table)
        main_layout.addWidget(table_card)

        self._refresh_table()

    def _process_all(self):
        queue_manager.start_processing()

    def _stop_processing(self):
        queue_manager.stop_processing()

    def _clear_done(self):
        queue_manager.clear_completed()

    def _remove_selected(self):
        row = self.table.currentRow()
        if 0 <= row < len(queue_manager.jobs):
            job = queue_manager.jobs[row]
            queue_manager.remove_job(job.id)

    def _refresh_table(self):
        jobs = queue_manager.jobs
        self.table.setRowCount(len(jobs))

        for row, job in enumerate(jobs):
            item_id = QTableWidgetItem(str(job.id))
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_id)

            type_label = "✂️ Split" if job.job_type == "split" else "🎬 Merge"
            item_type = QTableWidgetItem(type_label)
            item_type.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item_type)

            item_title = QTableWidgetItem(job.title)
            self.table.setItem(row, 2, item_title)

            # Status styling
            status_map = {
                "pending": ("Pending", "#94a3b8"),
                "running": ("Running...", "#38bdf8"),
                "completed": ("Completed", "#10b981"),
                "failed": ("Failed", "#ef4444"),
                "cancelled": ("Cancelled", "#f59e0b")
            }
            status_text, color = status_map.get(job.status, (job.status, "#f8fafc"))
            item_status = QTableWidgetItem(status_text)
            item_status.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_status)

            # Progress Bar Cell
            bar = QProgressBar(self)
            bar.setRange(0, 100)
            bar.setValue(int(job.progress))
            if job.status == "completed":
                bar.setValue(100)
            self.table.setCellWidget(row, 4, bar)

    def _on_job_status_changed(self, job_id: int, status: str, progress: float):
        for row, job in enumerate(queue_manager.jobs):
            if job.id == job_id:
                status_item = self.table.item(row, 3)
                if status_item:
                    status_item.setText(status.capitalize())
                bar = self.table.cellWidget(row, 4)
                if isinstance(bar, QProgressBar):
                    bar.setValue(int(progress))
                break

    def _add_folder_jobs(self):
        folder = QFileDialog.getExistingDirectory(self, t("queue_add_folder"))
        if not folder:
            return
        videos = scan_video_files(folder)
        if not videos:
            QMessageBox.information(self, t("folder_import_title"), t("folder_no_videos"))
            return

        default_params = {
            "split_mode": "duration",
            "duration_sec": 60.0,
            "num_parts": 2,
            "target_size_mb": 50,
            "silence_thresh": -30,
            "silence_dur": 0.5,
            "fast_mode": True,
            "output_preset": "original",
            "output_dir": settings.get("default_output_dir"),
            "naming_pattern": "{name}_Part_{index:03d}",
            "hw_accel": settings.get("hw_accel", "auto")
        }

        for v in videos:
            p = dict(default_params)
            p["source_file"] = v
            p["title"] = os.path.basename(v)
            queue_manager.add_split_job(v, p)

        succ_msg = t("batch_split_added_msg").format(count=len(videos))
        QMessageBox.information(self, t("queue_add_folder"), succ_msg)

    def retranslate_ui(self):
        self.btn_process_all.setText(t("queue_btn_start"))
        self.btn_add_folder.setText(t("queue_add_folder"))
        self.btn_clear_done.setText(t("queue_btn_clear"))
        self.table.setHorizontalHeaderLabels([
            t("queue_col_idx"),
            t("queue_col_type"),
            t("queue_col_file"),
            t("queue_col_status"),
            t("queue_col_progress")
        ])
        self._refresh_table()

