"""
Splitter engine for King Video Cutter.
Performs automatic video splitting by duration, parts, file size, or smart silence detection.
Supports both Fast Mode (stream copy) and Precise Mode (re-encode with GPU/CPU).
Executes in background QThread with real-time FFmpeg progress, pause/resume, and cancel.
"""

import os
import sys
import re
import time
import ctypes
import subprocess
from typing import List, Tuple, Dict, Any, Optional

from PySide6.QtCore import QThread, Signal

from core.ffmpeg_utils import (
    get_ffmpeg_path,
    probe_video,
    get_working_video_encoder,
    format_duration,
    detect_silence_points,
    CREATE_NO_WINDOW
)
from core.disk_utils import has_sufficient_disk_space
from core.settings import settings
from core.logger import logger
from core.i18n import t

def suspend_process(pid: int) -> bool:
    """Pauses Windows process using NtSuspendProcess."""
    if sys.platform != "win32":
        return False
    try:
        PROCESS_ALL_ACCESS = 0x1F0FFF
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if handle:
            ctypes.windll.ntdll.NtSuspendProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
    except Exception as e:
        logger.error(f"Error suspending process {pid}: {e}")
    return False

def resume_process(pid: int) -> bool:
    """Resumes Windows process using NtResumeProcess."""
    if sys.platform != "win32":
        return False
    try:
        PROCESS_ALL_ACCESS = 0x1F0FFF
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if handle:
            ctypes.windll.ntdll.NtResumeProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
    except Exception as e:
        logger.error(f"Error resuming process {pid}: {e}")
    return False


