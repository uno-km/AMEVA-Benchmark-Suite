from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QRadioButton, QPushButton, QComboBox, QGroupBox, QDoubleSpinBox, QSpinBox)
from PySide6.QtCore import Qt

class WizardUI(QWidget):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.presets = {
            "Galaxy A35": {"cpu": 4.0, "ram": 2560},
            "Galaxy S24 (NPU)": {"cpu": 8.0, "ram": 6144},
            "사용자 정의": {"cpu": 2.0, "ram": 4096}
        }
        self._setup()

    def _setup(self):
        l = QVBoxLayout(self)
        title = QLabel("Edge Matrix Architect v4 [Singularity]")
        title.setStyleSheet("font-size: 26px; font-weight: 900; color: #00ffcc;")
        l.addWidget(title)

        eg = QGroupBox("1. 추론 엔진 및 마운트")
        el = QVBoxLayout()
        self.r_ollama = QRadioButton(" Ollama (표준)")
        self.r_ollama.setChecked(True)
        self.r_llama = QRadioButton(" llama.cpp (GGUF 전용 / ./models 폴더 자동 마운트)")
        el.addWidget(self.r_ollama)
        el.addWidget(self.r_llama)
        eg.setLayout(el)
        l.addWidget(eg)

        hg = QGroupBox("2. 엣지 디바이스 맵핑 및 자원 제한")
        hl = QVBoxLayout()
        self.hw_combo = QComboBox()
        self.hw_combo.addItems(self.presets.keys())
        self.hw_combo.currentIndexChanged.connect(self._on_preset_change)
        hl.addWidget(self.hw_combo)
        
        ft_layout = QHBoxLayout()
        self.cpu_spin = QDoubleSpinBox(); self.cpu_spin.setRange(0.5, 16.0); self.cpu_spin.setSingleStep(0.5)
        self.ram_spin = QSpinBox(); self.ram_spin.setRange(512, 65536); self.ram_spin.setSingleStep(256)
        
        # [기능 4] GPU/NPU Offload 스핀박스
        self.gpu_spin = QSpinBox(); self.gpu_spin.setRange(0, 99); self.gpu_spin.setSingleStep(1)
        
        ft_layout.addWidget(QLabel("제한 코어:")); ft_layout.addWidget(self.cpu_spin)
        ft_layout.addWidget(QLabel("제한 RAM(MB):")); ft_layout.addWidget(self.ram_spin)
        ft_layout.addWidget(QLabel("GPU Offload:")); ft_layout.addWidget(self.gpu_spin)
        hl.addLayout(ft_layout)
        hg.setLayout(hl)
        l.addWidget(hg)

        self.boot_btn = QPushButton(" 하드코어 매트릭스 강제 부팅")
        self.boot_btn.clicked.connect(self._boot)
        l.addWidget(self.boot_btn)
        self._on_preset_change()

    def _on_preset_change(self):
        data = self.presets[self.hw_combo.currentText()]
        self.cpu_spin.setValue(data["cpu"]); self.ram_spin.setValue(data["ram"])

    def _boot(self):
        config = {
            "engine": "ollama" if self.r_ollama.isChecked() else "llama.cpp",
            "cpu_cores": self.cpu_spin.value(), "ram_mb": self.ram_spin.value(),
            "gpu_layers": self.gpu_spin.value()
        }
        self.ctrl.execute_boot(config)
