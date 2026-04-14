import psutil
import pyqtgraph as pg
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QGroupBox, QLineEdit, QProgressBar,
    QTabWidget, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from models.hardware import HardwareService
from ui.log_overlay import LogOverlay


def _ts() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"


class DashUI(QWidget):
    run_benchmark_signal = Signal()
    chaos_monkey_signal = Signal()
    shutdown_signal = Signal()

    # 히스토리 길이 (0.1s × 300 = 30초 분량)
    _HISTORY = 300

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.specs = HardwareService.detect_capabilities()

        # 텔레메트리 데이터 버퍼
        self.cpu_data  = [0.0] * self._HISTORY
        self.ram_data  = [0.0] * self._HISTORY
        self.gpu_data  = [0.0] * self._HISTORY
        self.tok_data  = [0]   * self._HISTORY   # 누적 토큰
        self._tok_cum  = 0                         # 누적 토큰 카운터

        self._setup()

        # 오버레이 (DashUI 위에 float)
        self._overlay = LogOverlay(self)

        # 0.1s 텔레메트리 타이머
        self._tel_timer = QTimer(self)
        self._tel_timer.setInterval(100)
        self._tel_timer.timeout.connect(self._poll_telemetry)
        self._tel_timer.start()

    # ──────────────────────────────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────────────────────────────

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        root.addWidget(self._build_control_bar())
        root.addLayout(self._build_telemetry_bar())
        root.addLayout(self._build_graphs(), stretch=3)
        root.addWidget(self._build_console_tabs(), stretch=4)
        self.apply_theme_to_graphs(True)

    # ── Control bar ───────────────────────────────────────────────────

    def _build_control_bar(self) -> QFrame:
        card = QFrame()
        card.setObjectName("ControlCard")
        card.setStyleSheet(
            "QFrame#ControlCard { background-color: #1e293b;"
            " border-radius: 8px; border: 1px solid #334155; }"
        )
        cl = QHBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(10)

        self.lbl_engine_info = QLabel("MATRIX STATUS: INITIALIZING...")
        self.lbl_engine_info.setStyleSheet(
            "color: #3b82f6; font-weight: 800; border: none; font-size: 13px;"
        )
        cl.addWidget(self.lbl_engine_info)
        cl.addStretch()

        self.model_combo = QComboBox()
        self.model_combo.addItems(["qwen2.5:0.5b", "llama3.2:1b", "gemma2:2b"])
        cl.addWidget(QLabel("Model:"))
        cl.addWidget(self.model_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "추론 모드 (Standard Inference)",
            "스트레스 마스터 (Hard Stress)",
            "전성비 최적화 (Efficiency Track)"
        ])
        cl.addWidget(QLabel("Protocol:"))
        cl.addWidget(self.mode_combo)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("LLM Judge API Key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setFixedWidth(160)
        cl.addWidget(self.api_key_input)

        self.btn_run = QPushButton("⚡  RUN")
        self.btn_run.setObjectName("RunButton")
        self.btn_run.setFixedWidth(90)
        self.btn_run.clicked.connect(self.run_benchmark_signal.emit)
        cl.addWidget(self.btn_run)

        self.btn_chaos = QPushButton("🔥")
        self.btn_chaos.setFixedWidth(38)
        self.btn_chaos.setToolTip("Chaos Monkey – 급격한 부하 주입")
        self.btn_chaos.setStyleSheet("background-color: #f59e0b; color: #0f172a; border: none;")
        self.btn_chaos.clicked.connect(self.chaos_monkey_signal.emit)
        cl.addWidget(self.btn_chaos)

        self.btn_harness = QPushButton("📋 HARNESS")
        self.btn_harness.setFixedWidth(100)
        self.btn_harness.setToolTip("Benchmark harness 관리창 열기")
        self.btn_harness.clicked.connect(self.ctrl.show_harness_manager)
        cl.addWidget(self.btn_harness)

        self.btn_shutdown = QPushButton("✖")
        self.btn_shutdown.setFixedWidth(38)
        self.btn_shutdown.setToolTip("Shutdown & Return")
        self.btn_shutdown.setStyleSheet("background-color: #ef4444; color: white; border: none;")
        self.btn_shutdown.clicked.connect(self._on_shutdown_clicked)
        cl.addWidget(self.btn_shutdown)

        self.theme_btn = QPushButton("🌓")
        self.theme_btn.setFixedWidth(36)
        self.theme_btn.clicked.connect(self.ctrl.toggle_theme)
        cl.addWidget(self.theme_btn)

        return card

    # ── Telemetry bar ─────────────────────────────────────────────────

    def _build_telemetry_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        health_grp = QGroupBox("SYSTEM HEALTH")
        hl = QVBoxLayout(health_grp)
        hl.setContentsMargins(8, 10, 8, 8)
        hl.setSpacing(4)
        self.lbl_battery = QLabel("Reliability: 100%")
        self.lbl_battery.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.bar_battery = QProgressBar()
        self.bar_battery.setValue(100)
        hl.addWidget(self.lbl_battery)
        hl.addWidget(self.bar_battery)
        row.addWidget(health_grp)

        self.lbl_blackout = QLabel("")
        self.lbl_blackout.setStyleSheet("color: #ef4444; font-weight: 900; font-size: 14px;")
        row.addWidget(self.lbl_blackout)
        row.addStretch()

        return row

    # ── Graph section ─────────────────────────────────────────────────

    def _build_graphs(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        # CPU
        self.cpu_plot = pg.PlotWidget(title="CPU Load (%)")
        self.cpu_plot.setYRange(0, 100)
        self.cpu_curve = self.cpu_plot.plot(pen=pg.mkPen('#3b82f6', width=2))
        row.addWidget(self.cpu_plot)

        # RAM
        self.ram_plot = pg.PlotWidget(title="RAM (MB)")
        self.ram_curve = self.ram_plot.plot(pen=pg.mkPen('#10b981', width=2))
        row.addWidget(self.ram_plot)

        # GPU (조건부)
        if self.specs.has_nvidia:
            self.gpu_plot = pg.PlotWidget(title="GPU (%)")
            self.gpu_plot.setYRange(0, 100)
            self.gpu_curve = self.gpu_plot.plot(pen=pg.mkPen('#f59e0b', width=2))
            row.addWidget(self.gpu_plot)

        # Token Usage
        self.tok_plot = pg.PlotWidget(title="Token Usage (cumulative)")
        self.tok_curve = self.tok_plot.plot(pen=pg.mkPen('#a855f7', width=2))
        row.addWidget(self.tok_plot)

        return row

    # ── Console tabs ──────────────────────────────────────────────────

    def _build_console_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()

        # Analytics tab
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        analytics_widget = self._wrap_console(
            self.console, "📊  ANALYTICS & INSIGHTS"
        )
        self.tabs.addTab(analytics_widget, "📊  ANALYTICS")

        # Kernel telemetry tab
        self.sys_console = QTextEdit()
        self.sys_console.setReadOnly(True)
        kernel_widget = self._wrap_console(
            self.sys_console, "⚙️  KERNEL TELEMETRY"
        )
        self.tabs.addTab(kernel_widget, "⚙️  KERNEL TELEMETRY")

        return self.tabs

    def _wrap_console(self, console: QTextEdit, title: str) -> QWidget:
        """QTextEdit 를 헤더(확장 버튼 포함) + 본문으로 감쌉니다."""
        wrapper = QWidget()
        vl = QVBoxLayout(wrapper)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # 미니 헤더
        hdr = QWidget()
        hdr.setFixedHeight(30)
        hdr.setStyleSheet(
            "background-color: #1e293b; border-bottom: 1px solid #334155;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(10, 0, 8, 0)

        lbl = QLabel(title)
        lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 700; border: none;")
        hl.addWidget(lbl)
        hl.addStretch()

        expand_btn = QPushButton("⤢  확장")
        expand_btn.setFixedSize(70, 22)
        expand_btn.setStyleSheet(
            "font-size: 10px; padding: 0; background-color: #334155; border: none;"
            " color: #f8fafc; border-radius: 3px;"
        )
        expand_btn.clicked.connect(lambda _, c=console, t=title: self._overlay.show_for(c, t))
        hl.addWidget(expand_btn)

        vl.addWidget(hdr)
        vl.addWidget(console)
        return wrapper

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def clear_logs(self):
        """화면 전환 전 로그 초기화 + 텔레메트리 데이터 리셋."""
        self.console.clear()
        self.sys_console.clear()
        # 텔레메트리 버퍼 리셋
        self.cpu_data  = [0.0] * self._HISTORY
        self.ram_data  = [0.0] * self._HISTORY
        self.gpu_data  = [0.0] * self._HISTORY
        self.tok_data  = [0]   * self._HISTORY
        self._tok_cum  = 0
        self.lbl_engine_info.setText("MATRIX STATUS: INITIALIZING...")
        # 오버레이가 열려 있으면 닫기
        self._overlay.close_overlay()

    def focus_log_tab(self):
        """커널 텔레메트리 탭을 활성화합니다 (인덱스 1)."""
        self.tabs.setCurrentIndex(1)

    def update_engine_status(self, text: str):
        self.lbl_engine_info.setText(f"MATRIX STATUS: {text}")

    def update_token_count(self, delta: int):
        """실행 엔진으로부터 토큰 증분을 수신합니다."""
        self._tok_cum += delta
        self.tok_data = self.tok_data[1:] + [self._tok_cum]
        self.tok_curve.setData(self.tok_data)

    def log_bench(self, text: str):
        self.console.append(text)
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum()
        )

    def log_sys(self, text: str):
        self.sys_console.append(text)
        self.sys_console.verticalScrollBar().setValue(
            self.sys_console.verticalScrollBar().maximum()
        )

    def apply_theme_to_graphs(self, is_dark: bool):
        bg = '#020617' if is_dark else '#ffffff'
        fg = '#94a3b8' if is_dark else '#475569'
        alpha = 0.08 if is_dark else 0.15

        plots = [self.cpu_plot, self.ram_plot, self.tok_plot]
        if self.specs.has_nvidia:
            plots.append(self.gpu_plot)

        for p in plots:
            p.setBackground(bg)
            p.showGrid(x=True, y=True, alpha=alpha)
            p.getAxis('left').setPen(fg)
            p.getAxis('left').setTextPen(fg)
            p.getAxis('bottom').setPen(fg)
            p.getAxis('bottom').setTextPen(fg)

        console_style = (
            f"background-color: {bg}; color: {'#94a3b8' if is_dark else '#1e293b'};"
            " border: none; border-radius: 0;"
            " font-family: 'JetBrains Mono','Consolas',monospace; font-size: 11px; padding: 8px;"
        )
        self.sys_console.setStyleSheet(console_style)

    def update_telemetry(self, cpu, mem_u, mem_l, bat_pct, gpu=None):
        """외부 호출 버전 (기존 호환성 유지)."""
        self.bar_battery.setValue(int(bat_pct))
        self.lbl_battery.setText(f"Reliability: {bat_pct:.1f}%")

    # ──────────────────────────────────────────────────────────────────
    # 0.1s Telemetry Polling
    # ──────────────────────────────────────────────────────────────────

    def _poll_telemetry(self):
        """QTimer 100ms 마다 psutil로 CPU/RAM을 실측합니다."""
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        ram_mb = mem.used / 1024 / 1024

        self.cpu_data = self.cpu_data[1:] + [cpu]
        self.ram_data = self.ram_data[1:] + [ram_mb]

        self.cpu_curve.setData(self.cpu_data)
        self.ram_curve.setData(self.ram_data)

        if self.specs.has_nvidia:
            try:
                import subprocess
                proc = subprocess.Popen(
                    ["nvidia-smi", "--query-gpu=utilization.gpu",
                     "--format=csv,noheader,nounits"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
                out, _ = proc.communicate(timeout=0.05)
                gpu_pct = float(out.strip().split('\n')[0])
                self.gpu_data = self.gpu_data[1:] + [gpu_pct]
                self.gpu_curve.setData(self.gpu_data)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────
    # Slots
    # ──────────────────────────────────────────────────────────────────

    def _on_shutdown_clicked(self):
        self.shutdown_signal.emit()

    def resizeEvent(self, event):
        if self._overlay.isVisible():
            self._overlay.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)