class SplitWorker(QThread):
    sig_status = Signal(str)
    sig_progress = Signal(float, float, str, str)  # part_pct, overall_pct, eta_str, speed_str
    sig_part_started = Signal(int, int, str)       # current_idx, total_parts, output_filename
    sig_part_done = Signal(int, str)              # current_idx, output_filepath
    sig_finished = Signal(list)                   # list of created file paths
    sig_error = Signal(str)                       # error message
    sig_cancelled = Signal()

    def __init__(
        self,
        source_file: str,
        split_mode: str = "duration",
        duration_sec: float = 60.0,
        num_parts: int = 10,
        target_size_mb: float = 50.0,
        silence_thresh: int = -30,
        silence_dur: float = 0.5,
        fast_mode: bool = True,
        output_preset: str = "original",
        output_dir: str = "",
        naming_pattern: str = "{name}_Part_{index:03d}",
        hw_accel: str = "auto",
        parent=None
    ):
        super().__init__(parent)
        self.source_file = source_file
        self.split_mode = split_mode
        self.duration_sec = max(1.0, float(duration_sec))
        self.num_parts = max(1, int(num_parts))
        self.target_size_mb = max(1.0, float(target_size_mb))
        self.silence_thresh = silence_thresh
        self.silence_dur = silence_dur
        self.fast_mode = fast_mode
        self.output_preset = output_preset
        self.output_dir = output_dir or settings.get("default_output_dir")
        self.naming_pattern = naming_pattern or "{name}_Part_{index:03d}"
        self.hw_accel = hw_accel

        self._is_paused = False
        self._is_cancelled = False
        self._current_proc: Optional[subprocess.Popen] = None
        self._current_output_file: Optional[str] = None
        self._created_files: List[str] = []

    def pause(self):
        self._is_paused = True
        if self._current_proc and self._current_proc.poll() is None:
            suspend_process(self._current_proc.pid)

    def resume(self):
        self._is_paused = False
        if self._current_proc and self._current_proc.poll() is None:
            resume_process(self._current_proc.pid)

    def cancel(self):
        self._is_cancelled = True
        if self._current_proc and self._current_proc.poll() is None:
            # Resume first so kill signal is processed
            resume_process(self._current_proc.pid)
            try:
                self._current_proc.kill()
            except Exception:
                pass
        # Clean up partially written file
        if self._current_output_file and os.path.exists(self._current_output_file):
            try:
                time.sleep(0.2)
                os.remove(self._current_output_file)
            except Exception:
                pass

    def run(self):
        logger.info(f"Starting SplitWorker for: {self.source_file}")
        self._created_files.clear()

        # 1. Validate source file
        if not os.path.isfile(self.source_file):
            self.sig_error.emit(t("msg_select_video_first"))
            return

        self.sig_status.emit(t("status_analyzing"))
        info = probe_video(self.source_file)
        if not info or info["duration"] <= 0:
            logger.error(f"Cannot decode or probe video: {self.source_file}")
            self.sig_error.emit(t("msg_file_corrupt"))
            return

        total_duration = info["duration"]
        base_name, ext = os.path.splitext(os.path.basename(self.source_file))
        if not ext:
            ext = ".mp4"

        # 2. Check disk space
        if settings.get("disk_check_enabled", True):
            min_gb = float(settings.get("min_disk_gb", 3.0))
            # Estimated needed space roughly equal to original size
            needed_gb = max(min_gb, info["size_bytes"] / (1024 ** 3))
            sufficient, free_gb, drive = has_sufficient_disk_space(self.output_dir, needed_gb)
            if not sufficient:
                msg = t("msg_disk_full", needed=f"{needed_gb:.1f}", free=f"{free_gb:.1f}", drive=drive)
                logger.error(msg)
                self.sig_error.emit(msg)
                return

        os.makedirs(self.output_dir, exist_ok=True)

        # 3. Calculate cut segments [(start_sec, duration_sec)]
        segments: List[Tuple[float, float]] = []

        if self.split_mode == "duration":
            step = self.duration_sec
            curr = 0.0
            while curr < total_duration:
                dur = min(step, total_duration - curr)
                if dur > 0.1:
                    segments.append((curr, dur))
                curr += step

        elif self.split_mode == "parts":
            step = total_duration / self.num_parts
            for i in range(self.num_parts):
                start = i * step
                dur = min(step, total_duration - start)
                if dur > 0.1:
                    segments.append((start, dur))

        elif self.split_mode == "size":
            # Estimate duration corresponding to target MB
            total_size_mb = max(1.0, info["size_bytes"] / (1024 * 1024))
            estimated_parts = max(1, int(round(total_size_mb / self.target_size_mb)))
            step = total_duration / estimated_parts
            curr = 0.0
            while curr < total_duration:
                dur = min(step, total_duration - curr)
                if dur > 0.1:
                    segments.append((curr, dur))
                curr += step

        elif self.split_mode == "smart":
            # Silence based detection
            silence_pts = detect_silence_points(self.source_file, self.silence_thresh, self.silence_dur)
            if not silence_pts:
                # Fallback to 60s duration
                step = 60.0
                curr = 0.0
                while curr < total_duration:
                    dur = min(step, total_duration - curr)
                    segments.append((curr, dur))
                    curr += step
            else:
                pts = [0.0] + [p for p in silence_pts if 0.0 < p < total_duration] + [total_duration]
                pts = sorted(list(set(pts)))
                for i in range(len(pts) - 1):
                    start = pts[i]
                    dur = pts[i + 1] - start
                    if dur >= 1.0:  # ignore sub-second noise
                        segments.append((start, dur))

        if not segments:
            self.sig_error.emit(t("msg_file_corrupt"))
            return

        total_parts = len(segments)
        logger.info(f"Splitting video into {total_parts} segments.")

        ffmpeg = get_ffmpeg_path()
        encoder, encoder_label = get_working_video_encoder(self.hw_accel)

        start_time_all = time.time()

        for idx, (seg_start, seg_dur) in enumerate(segments, start=1):
            if self._is_cancelled:
                self.sig_cancelled.emit()
                return

            while self._is_paused:
                if self._is_cancelled:
                    self.sig_cancelled.emit()
                    return
                time.sleep(0.3)

            # Generate output filename
            part_str = f"{idx:03d}"
            try:
                out_name = self.naming_pattern.format(
                    name=base_name,
                    index=idx,
                    part=idx,
                    total=total_parts
                )
            except Exception:
                out_name = f"{base_name}_Part_{part_str}"

            if not out_name.lower().endswith(ext.lower()):
                out_name += ext

            out_path = os.path.join(self.output_dir, out_name)
            self._current_output_file = out_path

            status_text = t("status_splitting", current=idx, total=total_parts)
            self.sig_status.emit(status_text)
            self.sig_part_started.emit(idx, total_parts, out_name)

            # Build FFmpeg command
            cmd = [ffmpeg, "-y"]

            # Keyframe fast seek before -i
            cmd.extend(["-ss", f"{seg_start:.3f}", "-i", self.source_file, "-t", f"{seg_dur:.3f}"])

            if self.fast_mode:
                # Stream copy: ultra-fast, lossless
                cmd.extend([
                    "-c", "copy",
                    "-avoid_negative_ts", "make_zero",
                    "-map", "0"
                ])
            else:
                # Precise mode: re-encode with exact frames
                cmd.extend(["-c:v", encoder])
                if encoder == "libx264":
                    cmd.extend(["-preset", "veryfast", "-crf", "22"])
                elif "nvenc" in encoder:
                    cmd.extend(["-preset", "p4", "-cq", "24"])
                elif "qsv" in encoder:
                    cmd.extend(["-global_quality", "23"])

                # Video filter presets
                vf_filters = []
                if self.output_preset == "1080p":
                    vf_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black")
                elif self.output_preset == "720p":
                    vf_filters.append("scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black")
                elif self.output_preset == "vertical":
                    # 9:16 vertical for Shorts / TikTok / Reels
                    vf_filters.append("scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black")

                if vf_filters:
                    cmd.extend(["-vf", ",".join(vf_filters)])

                cmd.extend(["-c:a", "aac", "-b:a", "192k"])

            cmd.extend(["-progress", "pipe:1", out_path])

            logger.info(f"Running part {idx}/{total_parts}: {' '.join(cmd[:8])}...")

            try:
                self._current_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_NO_WINDOW
                )

                part_time_elapsed = 0.0
                speed_str = "1.0x"

                while True:
                    if self._is_cancelled:
                        self.cancel()
                        self.sig_cancelled.emit()
                        return

                    line = self._current_proc.stdout.readline()
                    if not line:
                        if self._current_proc.poll() is not None:
                            break
                        continue

                    line = line.strip()
                    if "=" in line:
                        key, val = line.split("=", 1)
                        if key == "out_time_us":
                            try:
                                out_sec = float(val) / 1000000.0
                                part_pct = min(100.0, (out_sec / seg_dur) * 100.0)
                                # Overall percent calculation
                                overall_done_sec = sum(s[1] for s in segments[:idx - 1]) + out_sec
                                overall_pct = min(100.0, (overall_done_sec / total_duration) * 100.0)

                                # ETA calculation
                                elapsed = time.time() - start_time_all
                                if overall_pct > 1.0:
                                    eta_sec = (elapsed / (overall_pct / 100.0)) - elapsed
                                    eta_str = format_duration(eta_sec)
                                else:
                                    eta_str = "--:--"

                                self.sig_progress.emit(part_pct, overall_pct, eta_str, speed_str)
                            except Exception:
                                pass
                        elif key == "speed":
                            speed_str = val.strip()

                ret = self._current_proc.wait()
                if self._is_cancelled:
                    self.sig_cancelled.emit()
                    return

                if ret != 0:
                    logger.error(f"FFmpeg error on part {idx}, return code: {ret}")
                    self.sig_error.emit(f"FFmpeg error on part {idx}")
                    return

                self._created_files.append(out_path)
                self.sig_part_done.emit(idx, out_path)

            except Exception as e:
                logger.error(f"Exception during split part {idx}: {e}")
                self.sig_error.emit(str(e))
                return

        self.sig_progress.emit(100.0, 100.0, "00:00:00", speed_str)
        self.sig_status.emit(t("status_completed"))
        self.sig_finished.emit(self._created_files)
        logger.info(f"Split completed successfully. {len(self._created_files)} files created.")
