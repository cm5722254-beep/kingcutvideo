"""
Automated Build Script for King Video Cutter (ស្ដេចកាត់វីដេអូ).
Builds standalone Windows 64-bit application using PyInstaller and verifies outputs.
"""

import os
import sys
import shutil
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def build():
    print("=" * 60)
    print("Building King Video Cutter Desktop Standalone Executable")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(base_dir, "king_cutter.spec")

    if not os.path.exists(spec_file):
        print(f"Error: Spec file not found at {spec_file}", file=sys.stderr)
        sys.exit(1)

    # Check ffmpeg and ffprobe
    ffmpeg_exe = os.path.join(base_dir, "assets", "bin", "ffmpeg.exe")
    ffprobe_exe = os.path.join(base_dir, "assets", "bin", "ffprobe.exe")
    if not os.path.exists(ffmpeg_exe) or not os.path.exists(ffprobe_exe):
        print("Warning: FFmpeg/FFprobe binaries missing in assets/bin/!", file=sys.stderr)

    # Clean previous build artifacts
    for d in ["build", "dist"]:
        dp = os.path.join(base_dir, d)
        if os.path.exists(dp):
            print(f"Cleaning previous {d}/ directory...")
            try:
                shutil.rmtree(dp)
            except Exception as e:
                print(f"Note: Could not fully remove {d}: {e}")

    # Run PyInstaller
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "-y", spec_file]
    print("Running command:", " ".join(cmd))
    ret = subprocess.run(cmd, cwd=base_dir)

    if ret.returncode != 0:
        print(f"\nBuild FAILED with return code: {ret.returncode}", file=sys.stderr)
        sys.exit(ret.returncode)

    output_exe = os.path.join(base_dir, "dist", "KingVideoCutter", "KingVideoCutter.exe")
    if os.path.exists(output_exe):
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print(f"Executable output: {output_exe}")
        print("=" * 60)
    else:
        print(f"\nBuild finished but {output_exe} was not found!", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    build()
