# ស្ដេចកាត់វីដេអូ (King Video Cutter)

> **Professional Windows Desktop Video Splitting & Merging Application**  
> Simple, fast, offline video tool with native Khmer (ភាសាខ្មែរ) and English language support.

![King Video Cutter Icon](assets/icons/app_icon.png)

---

## 🌟 Key Features

### 1. Auto-Split (កាត់ជាភាគខ្លីៗ)
- **Drag & Drop**: Easily drop any video format (`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.ts`, `.flv`).
- **Flexible Split Modes**:
  - **By Duration**: e.g., Every 30s, 1m, 3m, 5m, 10m, or custom duration.
  - **By Number of Parts**: Split equally into $N$ parts (e.g. 10 parts).
  - **By File Size**: e.g., Each part max 50 MB, 100 MB.
  - **Smart Split**: Audio silence detection (`silencedetect`) to cut at natural pauses.
- **Cutting Engines**:
  - **Fast Mode (Lossless)**: Stream copy (`-c copy`), ultra-fast, 100% original quality, zero re-encoding.
  - **Precise Mode**: Re-encode for millisecond-exact cut points.
- **Presets**: Original, 1080p FHD, 720p HD, and **Vertical 9:16** (optimized for TikTok, YouTube Shorts, Facebook Reels).
- **Video Preview Player**: Embedded player with visual cut markers displayed directly on the timeline scrubber.
- **Multi-Hour Video Stability**: Built to handle 5+ hour recordings without memory bloat or UI freezes.

### 2. Merge (បញ្ចូលជាវីដេអូវែង)
- **Multi-Clip Concat**: Add multiple video clips and reorder them with drag-and-drop or Move Up / Move Down buttons.
- **Natural File Sorting**: Sorts filenames cleanly using natural ordering (`1, 2, 10` instead of `1, 10, 2`).
- **Smart Engine Detection**:
  - **Lossless Concat Demuxer**: Instant merge when video/audio codecs and resolutions match.
  - **Auto-Normalization Filter**: Automatically scales differing resolutions and standardizes frame rates.
- **Creative Additions**:
  - Add smooth crossfade transitions between clips.
  - Add background music (BGM) with adjustable volume.
  - Add custom Intro and Outro video clips.

### 3. User Interface & Experience (UI / UX)
- **Instant Runtime Language Switching**:
  - Toggle between **Khmer (ភាសាខ្មែរ)** and **English** with one click in the top bar (`ខ្មែរ | EN`) without restarting.
  - 100% translated: labels, buttons, dialogs, tooltips, progress stats, and error prompts.
- **Embedded Khmer Font**: Bundled `Noto Sans Khmer` font loaded at startup to ensure pristine rendering of subscripts, vowels, and signs.
- **Sleek Modern Themes**: Instant toggle between Dark Slate Mode and Light Mode.
- **Batch Processing Queue**: Queue multiple split and merge tasks and process them sequentially in the background.
- **Live Hardware Badge**: Automatically detects GPU hardware acceleration (`NVIDIA NVENC`, `Intel QuickSync`, `AMD AMF`) with graceful CPU fallback (`libx264`).
- **Storage Protection**: Pre-checks free disk space before processing to prevent disk-full crashes.

---

## 🛠️ Project Structure

