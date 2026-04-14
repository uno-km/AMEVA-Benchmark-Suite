from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QRadioButton, QPushButton, QComboBox, QGroupBox, 
                               QDoubleSpinBox, QSpinBox, QMessageBox, QFrame)
from PySide6.QtCore import Qt
from models.hardware import HardwareService
from models.settings import BootstrapConfig, StressOptions, BenchmarkSession

class WizardUI(QWidget):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        
        # Hardware Detection
        self.specs = HardwareService.detect_capabilities()
        
        self.presets = {
            "Galaxy A35 (Low-End)": {"cpu": 2.0, "ram": 2048},
            "Galaxy S24 (Mid-Range)": {"cpu": 4.0, "ram": 4096},
            "Edge Server (High-End)": {"cpu": 8.0, "ram": 8192},
            "Custom Path": {"cpu": self.specs.cpu_count / 2, "ram": self.specs.ram_total_gb * 512}
        }
        self._setup()

    def _setup(self):
        l = QVBoxLayout(self)
        l.setSpacing(20)
        l.setContentsMargins(40, 40, 40, 40)

        # Header
        header = QLabel("EDGE MATRIX v5.5 [CORE ARCHITECT]")
        header.setObjectName("HeaderLabel")
        header.setStyleSheet("font-size: 32px; font-weight: 900; color: #00ffcc; letter-spacing: 2px;")
        l.addWidget(header)

        # 1. Engine & Environment
        engine_group = QGroupBox("1. KERNEL & VIRTUALIZATION")
        eg_layout = QVBoxLayout()
        self.r_ollama = QRadioButton(" OLLAMA RUNTIME (AUTO-PROVISION)")
        self.r_ollama.setChecked(True)
        self.r_llama = QRadioButton(" LLAMA.CPP SERVER (GGUF NATIVE)")
        eg_layout.addWidget(self.r_ollama)
        eg_layout.addWidget(self.r_llama)
        engine_group.setLayout(eg_layout)
        l.addWidget(engine_group)

        # 2. Resource Constraints
        resource_group = QGroupBox("2. HARDWARE SLICING (EDGEMATRIX)")
        rg_layout = QVBoxLayout()
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.presets.keys())
        self.preset_combo.currentIndexChanged.connect(self._on_preset_change)
        rg_layout.addWidget(QLabel("DEVICE EMULATION PRESET:"))
        rg_layout.addWidget(self.preset_combo)

        ctrl_layout = QHBoxLayout()
        self.cpu_spin = QDoubleSpinBox()
        self.cpu_spin.setRange(0.5, self.specs.cpu_count)
        self.cpu_spin.setValue(2.0)
        
        self.ram_spin = QSpinBox()
        self.ram_spin.setRange(512, int(self.specs.ram_total_gb * 1024))
        self.ram_spin.setValue(4096)

        ctrl_layout.addWidget(QLabel("CPU CORES:"))
        ctrl_layout.addWidget(QLabel("CPU 코어:"))
        ctrl_layout.addWidget(self.cpu_spin)
        ctrl_layout.addWidget(QLabel("RAM (MB):"))
        ctrl_layout.addWidget(self.ram_spin)
        
        # GPU 확인
        self.gpu_spin = QSpinBox()
        self.gpu_spin.setRange(0, 99)
        self.gpu_label = QLabel("GPU 레이어:")
        
        if not self.specs.has_nvidia:
            self.gpu_spin.setEnabled(False)
            self.gpu_spin.setToolTip("NVIDIA GPU가 감지되지 않았습니다.")
            self.gpu_label.setStyleSheet("color: #444;")
        
        ctrl_layout.addWidget(self.gpu_label)
        ctrl_layout.addWidget(self.gpu_spin)
        
        rg_layout.addLayout(ctrl_layout)
        resource_group.setLayout(rg_layout)
        l.addWidget(resource_group)

        # 3. 스트레스 테스트 고급 옵션
        stress_group = QGroupBox("3. 스트레스 테스트 매개변수 (V5.5 마스터)")
        sg_layout = QHBoxLayout()
        
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, self.specs.cpu_count)
        self.thread_spin.setValue(4)
        
        self.ctx_spin = QSpinBox()
        self.ctx_spin.setRange(512, 32768)
        self.ctx_spin.setSingleStep(512)
        self.ctx_spin.setValue(2048)
        
        self.iter_spin = QSpinBox()
        self.iter_spin.setRange(1, 10)
        self.iter_spin.setValue(3)

        sg_layout.addWidget(QLabel("스레드:"))
        sg_layout.addWidget(self.thread_spin)
        sg_layout.addWidget(QLabel("컨텍스트 윈도우:"))
        sg_layout.addWidget(self.ctx_spin)
        sg_layout.addWidget(QLabel("반복 횟수:"))
        sg_layout.addWidget(self.iter_spin)
        
        stress_group.setLayout(sg_layout)
        l.addWidget(stress_group)

        l.addStretch()

        # 부팅 버튼
        self.boot_btn = QPushButton(" 커널 부팅 시퀀스 시작")
        self.boot_btn.setObjectName("BootButton")
        self.boot_btn.setFixedHeight(60)
        self.boot_btn.clicked.connect(self._on_boot_clicked)
        l.addWidget(self.boot_btn)

        self._on_preset_change()

    def _on_preset_change(self):
        preset_name = self.preset_combo.currentText()
        if preset_name in self.presets:
            data = self.presets[preset_name]
            self.cpu_spin.setValue(data["cpu"])
            self.ram_spin.setValue(data["ram"])

    def _on_boot_clicked(self):
        """설정값을 캡처하고 부팅 시퀀스를 발동합니다."""
        boot_config = BootstrapConfig(
            engine="OLM" if self.r_ollama.isChecked() else "ENG",
            cpu_cores=self.cpu_spin.value(),
            ram_mb=self.ram_spin.value(),
            gpu_layers=self.gpu_spin.value() if self.specs.has_nvidia else 0
        )
        
        stress_config = StressOptions(
            threads=self.thread_spin.value(),
            n_ctx=self.ctx_spin.value(),
            iterations=self.iter_spin.value()
        )
        
        session = BenchmarkSession(boot_config=boot_config, stress_config=stress_config)
        self.ctrl.execute_boot_sequence(session)