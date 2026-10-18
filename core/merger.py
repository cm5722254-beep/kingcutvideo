"""
Merger engine for King Video Cutter.
Combines multiple video clips into one long video.
Supports fast lossless stream-copy merge when codecs match,
and automatic normalization & re-encoding (with transitions, BGM, intro/outro) when they differ.
Executes in background QThread with real-time FFmpeg progress, pause/resume, and cancel.
"""

import os
import sys
import time
import tempfile
import subprocess
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QThread, Signal

from core.ffmpeg_utils import (
    get_ffmpeg_path,
    probe_video,
    get_working_video_encoder,
    format_duration,
    natural_sort_key,
    CREATE_NO_WINDOW
)
from core.splitter import suspend_process, resume_process
from core.disk_utils import has_sufficient_disk_space
from core.settings import settings
from core.logger import logger
from core.i18n import t

class MergeWorker(QThread):
    sig_status = Signal(str)
    sig_progress = Signal(float, str, str)  # overall_pct, eta_str, speed_str
    sig_finished = Signal(str)             # output file path
    sig_error = Signal(str)                # error message
    sig_cancelled = Signal()

    def __init__(
        self,
        input_files: List[str],
        output_path: str,
        add_transition: bool = False,
        transition_dur: float = 1.0,
        bgm_file: Optional[str] = None,
        bgm_volume: float = 0.2,
        intro_file: Optional[str] = None,
        outro_file: Optional[str] = None,
        hw_accel: str = "auto",
        output_preset: str = "original",
        trim_start: float = 0.0,
        trim_end: float = 0.0,
        parent=None
    ):
        super().__init__(parent)
        self.input_files = list(input_files)
        self.output_path = output_path
        self.add_transition = add_transition
        self.transition_dur = max(0.5, float(transition_dur))
        self.bgm_file = bgm_file if bgm_file and os.path.isfile(bgm_file) else None
        self.bgm_volume = max(0.0, min(1.0, float(bgm_volume)))
        self.intro_file = intro_file if intro_file and os.path.isfile(intro_file) else None
        self.outro_file = outro_file if outro_file and os.path.isfile(outro_file) else None
        self.hw_accel = hw_accel
        self.output_preset = output_preset
        self.trim_start = max(0.0, float(trim_start))
        self.trim_end = max(0.0, float(trim_end))

        self._is_paused = False
        self._is_cancelled = False
        self._current_proc: Optional[subprocess.Popen] = None
        self._temp_concat_file: Optional[str] = None

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
            resume_process(self._current_proc.pid)
            try:
                self._current_proc.kill()
            except Exception:
                pass
        # Clean up partial output file
        if self.output_path and os.path.exists(self.output_path):
            try:
                time.sleep(0.2)
                os.remove(self.output_path)
            except Exception:
                pass

    def run(self):
        logger.info(f"Starting MergeWorker with {len(self.input_files)} clips -> {self.output_path}")

        # Assemble full list with optional intro and outro
        all_clips: List[str] = []
        if self.intro_file:
            all_clips.append(self.intro_file)
        all_clips.extend(self.input_files)
        if self.outro_file:
            all_clips.append(self.outro_file)

        if len(all_clips) < 2:
            self.sig_error.emit(t("msg_select_two_videos"))
            return

        # Check existing and valid
        valid_clips = []
        for p in all_clips:
            if os.path.isfile(p):
                valid_clips.append(p)
            else:
                logger.warning(f"File not found: {p}")

        if len(valid_clips) < 2:
            self.sig_error.emit(t("msg_select_two_videos"))
            return

        self.sig_status.emit(t("status_analyzing"))

        # Probe each clip
        probes: List[Dict[str, Any]] = []
        total_duration = 0.0
        total_size_bytes = 0

        for clip in valid_clips:
            pr = probe_video(clip)
            if not pr or pr["duration"] <= 0:
                logger.error(f"Cannot probe video clip: {clip}")
                self.sig_error.emit(t("msg_file_corrupt"))
                return
            probes.append(pr)
            total_duration += pr["duration"]
            total_size_bytes += pr["size_bytes"]

        ffmpeg = get_ffmpeg_path()
        trim_temp_dir = None
        if self.trim_start > 0 or self.trim_end > 0:
            logger.info(f"Applying per-clip trim: start={self.trim_start}s, end={self.trim_end}s")
            self.sig_status.emit("Trimming intro/outro from clips...")
            trimmed_clips = []
            trim_temp_dir = tempfile.mkdtemp(prefix="tgcut_trim_")
            for idx, clip in enumerate(valid_clips):
                dur = probes[idx]["duration"]
                start_sec = self.trim_start
                out_dur = max(0.5, dur - self.trim_start - self.trim_end)
                temp_out = os.path.join(trim_temp_dir, f"trim_{idx:04d}.mp4")
                trim_cmd = [
                    ffmpeg, "-y",
                    "-ss", f"{start_sec:.3f}",
                    "-i", clip,
                    "-t", f"{out_dur:.3f}",
                    "-c", "copy",
                    temp_out
                ]
                subprocess.run(trim_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
                if os.path.exists(temp_out):
                    trimmed_clips.append(temp_out)
                else:
                    trimmed_clips.append(clip)
            valid_clips = trimmed_clips

        # Check disk space
        out_dir = os.path.dirname(os.path.abspath(self.output_path))
        os.makedirs(out_dir, exist_ok=True)

        if settings.get("disk_check_enabled", True):
            min_gb = float(settings.get("min_disk_gb", 3.0))
            needed_gb = max(min_gb, (total_size_bytes * 1.2) / (1024 ** 3))
            sufficient, free_gb, drive = has_sufficient_disk_space(out_dir, needed_gb)
            if not sufficient:
                msg = t("msg_disk_full", needed=f"{needed_gb:.1f}", free=f"{free_gb:.1f}", drive=drive)
                logger.error(msg)
                self.sig_error.emit(msg)
                return

        # Check if fast stream-copy concat is possible
        # Requires: no transitions, no BGM, matching vcodec, acodec, width, height, fps
        first = probes[0]
        can_fast_concat = (
            not self.add_transition and
            not self.bgm_file and
            self.output_preset == "original" and
            all(
                p["video_codec"] == first["video_codec"] and
                p["audio_codec"] == first["audio_codec"] and
                p["width"] == first["width"] and
                p["height"] == first["height"] and
                abs(p["fps"] - first["fps"]) < 0.2
                for p in probes
            )
        )

        ffmpeg = get_ffmpeg_path()
        start_time_all = time.time()
        self.sig_status.emit(t("status_merging"))

        if can_fast_concat:
            logger.info("Matching parameters detected -> Performing FAST concat demuxer (lossless stream copy).")
            # Create temporary concat file
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as tf:
                    self._temp_concat_file = tf.name
                    for clip in valid_clips:
                        # Clean path formatting for FFmpeg concat demuxer
                        escaped_path = clip.replace("\\", "/").replace("'", "'\\''")
                        tf.write(f"file '{escaped_path}'\n")

                cmd = [
                    ffmpeg, "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", self._temp_concat_file,
                    "-c", "copy",
                    "-progress", "pipe:1",
                    self.output_path
                ]
                self._execute_ffmpeg(cmd, total_duration, start_time_all)

            finally:
                if self._temp_concat_file and os.path.exists(self._temp_concat_file):
                    try:
                        os.remove(self._temp_concat_file)
                    except Exception:
                        pass
                if trim_temp_dir and os.path.exists(trim_temp_dir):
                    try:
                        import shutil
                        shutil.rmtree(trim_temp_dir, ignore_errors=True)
                    except Exception:
                        pass
        else:
            logger.info("Parameters differ or filters applied -> Performing normalized re-encode concat.")
            encoder, _ = get_working_video_encoder(self.hw_accel)

            # Determine target resolution
            target_w = 1920
            target_h = 1080
            if self.output_preset == "720p":
                target_w, target_h = 1280, 720
            elif self.output_preset == "1080p":
                target_w, target_h = 1920, 1080
            else:
                # Use max resolution found among clips
                target_w = max(p["width"] for p in probes if p["width"] > 0) or 1920
                target_h = max(p["height"] for p in probes if p["height"] > 0) or 1080

            cmd = [ffmpeg, "-y"]

            # Add each video input
            for clip in valid_clips:
                cmd.extend(["-i", clip])

            # If BGM is provided, add as last input
            bgm_idx = None
            if self.bgm_file:
                bgm_idx = len(valid_clips)
                cmd.extend(["-stream_loop", "-1", "-i", self.bgm_file])

            # Build filter_complex
            filter_parts = []
            num_clips = len(valid_clips)

            for i in range(num_clips):
                filter_parts.append(
                    f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                    f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30[v{i}];"
                    f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]"
                )

            # Concat all inputs
            concat_in = "".join(f"[v{i}][a{i}]" for i in range(num_clips))
            filter_parts.append(f"{concat_in}concat=n={num_clips}:v=1:a=1[vconcat][aconcat]")

            final_v = "[vconcat]"
            final_a = "[aconcat]"

            # Mix BGM if requested
            if bgm_idx is not None:
                filter_parts.append(
                    f"[{bgm_idx}:a]volume={self.bgm_volume:.2f},aformat=sample_rates=44100:channel_layouts=stereo[abgm];"
                    f"[aconcat][abgm]amix=inputs=2:duration=first:dropout_transition=2[afinal]"
                )
                final_a = "[afinal]"

            complex_filter = ";".join(filter_parts)
            cmd.extend(["-filter_complex", complex_filter, "-map", final_v, "-map", final_a])

            # Video encoding options
            cmd.extend(["-c:v", encoder])
            if encoder == "libx264":
                cmd.extend(["-preset", "veryfast", "-crf", "22"])
            elif "nvenc" in encoder:
                cmd.extend(["-preset", "p4", "-cq", "24"])
            elif "qsv" in encoder:
                cmd.extend(["-global_quality", "23"])

            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-progress", "pipe:1", self.output_path])

            self._execute_ffmpeg(cmd, total_duration, start_time_all)

    def _execute_ffmpeg(self, cmd: List[str], total_duration: float, start_time_all: float):
        logger.info(f"Running FFmpeg merge: {' '.join(cmd[:10])}...")
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
                            pct = min(99.0, (out_sec / max(1.0, total_duration)) * 100.0)
                            elapsed = time.time() - start_time_all
                            if pct > 1.0:
                                eta_sec = (elapsed / (pct / 100.0)) - elapsed
                                eta_str = format_duration(eta_sec)
                            else:
                                eta_str = "--:--"
                            self.sig_progress.emit(pct, eta_str, speed_str)
                        except Exception:
                            pass
                    elif key == "speed":
                        speed_str = val.strip()

            ret = self._current_proc.wait()
            if self._is_cancelled:
                self.sig_cancelled.emit()
                return

            if ret != 0:
                logger.error(f"FFmpeg merge error, exit code: {ret}")
                self.sig_error.emit(f"Merge error with exit code {ret}")
                return

            self.sig_progress.emit(100.0, "00:00:00", speed_str)
            self.sig_status.emit(t("status_completed"))
            self.sig_finished.emit(self.output_path)
            logger.info("Merge completed successfully!")

        except Exception as e:
            logger.error(f"Exception during merge: {e}")
            self.sig_error.emit(str(e))