```
TG Cut/
├── main.py                     # Application entry point (DPI, fonts, theme, MainWindow)
├── king_cutter.spec            # PyInstaller packaging configuration
├── build_exe.py                # Automated script to build standalone Windows application
├── installer.iss               # Inno Setup script to create single .exe installer
├── requirements.txt            # Python dependencies (PySide6, pyinstaller)
├── README.md                   # Complete documentation and user guide
├── core/
│   ├── disk_utils.py           # Disk storage validation and free space monitoring
│   ├── ffmpeg_utils.py         # FFmpeg binary resolution, probing, and GPU detection
│   ├── i18n.py                 # Multi-language translation engine with runtime switching
│   ├── logger.py               # Centralized UTF-8 logging (logs/king_video_cutter.log)
│   ├── merger.py               # Video merging engine (Fast demuxer + Normalized filter)
│   ├── queue_manager.py        # Sequential batch job processing manager
│   ├── settings.py             # Persistent JSON settings manager
│   └── splitter.py             # Video auto-splitting engine (Fast + Precise modes)
├── ui/
│   ├── main_window.py          # Main application window, header, tabs, and status bar
│   ├── split_tab.py            # Auto-split interface, drop area, preview, and options
│   ├── merge_tab.py            # Video merging interface, clip table, and settings
│   ├── queue_tab.py            # Batch processing queue interface
│   ├── preview_player.py       # Embedded video player with visual cut markers
│   ├── settings_dialog.py      # App preferences modal (Language, Theme, GPU, Storage)
│   └── theme.py                # Dark and Light QSS styling with Khmer typography
├── assets/
│   ├── bin/                    # Bundled Windows 64-bit binaries
│   │   ├── ffmpeg.exe          # FFmpeg executable
│   │   └── ffprobe.exe         # FFprobe executable
│   ├── fonts/
│   │   └── NotoSansKhmer.ttf   # Embedded Khmer font
│   └── icons/
│       ├── app_icon.png        # High-resolution application logo
│       └── app_icon.ico        # Windows executable and installer icon
├── locales/
│   ├── km.json                 # Complete Khmer translation dictionary
│   └── en.json                 # Complete English translation dictionary
└── tests/
    └── test_functional.py      # Automated test suite (Split, Merge, Khmer paths, Cancel)
```

---

## 🚀 Getting Started

### Prerequisites
- Windows 10 or Windows 11 (64-bit)
- Python 3.11+ installed

### 1. Setup Virtual Environment
Open PowerShell or Command Prompt in the project folder:
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run from Source
```powershell
python main.py
```

---

## 📦 Building the Standalone Executable & Installer

### Step 1: Build Standalone Executable (.exe)
Run the automated build script:
```powershell
python build_exe.py
```
This compiles the application using PyInstaller and outputs the complete portable bundle to:
```
dist\KingVideoCutter\KingVideoCutter.exe
```
All required dependencies—including Python runtime, Qt libraries, Khmer fonts, translation files, and FFmpeg/FFprobe binaries—are bundled automatically.

### Step 2: Build the Windows Setup Installer (.exe)
1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php) (free).
2. Right-click on `installer.iss` and choose **"Compile"**, or run from command line:
   ```cmd
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
   ```
3. The standalone setup wizard will be generated in:
   ```
   installer_output\KingVideoCutter_Setup_v1.0.0.exe
   ```

---

## ✅ Test Checklist & Quality Assurance

Run the automated verification suite:
```powershell
python tests/test_functional.py
```

| # | Test Case | Expected Result | Status |
|---|-----------|-----------------|--------|
| 1 | **Synthetic Video Probe** | Correctly extracts duration, resolution, codecs, fps, and bitrate | Passed |
| 2 | **Fast Auto-Split** | Slices video via stream copy (`-c copy`) in seconds without re-encoding | Passed |
| 3 | **Precise Auto-Split** | Re-encodes exact frame cut points with 720p/1080p/vertical presets | Passed |
| 4 | **Lossless Merge** | Concatenates video segments into a seamless output video | Passed |
| 5 | **Khmer File & Path Handling** | Processes files with names like `វីដេអូតេស្ត_២០២៦.mp4` in Unicode paths | Passed |
| 6 | **Job Pause & Cancelation** | Pauses/resumes Windows processes cleanly; deletes partial files on cancel | Passed |
| 7 | **Instant Language Toggle** | UI switches between Khmer and English instantly without restart | Passed |
| 8 | **Dark / Light Theme** | Stylesheet and contrast adapt dynamically | Passed |

---

## 🔒 Offline & Privacy Guarantee
- 100% offline operation: No internet connection, API keys, or user accounts required.
- All media processing runs locally on your computer.
- Settings are saved locally in `%APPDATA%\KingVideoCutter\settings.json`.
- Logs are stored locally in `%APPDATA%\KingVideoCutter\logs\king_video_cutter.log`.

---

## 📄 License
Released under the MIT License. Built with ❤️ for content creators and video editors.
