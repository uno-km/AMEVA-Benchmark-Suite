from ui.qt_bridge import *
from core.constants import DEFAULT_INFERENCE_MODEL
from models.hardware import HardwareService
from models.settings import BootstrapConfig, StressOptions, BenchmarkSession


class WizardUI(QWidget):
    """[V5.5] 부트스트랩 설정 마법사. 날렵한 레이아웃 + 수평 엔진 선택."""

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.specs = HardwareService.detect_capabilities()

        # 사전 정의된 기기 에뮬레이션 프리셋
        self.presets = {
            "Galaxy A35 (Low-End)":  {"cpu": 2.0, "ram": 2048},
            "Galaxy S24 (Mid-Range)": {"cpu": 4.0, "ram": 4096},
            "Edge Server (High-End)": {"cpu": 8.0, "ram": 8192},
            "Custom (Host-Defined)":  {"cpu": self.specs.cpu_count / 2,
                                       "ram": self.specs.ram_total_gb * 512},
        }

        # 엔진 옵션 레지스트리 – 확장 시 여기에 추가
        self._engine_registry = [
            ("🔵  OLLAMA",    "OLM", "Managed Container – 자동 프로비저닝 (권장)"),
            ("⚡  LLAMA.CPP", "ENG", "GGUF Native Server – 최대 성능 / 최저 지연"),
        ]

        self._engine_btns: dict[str, QPushButton] = {}
        self._engine_btn_group = QButtonGroup(self)
        self._engine_btn_group.setExclusive(True)

        self._setup()

    # ──────────────────────────────────────────────────────────────────
    # Build UI
    # ──────────────────────────────────────────────────────────────────

    def _setup(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(28, 24, 28, 20)

        # ── 헤더 ──────────────────────────────────────────────────────
        h_row = QHBoxLayout()
        header = QLabel("AMEVA EDGE MATRIX")
        header.setObjectName("HeaderLabel")
        h_row.addWidget(header)
        h_row.addStretch()

        self.btn_gallery = QPushButton("📊 모델 현황")
        self.btn_gallery.setFixedWidth(100)
        self.btn_gallery.setStyleSheet("font-weight: 600; font-size: 11px;")
        self.btn_gallery.clicked.connect(self._open_gallery)
        h_row.addWidget(self.btn_gallery)

        self.theme_btn = QPushButton("🌓")
        self.theme_btn.setFixedSize(36, 30)
        self.theme_btn.clicked.connect(self.ctrl.toggle_theme)
        h_row.addWidget(self.theme_btn)
        root.addLayout(h_row)

        sub = QLabel("AI Runtime Configuration  ·  Hardware Slicing  ·  Stress Protocol")
        sub.setObjectName("SubHeaderLabel")
        root.addWidget(sub)

        # ── 섹션 1: 엔진 & 가상화 ─────────────────────────────────────
        root.addWidget(self._build_engine_section())

        # ── 섹션 2: 하드웨어 슬라이싱 ────────────────────────────────
        root.addWidget(self._build_hardware_section())

        # ── 섹션 3: 스트레스 파라미터 ────────────────────────────────
        root.addWidget(self._build_stress_section())

        root.addStretch()

        # ── 부팅 버튼 ─────────────────────────────────────────────────
        self.boot_btn = QPushButton("🚀  커널 부팅 시퀀스 시작")
        self.boot_btn.setObjectName("BootButton")
        self.boot_btn.setFixedHeight(48)
        self.boot_btn.clicked.connect(self._on_boot_clicked)
        root.addWidget(self.boot_btn)

        # 초기 프리셋 적용
        self._on_preset_change()

    def _open_gallery(self):
        """모델 갤러리를 팝업하여 다운로드 상태를 확인합니다."""
        from ui.model_gallery import ModelGalleryDialog
        dlg = ModelGalleryDialog(current_model="", parent=self)
        dlg.exec()

    def _build_engine_section(self) -> QGroupBox:
        """섹션 1: 엔진 선택 (수평 토글 버튼 + 확장 가능 구조)."""
        group = QGroupBox("1.  KERNEL & VIRTUALIZATION")
        layout = QHBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 14, 10, 10)

        for label, key, tooltip in self._engine_registry:
            self._add_engine_button(label, key, tooltip, layout)

        layout.addStretch()
        return group

    def _add_engine_button(self, label: str, key: str, tooltip: str,
                           layout: QHBoxLayout):
        """엔진 버튼을 동적으로 등록합니다. 향후 엔진 추가 시 이 메서드를 호출."""
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setToolTip(tooltip)
        btn.setFixedHeight(34)
        btn.setMinimumWidth(160)
        self._engine_btn_group.addButton(btn)
        self._engine_btns[key] = btn
        layout.addWidget(btn)
        # 첫 번째 버튼을 기본 선택
        if len(self._engine_btns) == 1:
            btn.setChecked(True)

    def _build_hardware_section(self) -> QGroupBox:
        """섹션 2: 하드웨어 슬라이싱 (프리셋 + 세부 설정)."""
        group = QGroupBox("2.  HARDWARE SLICING  —  Isolation Policy")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 14, 10, 10)

        # 프리셋 콤보박스 (잘림 방지)
        preset_row = QHBoxLayout()
        preset_lbl = QLabel("Device Emulation Preset:")
        preset_lbl.setFixedWidth(180)
        preset_row.addWidget(preset_lbl)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.presets.keys())
        self.preset_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.preset_combo.setMinimumContentsLength(22)
        self.preset_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_change)
        preset_row.addWidget(self.preset_combo)
        layout.addLayout(preset_row)

        # 세부 수치 행
        detail_row = QHBoxLayout()
        detail_row.setSpacing(16)

        # CPU
        cpu_col = QVBoxLayout()
        cpu_col.setSpacing(3)
        cpu_col.addWidget(QLabel("CPU Cores:"))
        self.cpu_spin = QDoubleSpinBox()
        self.cpu_spin.setRange(0.5, self.specs.cpu_count)
        self.cpu_spin.setSingleStep(0.5)
        self.cpu_spin.setDecimals(1)
        self.cpu_spin.setValue(2.0)
        cpu_col.addWidget(self.cpu_spin)
        detail_row.addLayout(cpu_col)

        # RAM
        ram_col = QVBoxLayout()
        ram_col.setSpacing(3)
        ram_col.addWidget(QLabel("RAM (MB):"))
        self.ram_spin = QSpinBox()
        self.ram_spin.setRange(512, int(self.specs.ram_total_gb * 1024))
        self.ram_spin.setSingleStep(512)
        self.ram_spin.setValue(4096)
        ram_col.addWidget(self.ram_spin)
        detail_row.addLayout(ram_col)

        # GPU (감지 시에만 활성)
        gpu_col = QVBoxLayout()
        gpu_col.setSpacing(3)
        self.gpu_label = QLabel("GPU Layers:")
        gpu_col.addWidget(self.gpu_label)
        self.gpu_spin = QSpinBox()
        self.gpu_spin.setRange(0, 99)
        self.gpu_spin.setValue(0)
        if not self.specs.has_nvidia:
            self.gpu_spin.setEnabled(False)
            self.gpu_spin.setToolTip("NVIDIA GPU not detected on this host.")
            self.gpu_label.setStyleSheet("color: #475569;")
        gpu_col.addWidget(self.gpu_spin)
        detail_row.addLayout(gpu_col)

        detail_row.addStretch()
        layout.addLayout(detail_row)
        return group

    def _build_stress_section(self) -> QGroupBox:
        """섹션 3: 스트레스 파라미터."""
        group = QGroupBox("3.  STRESS TEST PROTOCOL  —  Parameter Tuning")
        layout = QHBoxLayout(group)
        layout.setSpacing(20)
        layout.setContentsMargins(10, 14, 10, 10)

        # 스레드
        t_col = QVBoxLayout()
        t_col.setSpacing(3)
        t_lbl = QLabel("Threads:")
        t_lbl.setToolTip("병렬 연산 스레드 수. 물리 코어 수와 일치 시 가장 효율적입니다.")
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, self.specs.cpu_count)
        self.thread_spin.setValue(4)
        t_col.addWidget(t_lbl)
        t_col.addWidget(self.thread_spin)
        layout.addLayout(t_col)

        # 컨텍스트 윈도우
        c_col = QVBoxLayout()
        c_col.setSpacing(3)
        c_lbl = QLabel("Context Window (N_CTX):")
        c_lbl.setToolTip("AI 단기 기억력 크기. 값이 커질수록 RAM 사용량이 급증합니다.")
        self.ctx_spin = QSpinBox()
        self.ctx_spin.setRange(512, 32768)
        self.ctx_spin.setSingleStep(512)
        self.ctx_spin.setValue(2048)
        c_col.addWidget(c_lbl)
        c_col.addWidget(self.ctx_spin)
        layout.addLayout(c_col)

        # 반복 횟수
        i_col = QVBoxLayout()
        i_col.setSpacing(3)
        self.iter_spin = QSpinBox()
        self.iter_spin.setRange(1, 10)
        self.iter_spin.setValue(3)
        i_col.addWidget(QLabel("Iterations:"))
        i_col.addWidget(self.iter_spin)
        layout.addLayout(i_col)

        layout.addStretch()
        return group

    # ──────────────────────────────────────────────────────────────────
    # Slots
    # ──────────────────────────────────────────────────────────────────

    def _on_preset_change(self):
        name = self.preset_combo.currentText()
        if name in self.presets:
            d = self.presets[name]
            self.cpu_spin.setValue(d["cpu"])
            self.ram_spin.setValue(d["ram"])

    def _on_boot_clicked(self):
        """설정을 캡처하고 즉시 부팅 시퀀스를 발동합니다."""
        selected_engine = next(
            (k for k, b in self._engine_btns.items() if b.isChecked()), "OLM"
        )
        boot_config = BootstrapConfig(
            engine=selected_engine,
            cpu_cores=self.cpu_spin.value(),
            ram_mb=self.ram_spin.value(),
            gpu_layers=self.gpu_spin.value() if self.specs.has_nvidia else 0,
            model_name=DEFAULT_INFERENCE_MODEL
        )
        stress_config = StressOptions(
            threads=self.thread_spin.value(),
            n_ctx=self.ctx_spin.value(),
            iterations=self.iter_spin.value()
        )
        session = BenchmarkSession(boot_config=boot_config, stress_config=stress_config)
        self.ctrl.execute_boot_sequence(session)