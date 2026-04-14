from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QRadioButton, QPushButton, QComboBox, QGroupBox, 
                               QDoubleSpinBox, QSpinBox, QMessageBox) # ✅ QMessageBox 추가
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
        
        # ✅ 두 개로 쪼개져 있던 연결을 하나로 통합!
        self.boot_btn.clicked.connect(self._on_boot_clicked) 
        
        l.addWidget(self.boot_btn)
        self._on_preset_change()

    def _on_preset_change(self):
        data = self.presets[self.hw_combo.currentText()]
        self.cpu_spin.setValue(data["cpu"]); self.ram_spin.setValue(data["ram"])

    # ================= ✅ 대망의 부팅 통합 시퀀스 =================
    def _on_boot_clicked(self):
        # 1. UI에서 설정값(Config) 파싱
        config = {
            "engine": "OLM" if self.r_ollama.isChecked() else "ENG",
            "cpu_cores": self.cpu_spin.value(), "ram_mb": self.ram_spin.value(),
            "gpu_layers": self.gpu_spin.value()
        }
        
        # 2. 엔진의 로거를 DashUI의 시스템 로그 탭에 연결!
        # (main.py의 self.dash 이름에 정확히 맞췄습니다)
        self.ctrl.engine.set_logger(self.ctrl.dash.log_sys)
        
        # 3. 화면을 대시보드(Index 1)로 즉시 전환!
        # (main.py의 self.stack 이름에 정확히 맞췄습니다)
        self.ctrl.stack.setCurrentIndex(1)
        
        # 4. 화면이 넘어가자마자 시스템 콘솔에 첫 메시지 투척
        self.ctrl.dash.log_sys("🚀 [SYSTEM] 위저드 모드에서 매트릭스 전이 시퀀스 개시...")
        
        # 5. 메인 컨트롤러(main.py)의 execute_boot 호출!
        # (이 안에서 도커 기동 + CPU/RAM 그래프 연동이 완벽하게 실행됩니다)
        self.ctrl.execute_boot(config)
        
        # 6. 만약 부팅에 실패해서 (main.py에서 에러를 띄운 후) 
        # 엔진이 꺼져있다면 다시 첫 화면으로 강제 복귀!
        if not self.ctrl.engine.container:
            self.ctrl.stack.setCurrentIndex(0)