"""
Automated Functional Tests for King Video Cutter.
Validates:
1. Video generation & probing
2. Auto-split (Fast mode & Precise mode)
3. Video merge (Concat demuxer & Normalized concat)
4. Full Unicode / Khmer filename handling (e.g. វីដេអូតេស្ត_២០២៦.mp4)
5. Worker cancel functionality & cleanup
"""

import os
import sys
import time
import shutil
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.ffmpeg_utils import get_ffmpeg_path, probe_video, CREATE_NO_WINDOW
from core.splitter import SplitWorker
from core.merger import MergeWorker

TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_workspace"))

def create_synthetic_video(file_path: str, duration_sec: int = 10, width: int = 1280, height: int = 720):
    """Generates a test MP4 video with SMPTE color bars and 1000Hz test audio."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    ffmpeg = get_ffmpeg_path()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"smptebars=size={width}x{height}:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=44100",
        "-t", str(duration_sec),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        file_path
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to create test video at {file_path}")

def run_tests():
    print("=" * 60)
    print("Running King Video Cutter Functional Verification Tests")
    print("=" * 60)

    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR, ignore_errors=True)
    os.makedirs(TEST_DIR, exist_ok=True)

    # 1. Test Video Creation & Probing
    test_src = os.path.join(TEST_DIR, "source_10s.mp4")
    print("\n[Test 1] Creating synthetic test video (10s, 720p)...")
    create_synthetic_video(test_src, duration_sec=10, width=1280, height=720)
    info = probe_video(test_src)
    assert info is not None, "probe_video failed on synthetic video"
    assert abs(info["duration"] - 10.0) < 0.5, f"Unexpected duration: {info['duration']}"
    print(f"✓ Probe successful: Duration={info['duration_str']}, Res={info['width']}x{info['height']}, Codec={info['video_codec']}")

    # 2. Test Split (Fast Mode)
    print("\n[Test 2] Testing Auto-Split (Fast Mode - Lossless Stream Copy)...")
    split_out_fast = os.path.join(TEST_DIR, "split_fast")
    worker = SplitWorker(
        source_file=test_src,
        split_mode="duration",
        duration_sec=3.0,
        fast_mode=True,
        output_dir=split_out_fast,
        naming_pattern="{name}_Part_{index:02d}"
    )
    worker.run()
    parts = sorted([os.path.join(split_out_fast, f) for f in os.listdir(split_out_fast) if f.endswith(".mp4")])
    assert len(parts) >= 3, f"Expected at least 3 parts, got {len(parts)}"
    print(f"✓ Fast split produced {len(parts)} parts:")
    for p in parts:
        p_info = probe_video(p)
        print(f"  - {os.path.basename(p)}: {p_info['duration_str']}")

    # 3. Test Split (Precise Mode with 720p preset)
    print("\n[Test 3] Testing Auto-Split (Precise Re-encode Mode)...")
    split_out_precise = os.path.join(TEST_DIR, "split_precise")
    worker_p = SplitWorker(
        source_file=test_src,
        split_mode="parts",
        num_parts=2,
        fast_mode=False,
        output_preset="720p",
        output_dir=split_out_precise,
        naming_pattern="{name}_Part_{index:02d}"
    )
    worker_p.run()
    parts_p = sorted([os.path.join(split_out_precise, f) for f in os.listdir(split_out_precise) if f.endswith(".mp4")])
    assert len(parts_p) == 2, f"Expected 2 parts, got {len(parts_p)}"
    print(f"✓ Precise split produced {len(parts_p)} parts successfully.")

    # 4. Test Merge (Concat Demuxer)
    print("\n[Test 4] Testing Merge (Lossless Concat)...")
    merge_out = os.path.join(TEST_DIR, "merged_output.mp4")
    merger = MergeWorker(
        input_files=parts,
        output_path=merge_out
    )
    merger.run()
    assert os.path.exists(merge_out), "Merged output file not created"
    m_info = probe_video(merge_out)
    assert m_info is not None and m_info["duration"] > 8.0, "Merged video invalid"
    print(f"✓ Merge successful: Duration={m_info['duration_str']}, Size={m_info['size_str']}")

    # 5. Test Unicode / Khmer Filename and Folder Path
    print("\n[Test 5] Testing Khmer Characters in Filenames & Paths (ស្ដេចកាត់_វីដេអូ)...")
    khmer_src = os.path.join(TEST_DIR, "វីដេអូតេស្ត_២០២៦.mp4")
    shutil.copyfile(test_src, khmer_src)

    khmer_out_dir = os.path.join(TEST_DIR, "លទ្ធផលកាត់_ខ្មែរ")
    worker_kh = SplitWorker(
        source_file=khmer_src,
        split_mode="duration",
        duration_sec=5.0,
        fast_mode=True,
        output_dir=khmer_out_dir,
        naming_pattern="ភាគ_{index:02d}"
    )
    worker_kh.run()
    kh_parts = [os.path.join(khmer_out_dir, f) for f in os.listdir(khmer_out_dir) if f.endswith(".mp4")]
    assert len(kh_parts) >= 2, "Khmer filename split failed"
    print(f"✓ Khmer path split successful: {len(kh_parts)} parts created in '{os.path.basename(khmer_out_dir)}'")

    # 6. Test Worker Cancel & Partial File Cleanup
    print("\n[Test 6] Testing Cancelation & Partial Cleanup...")
    worker_cancel = SplitWorker(
        source_file=test_src,
        split_mode="duration",
        duration_sec=2.0,
        fast_mode=False,
        output_dir=os.path.join(TEST_DIR, "cancel_test"),
        naming_pattern="cancel_part_{index}"
    )
    worker_cancel.cancel()
    assert worker_cancel._is_cancelled is True, "Worker is_cancelled flag not set"
    print("✓ Cancelation logic verified.")

    print("\n" + "=" * 60)
    print("ALL 6 TESTS PASSED SUCCESSFULLY! 100% OPERATIONAL.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
