"""
Settings Dialog for King Video Cutter.
Allows configuring Language, Theme, GPU acceleration, Disk space checks, and output path.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QCheckBox, QDoubleSpinBox,
    QLineEdit, QFileDialog, QGroupBox, QFrame
)

from core.settings import settings
from core.i18n import t, set_language, get_current_language, subscribe_language_change

class SettingsDialog(QDialog):
    sig_theme_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings_title"))
        self.setMinimumWidth(480)
        self.setModal(True)
        self._init_ui()
        subscribe_language_change(self.retranslate_ui)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # General Group
        self.grp_general = QGroupBox(t("settings_general"), self)
        gen_grid = QGridLayout(self.grp_general)
        gen_grid.setSpacing(10)

        # Language
        self.lbl_lang = QLabel(t("settings_language"), self)
        self.combo_lang = QComboBox(self)
        self.combo_lang.addItem("ភាសាខ្មែរ (Khmer)", "km")
        self.combo_lang.addItem("English (EN)", "en")
        curr_lang = get_current_language()
        idx = 0 if curr_lang == "km" else 1
        self.combo_lang.setCurrentIndex(idx)
        gen_grid.addWidget(self.lbl_lang, 0, 0)
        gen_grid.addWidget(self.combo_lang, 0, 1)

        # Theme
        self.lbl_theme = QLabel(t("settings_theme"), self)
        self.combo_theme = QComboBox(self)
        self.combo_theme.addItem(t("settings_theme_dark"), "dark")
        self.combo_theme.addItem(t("settings_theme_light"), "light")
        curr_theme = settings.get("theme", "dark")
        self.combo_theme.setCurrentIndex(0 if curr_theme == "dark" else 1)
        gen_grid.addWidget(self.lbl_theme, 1, 0)
        gen_grid.addWidget(self.combo_theme, 1, 1)

        main_layout.addWidget(self.grp_general)

        # Hardware Acceleration Group
        self.grp_hw = QGroupBox(t("settings_hardware"), self)
        hw_grid = QGridLayout(self.grp_hw)

        self.lbl_hw = QLabel("GPU / Encoder", self)
        self.combo_hw = QComboBox(self)
        self.combo_hw.addItem(t("settings_hw_auto"), "auto")
        self.combo_hw.addItem(t("settings_hw_nvenc"), "nvenc")
        self.combo_hw.addItem(t("settings_hw_qsv"), "qsv")
        self.combo_hw.addItem(t("settings_hw_amf"), "amf")
        self.combo_hw.addItem(t("settings_hw_none"), "none")

        curr_hw = settings.get("hw_accel", "auto")
        hw_indices = {"auto": 0, "nvenc": 1, "qsv": 2, "amf": 3, "none": 4}
        self.combo_hw.setCurrentIndex(hw_indices.get(curr_hw, 0))
        hw_grid.addWidget(self.lbl_hw, 0, 0)
        hw_grid.addWidget(self.combo_hw, 0, 1)

        main_layout.addWidget(self.grp_hw)

        # Storage & Output Group
        self.grp_storage = QGroupBox("Storage & Disk Protection", self)
        stor_grid = QGridLayout(self.grp_storage)

        self.chk_disk = QCheckBox(t("settings_disk_check"), self)
        self.chk_disk.setChecked(settings.get("disk_check_enabled", True))
        stor_grid.addWidget(self.chk_disk, 0, 0, 1, 2)

        self.lbl_min_disk = QLabel(t("settings_min_disk"), self)
        self.spin_min_disk = QDoubleSpinBox(self)
        self.spin_min_disk.setRange(0.5, 50.0)
        self.spin_min_disk.setValue(float(settings.get("min_disk_gb", 3.0)))
        self.spin_min_disk.setSuffix(" GB")
        stor_grid.addWidget(self.lbl_min_disk, 1, 0)
        stor_grid.addWidget(self.spin_min_disk, 1, 1)

        self.lbl_out_dir = QLabel(t("output_folder_label"), self)
        self.txt_out_dir = QLineEdit(self)
        self.txt_out_dir.setText(settings.get("default_output_dir"))
        self.btn_browse = QPushButton(t("browse_folder_btn"), self)
        self.btn_browse.clicked.connect(self._browse_folder)
        stor_grid.addWidget(self.lbl_out_dir, 2, 0)
        stor_grid.addWidget(self.txt_out_dir, 2, 1)
        stor_grid.addWidget(self.btn_browse, 2, 2)

        main_layout.addWidget(self.grp_storage)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_save = QPushButton(t("settings_save_btn"), self)
        self.btn_save.setProperty("variant", "primary")
        self.btn_save.clicked.connect(self._save_settings)

        self.btn_close = QPushButton(t("settings_close_btn"), self)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, t("output_folder_label"), self.txt_out_dir.text())
        if folder:
            self.txt_out_dir.setText(folder)

    def _save_settings(self):
        # Save values
        chosen_lang = self.combo_lang.currentData()
        chosen_theme = self.combo_theme.currentData()
        chosen_hw = self.combo_hw.currentData()

        settings.set("language", chosen_lang)
        settings.set("theme", chosen_theme)
        settings.set("hw_accel", chosen_hw)
        settings.set("disk_check_enabled", self.chk_disk.isChecked())
        settings.set("min_disk_gb", self.spin_min_disk.value())
        settings.set("default_output_dir", self.txt_out_dir.text().strip())

        # Apply Language
        set_language(chosen_lang)

        # Apply Theme signal
        self.sig_theme_changed.emit(chosen_theme)

        self.accept()

    def retranslate_ui(self):
        self.setWindowTitle(t("settings_title"))
        self.grp_general.setTitle(t("settings_general"))
        self.lbl_lang.setText(t("settings_language"))
        self.lbl_theme.setText(t("settings_theme"))
        self.combo_theme.setItemText(0, t("settings_theme_dark"))
        self.combo_theme.setItemText(1, t("settings_theme_light"))
        self.grp_hw.setTitle(t("settings_hardware"))
        self.combo_hw.setItemText(0, t("settings_hw_auto"))
        self.combo_hw.setItemText(1, t("settings_hw_nvenc"))
        self.combo_hw.setItemText(2, t("settings_hw_qsv"))
        self.combo_hw.setItemText(3, t("settings_hw_amf"))
        self.combo_hw.setItemText(4, t("settings_hw_none"))
        self.chk_disk.setText(t("settings_disk_check"))
        self.lbl_min_disk.setText(t("settings_min_disk"))
        self.lbl_out_dir.setText(t("output_folder_label"))
        self.btn_browse.setText(t("browse_folder_btn"))
        self.btn_save.setText(t("settings_save_btn"))
        self.btn_close.setText(t("settings_close_btn"))
