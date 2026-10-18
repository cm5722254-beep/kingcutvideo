"""
FFmpeg & FFprobe utilities for King Video Cutter.
Handles binary detection, video probing, GPU hardware acceleration detection,
silence detection, and process execution flags.
"""

import os
import sys
import json
import re
import subprocess
from typing import Dict, Any, Optional, List, Tuple

# Windows flag to suppress terminal window popping up
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

def get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def get_ffmpeg_path() -> str:
    """Finds bundled ffmpeg.exe first, then falls back to system PATH."""
    base_dir = get_base_dir()
    bundled_paths = [
        os.path.join(base_dir, "assets", "bin", "ffmpeg.exe"),
        os.path.join(base_dir, "bin", "ffmpeg.exe"),
        os.path.join(base_dir, "ffmpeg.exe"),
    ]
    for p in bundled_paths:
        if os.path.isfile(p):
            return p
    # Fallback to system path
    import shutil
    sys_path = shutil.which("ffmpeg")
    return sys_path if sys_path else "ffmpeg"

def get_ffprobe_path() -> str:
    """Finds bundled ffprobe.exe first, then falls back to system PATH."""
    base_dir = get_base_dir()
    bundled_paths = [
        os.path.join(base_dir, "assets", "bin", "ffprobe.exe"),
        os.path.join(base_dir, "bin", "ffprobe.exe"),
        os.path.join(base_dir, "ffprobe.exe"),
    ]
    for p in bundled_paths:
        if os.path.isfile(p):
            return p
    import shutil
    sys_path = shutil.which("ffprobe")
    return sys_path if sys_path else "ffprobe"

def format_duration(seconds: float) -> str:
    """Formats seconds into HH:MM:SS or MM:SS."""
    if seconds < 0:
        seconds = 0
    total_sec = int(round(seconds))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def format_file_size(size_bytes: int) -> str:
    """Formats byte count to human-readable string like '4.8 GB' or '45.2 MB'."""
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024 ** 3):.1f} GB"
    elif size_bytes >= 1024 ** 2:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"

