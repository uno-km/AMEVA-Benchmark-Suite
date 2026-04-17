import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QSlider, QDoubleSpinBox, QSpinBox, QPushButton, 
    QTextEdit, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from models.settings import StressOptions

class ModelTuningDialog(QDialog):
    """[Engineering] 모델 파라미터 미세 튜닝 팝업"""
    
    settings_updated = Signal(StressOptions)

    def __init__(self, current_options: StressOptions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Model Architecture Tuning")
        self.setFixedWidth(450)
        self._options = current_options
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        hdr = QLabel("PARAMETER FINE-TUNING")
        hdr.setStyleSheet("font-weight: bold; color: #3b82f6; font-size: 14px;")
        layout.addWidget(hdr)

        # ── Parameter Grid ──────────────────────────────────────────────
        grid_frame = QFrame()
        grid_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(15, 15, 15, 15)
        grid.setSpacing(10)

        # 1. Temperature
        grid.addWidget(QLabel("Temperature:"), 0, 0)
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(self._options.temperature)
        grid.addWidget(self.temp_spin, 0, 1)

        # 2. Top-P
        grid.addWidget(QLabel("Top-P:"), 1, 0)
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(self._options.top_p)
        grid.addWidget(self.top_p_spin, 1, 1)

        # 3. Top-K
        grid.addWidget(QLabel("Top-K:"), 2, 0)
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 256)
        self.top_k_spin.setValue(self._options.top_k)
        grid.addWidget(self.top_k_spin, 2, 1)

        # 4. Repeat Penalty
        grid.addWidget(QLabel("Repeat Penalty:"), 3, 0)
        self.penalty_spin = QDoubleSpinBox()
        self.penalty_spin.setRange(1.0, 2.0)
        self.penalty_spin.setSingleStep(0.1)
        self.penalty_spin.setValue(self._options.repeat_penalty)
        grid.addWidget(self.penalty_spin, 3, 1)

        layout.addWidget(grid_frame)

        # ── System Prompt ───────────────────────────────────────────────
        layout.addWidget(QLabel("SYSTEM PROMPT (ChatML Mode)"))
        self.sys_prompt_edit = QTextEdit()
        self.sys_prompt_edit.setPlaceholderText("Enter system instructions here...")
        self.sys_prompt_edit.setPlainText(self._options.system_prompt)
        self.sys_prompt_edit.setFixedHeight(80)
        self.sys_prompt_edit.setStyleSheet(
            "background-color: #020617; color: #cbd5e1; border: 1px solid #334155; font-family: 'Consolas';"
        )
        layout.addWidget(self.sys_prompt_edit)

        # ── Buttons ─────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply Settings")
        apply_btn.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold; padding: 5px 15px;")
        apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(apply_btn)

        layout.addLayout(btn_layout)

    def _on_apply(self):
        new_opts = StressOptions(
            threads=self._options.threads,
            n_ctx=self._options.n_ctx,
            iterations=self._options.iterations,
            temperature=self.temp_spin.value(),
            top_p=self.top_p_spin.value(),
            top_k=self.top_k_spin.value(),
            repeat_penalty=self.penalty_spin.value(),
            system_prompt=self.sys_prompt_edit.toPlainText()
        )
        self.settings_updated.emit(new_opts)
        self.accept()
