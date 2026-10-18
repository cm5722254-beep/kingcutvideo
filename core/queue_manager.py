"""
Batch Queue Manager for King Video Cutter.
Allows users to queue multiple Split and Merge jobs and execute them sequentially.
"""

from typing import List, Dict, Any, Optional
from PySide6.QtCore import QObject, Signal

from core.splitter import SplitWorker
from core.merger import MergeWorker
from core.logger import logger
from core.i18n import t

class QueueJob:
    def __init__(self, job_id: int, job_type: str, title: str, params: Dict[str, Any]):
        self.id = job_id
        self.job_type = job_type  # "split" or "merge"
        self.title = title
        self.params = params
        self.status = "pending"   # pending, running, completed, failed, cancelled
        self.progress = 0.0
        self.status_text = t("status_pending")

class BatchQueueManager(QObject):
    sig_queue_updated = Signal()
    sig_job_status_changed = Signal(int, str, float)  # job_id, status, progress
    sig_all_completed = Signal()

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BatchQueueManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self._initialized = True
        self.jobs: List[QueueJob] = []
        self._next_id = 1
        self._is_running = False
        self._current_worker: Optional[QObject] = None
        self._current_job: Optional[QueueJob] = None

    def add_split_job(self, source_file: str, params: Dict[str, Any]) -> int:
        job_id = self._next_id
        self._next_id += 1
        title = f"[Split] {params.get('title', source_file)}"
        job = QueueJob(job_id, "split", title, params)
        self.jobs.append(job)
        self.sig_queue_updated.emit()
        return job_id

    def add_merge_job(self, input_files: List[str], output_path: str, params: Dict[str, Any]) -> int:
        job_id = self._next_id
        self._next_id += 1
        title = f"[Merge] {len(input_files)} clips -> {output_path}"
        params["input_files"] = input_files
        params["output_path"] = output_path
        job = QueueJob(job_id, "merge", title, params)
        self.jobs.append(job)
        self.sig_queue_updated.emit()
        return job_id

    def remove_job(self, job_id: int):
        self.jobs = [j for j in self.jobs if j.id != job_id]
        self.sig_queue_updated.emit()

    def clear_completed(self):
        self.jobs = [j for j in self.jobs if j.status in ("pending", "running")]
        self.sig_queue_updated.emit()

    def start_processing(self):
        if self._is_running:
            return
        self._is_running = True
        self._process_next()

    def stop_processing(self):
        self._is_running = False
        if self._current_worker and hasattr(self._current_worker, "cancel"):
            self._current_worker.cancel()

    def _process_next(self):
        if not self._is_running:
            return

        # Find next pending job
        pending_jobs = [j for j in self.jobs if j.status == "pending"]
        if not pending_jobs:
            self._is_running = False
            self.sig_all_completed.emit()
            return

        job = pending_jobs[0]
        self._current_job = job
        job.status = "running"
        job.status_text = t("status_analyzing")
        self.sig_job_status_changed.emit(job.id, job.status, 0.0)
        self.sig_queue_updated.emit()

        if job.job_type == "split":
            p = job.params
            worker = SplitWorker(
                source_file=p["source_file"],
                split_mode=p.get("split_mode", "duration"),
                duration_sec=p.get("duration_sec", 60.0),
                num_parts=p.get("num_parts", 10),
                target_size_mb=p.get("target_size_mb", 50.0),
                silence_thresh=p.get("silence_thresh", -30),
                silence_dur=p.get("silence_dur", 0.5),
                fast_mode=p.get("fast_mode", True),
                output_preset=p.get("output_preset", "original"),
                output_dir=p.get("output_dir", ""),
                naming_pattern=p.get("naming_pattern", "{name}_Part_{index:03d}"),
                hw_accel=p.get("hw_accel", "auto")
            )
            worker.sig_progress.connect(lambda part_pct, overall_pct, eta, spd: self._on_worker_progress(job, overall_pct))
            worker.sig_finished.connect(lambda files: self._on_worker_success(job))
            worker.sig_error.connect(lambda err: self._on_worker_error(job, err))
            worker.sig_cancelled.connect(lambda: self._on_worker_cancelled(job))
            self._current_worker = worker
            worker.start()

        elif job.job_type == "merge":
            p = job.params
            worker = MergeWorker(
                input_files=p["input_files"],
                output_path=p["output_path"],
                add_transition=p.get("add_transition", False),
                transition_dur=p.get("transition_dur", 1.0),
                bgm_file=p.get("bgm_file"),
                bgm_volume=p.get("bgm_volume", 0.2),
                intro_file=p.get("intro_file"),
                outro_file=p.get("outro_file"),
                hw_accel=p.get("hw_accel", "auto"),
                output_preset=p.get("output_preset", "original")
            )
            worker.sig_progress.connect(lambda overall_pct, eta, spd: self._on_worker_progress(job, overall_pct))
            worker.sig_finished.connect(lambda path: self._on_worker_success(job))
            worker.sig_error.connect(lambda err: self._on_worker_error(job, err))
            worker.sig_cancelled.connect(lambda: self._on_worker_cancelled(job))
            self._current_worker = worker
            worker.start()

    def _on_worker_progress(self, job: QueueJob, progress: float):
        job.progress = progress
        self.sig_job_status_changed.emit(job.id, job.status, progress)

    def _on_worker_success(self, job: QueueJob):
        job.status = "completed"
        job.progress = 100.0
        job.status_text = t("status_completed")
        self.sig_job_status_changed.emit(job.id, job.status, 100.0)
        self.sig_queue_updated.emit()
        self._process_next()

    def _on_worker_error(self, job: QueueJob, error_msg: str):
        job.status = "failed"
        job.status_text = error_msg
        self.sig_job_status_changed.emit(job.id, job.status, job.progress)
        self.sig_queue_updated.emit()
        self._process_next()

    def _on_worker_cancelled(self, job: QueueJob):
        job.status = "cancelled"
        job.status_text = t("status_cancelled")
        self.sig_job_status_changed.emit(job.id, job.status, job.progress)
        self.sig_queue_updated.emit()
        self._process_next()

queue_manager = BatchQueueManager()