def probe_video(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Runs ffprobe on given video and parses duration, resolution, codecs, bitrate, size.
    Returns structured dict or None if invalid/corrupt.
    """
    if not os.path.isfile(file_path):
        return None

    ffprobe = get_ffprobe_path()
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-print_format", "json",
        file_path
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None

        data = json.loads(proc.stdout)
        format_info = data.get("format", {})
        streams = data.get("streams", [])

        # Find primary video stream and audio stream
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        duration = 0.0
        if "duration" in format_info:
            try:
                duration = float(format_info["duration"])
            except ValueError:
                pass
        elif video_stream and "duration" in video_stream:
            try:
                duration = float(video_stream["duration"])
            except ValueError:
                pass

        size_bytes = 0
        if "size" in format_info:
            try:
                size_bytes = int(format_info["size"])
            except ValueError:
                pass
        if size_bytes == 0 and os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)

        width = 0
        height = 0
        vcodec = "unknown"
        fps = 30.0
        if video_stream:
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            vcodec = video_stream.get("codec_name", "unknown")
            r_frame_rate = video_stream.get("r_frame_rate", "30/1")
            try:
                if "/" in r_frame_rate:
                    num, den = r_frame_rate.split("/")
                    fps = float(num) / float(den) if float(den) != 0 else 30.0
                else:
                    fps = float(r_frame_rate)
            except Exception:
                fps = 30.0

        acodec = audio_stream.get("codec_name", "none") if audio_stream else "none"

        # Determine readable resolution tag like 1080p, 720p, 4K
        res_tag = f"{width}x{height}"
        if height == 1080 or width == 1920:
            res_tag = "1080p"
        elif height == 720 or width == 1280:
            res_tag = "720p"
        elif height == 2160 or width == 3840:
            res_tag = "4K"
        elif height == 480 or width == 854:
            res_tag = "480p"

        return {
            "path": file_path,
            "filename": os.path.basename(file_path),
            "duration": duration,
            "duration_str": format_duration(duration),
            "size_bytes": size_bytes,
            "size_str": format_file_size(size_bytes),
            "width": width,
            "height": height,
            "resolution_str": res_tag,
            "fps": fps,
            "video_codec": vcodec,
            "audio_codec": acodec,
            "bitrate": int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else 0
        }
    except Exception as e:
        print(f"probe_video error for {file_path}: {e}", file=sys.stderr)
        return None

_detected_hw_encoder = None

def get_working_video_encoder(preference: str = "auto") -> Tuple[str, str]:
    """
    Checks hardware encoders support and returns (encoder_name, label).
    preference: 'auto', 'nvenc', 'qsv', 'amf', 'none'
    """
    global _detected_hw_encoder
    if preference != "auto":
        if preference == "nvenc":
            return "h264_nvenc", "GPU (NVIDIA NVENC)"
        elif preference == "qsv":
            return "h264_qsv", "GPU (Intel QuickSync)"
        elif preference == "amf":
            return "h264_amf", "GPU (AMD AMF)"
        return "libx264", "CPU"

    if _detected_hw_encoder is not None:
        return _detected_hw_encoder

    ffmpeg = get_ffmpeg_path()
    candidates = [
        ("h264_nvenc", "GPU (NVIDIA)"),
        ("h264_qsv", "GPU (Intel)"),
        ("h264_amf", "GPU (AMD)")
    ]

    for enc, label in candidates:
        try:
            # Test encoding 1 frame of synthetic color with encoder
            test_cmd = [
                ffmpeg,
                "-y",
                "-f", "lavfi",
                "-i", "color=c=black:s=64x64:d=0.1",
                "-c:v", enc,
                "-f", "null",
                "-"
            ]
            res = subprocess.run(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW,
                timeout=5
            )
            if res.returncode == 0:
                _detected_hw_encoder = (enc, label)
                return _detected_hw_encoder
        except Exception:
            continue

    # Fallback to standard CPU libx264
    _detected_hw_encoder = ("libx264", "CPU")
    return _detected_hw_encoder

def natural_sort_key(s: str) -> List[Any]:
    """Sort strings containing numbers in human order: 1, 2, 10 instead of 1, 10, 2."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def detect_silence_points(file_path: str, noise_db: int = -30, min_duration: float = 0.5) -> List[float]:
    """
    Uses ffmpeg silencedetect audio filter to find silence timestamps.
    Returns list of cut timestamp points (seconds).
    """
    ffmpeg = get_ffmpeg_path()
    cmd = [
        ffmpeg,
        "-i", file_path,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null",
        "-"
    ]
    points = []
    try:
        proc = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW
        )
        for line in proc.stderr:
            if "silence_end:" in line:
                match = re.search(r"silence_end:\s*([0-9.]+)", line)
                if match:
                    points.append(float(match.group(1)))
        proc.wait()
    except Exception as e:
        print(f"Error in silence detection: {e}", file=sys.stderr)
    return points

SUPPORTED_VIDEO_EXTENSIONS = (
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".ts", ".flv", ".m4v", ".wmv", ".3gp", ".vob", ".mpg", ".mpeg"
)

def scan_video_files(folder_or_path: str, recursive: bool = False) -> List[str]:
    """
    Finds all supported video files in a folder or returns the file if it is a video.
    Returns list of paths sorted with natural alphanumeric ordering (1, 2, 10).
    """
    if not os.path.exists(folder_or_path):
        return []

    if os.path.isfile(folder_or_path):
        if folder_or_path.lower().endswith(SUPPORTED_VIDEO_EXTENSIONS):
            return [folder_or_path]
        return []

    videos = []
    if recursive:
        for root, _, files in os.walk(folder_or_path):
            for f in files:
                if f.lower().endswith(SUPPORTED_VIDEO_EXTENSIONS):
                    videos.append(os.path.join(root, f))
    else:
        try:
            for f in os.listdir(folder_or_path):
                full_path = os.path.join(folder_or_path, f)
                if os.path.isfile(full_path) and f.lower().endswith(SUPPORTED_VIDEO_EXTENSIONS):
                    videos.append(full_path)
        except Exception as e:
            print(f"Error scanning directory {folder_or_path}: {e}", file=sys.stderr)

    videos.sort(key=lambda p: natural_sort_key(os.path.basename(p)))
    return videos

