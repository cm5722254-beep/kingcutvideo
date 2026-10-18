"""
Video Preview Player for King Video Cutter.
Features playback control, seek timeline with visual cut markers, and volume control.
"""

from typing import List
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider, QStyle, QSizePolicy
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from core.ffmpeg_utils import format_duration
from core.i18n import t

class MarkedSlider(QSlider):
    """
    Slider that visually draws vertical cut point markers across the timeline.
    """
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.cut_marker_percentages: List[float] = []

    def set_cut_markers(self, marker_seconds: List[float], total_seconds: float):
        if total_seconds > 0:
            self.cut_marker_percentages = [
                min(1.0, max(0.0, s / total_seconds)) for s in marker_seconds
            ]
        else:
            self.cut_marker_percentages.clear()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.cut_marker_percentages:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        # Gold/yellow marker lines
        pen = QPen(QColor("#f59e0b"), 2)
        painter.setPen(pen)

        w = self.width()
        h = self.height()
        margin = 10
        track_w = w - (margin * 2)

        for pct in self.cut_marker_percentages:
            x = int(margin + (pct * track_w))
            painter.drawLine(x, 4, x, h - 4)


class VideoPreviewPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.total_duration_sec = 0.0
        self.current_pos_sec = 0.0

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Video Output Widget
        self.video_widget = QVideoWidget(self)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_widget.setMinimumHeight(200)
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 8px;")
        self.media_player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget)

        # Controls Container
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(4)

        # Timeline Slider with cut point markers
        self.slider = MarkedSlider(Qt.Horizontal, self)
        self.slider.setRange(0, 1000)
        self.slider.sliderMoved.connect(self._on_seek)
        controls_layout.addWidget(self.slider)

        # Buttons Bar
        bar_layout = QHBoxLayout()
        bar_layout.setSpacing(8)

        self.btn_play = QPushButton("▷", self)
        self.btn_play.setFixedWidth(40)
        self.btn_play.clicked.connect(self.toggle_play)
        bar_layout.addWidget(self.btn_play)

        self.lbl_time = QLabel("00:00:00 / 00:00:00", self)
        self.lbl_time.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: bold;")
        bar_layout.addWidget(self.lbl_time)

        bar_layout.addStretch()

        self.btn_mute = QPushButton("🔊", self)
        self.btn_mute.setFixedWidth(36)
        self.btn_mute.clicked.connect(self._toggle_mute)
        bar_layout.addWidget(self.btn_mute)

        self.vol_slider = QSlider(Qt.Horizontal, self)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(70)
        self.vol_slider.valueChanged.connect(self._on_volume_change)
        bar_layout.addWidget(self.vol_slider)

        controls_layout.addLayout(bar_layout)
        layout.addLayout(controls_layout)

        # Connect signals
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)

    def load_video(self, file_path: str, duration_sec: float = 0.0):
        self.media_player.stop()
        self.total_duration_sec = duration_sec
        url = QUrl.fromLocalFile(file_path)
        self.media_player.setSource(url)
        self.btn_play.setText("▷")
        self._update_time_label(0.0)

    def set_cut_markers(self, marker_seconds: List[float]):
        self.slider.set_cut_markers(marker_seconds, self.total_duration_sec)

    def toggle_play(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play.setText("▷")
        else:
            self.media_player.play()
            self.btn_play.setText("❚❚")

    def stop(self):
        self.media_player.stop()
        self.btn_play.setText("▷")

    def _on_seek(self, position):
        if self.total_duration_sec > 0:
            target_ms = int((position / 1000.0) * (self.total_duration_sec * 1000.0))
            self.media_player.setPosition(target_ms)

    def _on_position_changed(self, position_ms):
        self.current_pos_sec = position_ms / 1000.0
        if not self.slider.isSliderDown() and self.total_duration_sec > 0:
            val = int((self.current_pos_sec / self.total_duration_sec) * 1000.0)
            self.slider.setValue(val)
        self._update_time_label(self.current_pos_sec)

    def _on_duration_changed(self, duration_ms):
        if duration_ms > 0:
            self.total_duration_sec = duration_ms / 1000.0
            self._update_time_label(self.current_pos_sec)

    def _update_time_label(self, current_sec: float):
        curr_str = format_duration(current_sec)
        total_str = format_duration(self.total_duration_sec)
        self.lbl_time.setText(f"{curr_str} / {total_str}")

    def _toggle_mute(self):
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        self.btn_mute.setText("🔇" if not is_muted else "🔊")

    def _on_volume_change(self, val):
        self.audio_output.setVolume(val / 100.0)
        if val == 0:
            self.btn_mute.setText("🔇")
        else:
            self.btn_mute.setText("🔊")
