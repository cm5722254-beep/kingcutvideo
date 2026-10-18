"""
Entry point for "ស្ដេចកាត់វីដេអូ" (King Video Cutter).
Initializes Qt application, loads embedded Khmer fonts, sets high DPI scaling,
applies selected theme and language, and launches MainWindow.
"""

import os
import sys

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QFontDatabase, QFont, QIcon
from PySide6.QtWidgets import QApplication

from core.i18n import set_language, get_base_dir
from core.settings import settings
from core.logger import logger
from ui.theme import get_stylesheet
from ui.main_window import MainWindow

def main():
    # Force UTF-8 encoding on Windows console
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    logger.info("Initializing King Video Cutter (ស្ដេចកាត់វីដេអូ)...")

    # High DPI Scaling
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("KingVideoCutter")
    app.setOrganizationName("KingTools")

    # Load App Icon
    base_dir = get_base_dir()
    icon_path = os.path.join(base_dir, "assets", "icons", "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Load Embedded Khmer Font (Noto Sans Khmer)
    font_path = os.path.join(base_dir, "assets", "fonts", "NotoSansKhmer.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app_font = QFont(families[0], 10)
                app.setFont(app_font)
                logger.info(f"Loaded embedded font: {families[0]}")
    else:
        logger.warning(f"Font file not found at: {font_path}")

    # Set Initial Language from settings (Default: Khmer 'km')
    current_lang = settings.get("language", "km")
    set_language(current_lang)

    # Set Initial Theme (Default: 'dark')
    current_theme = settings.get("theme", "dark")
    app.setStyleSheet(get_stylesheet(current_theme))

    # Launch Main Window
    window = MainWindow()
    window.show()

    logger.info("Application started successfully.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
