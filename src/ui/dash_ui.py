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

        # 텔레메트리 데이터 버퍼 (start-of-session부터 누적)
        self.cpu_data  = []
        self.ram_data  = []
        self.gpu_data  = []
        self.tok_data  = []
        self._tok_cum  = 0                         # 누적 토큰 카운터

        # 로그 스트리밍 모드
        self.is_streaming_enabled = False
        self._stream_buttons = []

        self._setup()

        # 오버레이 (DashUI 위에 float)
        self._overlay = LogOverlay(self)

        # Toast notification
        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.timeout.connect(self._hide_toast)

        self.toast_label = QLabel("", self)
        self.toast_label.setObjectName("ToastLabel")
        self.toast_label.setStyleSheet(
            "background-color: rgba(15, 23, 42, 0.96);"
            " color: #f8fafc;"
            " border: 1px solid #60a5fa;"
            " border-radius: 12px;"
            " padding: 12px;"
            " font-size: 12px;"
            " font-weight: 600;"
        )
        self.toast_label.setWordWrap(True)
        self.toast_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.toast_label.setFixedWidth(340)
        self.toast_label.hide()

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

        self.lbl_ram_usage = QLabel("RAM Usage: 0%")
        self.lbl_ram_usage.setStyleSheet("color: #94a3b8; font-size: 11px; margin-left: 12px;")
        hl.addWidget(self.lbl_ram_usage)
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
        self.cpu_plot.showGrid(x=True, y=True, alpha=0.5)
        self.cpu_plot.getAxis('left').setTicks([[(i, str(i)) for i in range(0, 101, 5)]])
        self.cpu_curve = self.cpu_plot.plot(pen=pg.mkPen('#3b82f6', width=2))
        row.addWidget(self.cpu_plot)

        # RAM
        self.ram_plot = pg.PlotWidget(title="RAM Usage (%)")
        self.ram_plot.setYRange(0, 100)
        self.ram_plot.showGrid(x=True, y=True, alpha=0.5)
        self.ram_plot.getAxis('left').setTicks([[(i, str(i)) for i in range(0, 101, 5)]])
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

        stream_btn = QPushButton("자유")
        stream_btn.setCheckable(True)
        stream_btn.setChecked(self.is_streaming_enabled)
        stream_btn.setFixedSize(70, 22)
        stream_btn.setStyleSheet(
            "font-size: 10px; padding: 0; background-color: #475569; border: none;"
            " color: #f8fafc; border-radius: 3px;"
        )
        stream_btn.clicked.connect(self._toggle_streaming)
        self._stream_buttons.append(stream_btn)
        hl.addWidget(stream_btn)

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
        self.cpu_data  = []
        self.ram_data  = []
        self.gpu_data  = []
        self.tok_data  = []
        self._tok_cum  = 0
        self.lbl_engine_info.setText("MATRIX STATUS: INITIALIZING...")
        self.lbl_ram_usage.setText("RAM Usage: 0%")
        # 오버레이가 열려 있으면 닫기
        self._overlay.close_overlay()

    def show_toast(self, message: str, duration_ms: int = 3200):
        self.toast_timer.stop()
        self.toast_label.setText(message)
        self.toast_label.adjustSize()
        self._position_toast()
        self.toast_label.show()
        self.toast_timer.start(duration_ms)

    def _hide_toast(self):
        self.toast_label.hide()

    def _position_toast(self):
        margin = 16
        w = self.toast_label.width()
        h = self.toast_label.height()
        self.toast_label.setGeometry(
            self.width() - w - margin,
            self.height() - h - margin,
            w,
            h
        )

    def focus_log_tab(self):
        """커널 텔레메트리 탭을 활성화합니다 (인덱스 1)."""
        self.tabs.setCurrentIndex(1)

    def update_engine_status(self, text: str):
        self.lbl_engine_info.setText(f"MATRIX STATUS: {text}")

    def _toggle_streaming(self):
        self.is_streaming_enabled = not self.is_streaming_enabled
        for btn in self._stream_buttons:
            btn.setChecked(self.is_streaming_enabled)
            if self.is_streaming_enabled:
                btn.setText("스트리밍")
                btn.setStyleSheet(
                    "font-size: 10px; padding: 0; background-color: #2563eb; border: none;"
                    " color: #f8fafc; border-radius: 3px;"
                )
            else:
                btn.setText("자유")
                btn.setStyleSheet(
                    "font-size: 10px; padding: 0; background-color: #475569; border: none;"
                    " color: #f8fafc; border-radius: 3px;"
                )

    def _get_container_stats(self):
        try:
            container = getattr(self.ctrl.engine, 'container', None)
            if container is not None and getattr(container, 'status', None) == 'running':
                return container.stats(stream=False)
        except Exception:
            pass
        return None

    def _parse_container_stats(self, stats):
        cpu_pct = 0.0
        mem_pct = 0.0
        used_mb = 0.0
        limit_mb = 0.0
        try:
            mem = stats.get('memory_stats', {})
            usage = mem.get('usage', 0)
            limit = mem.get('limit', 0)
            if limit > 0:
                mem_pct = usage / limit * 100
            used_mb = usage / 1024 / 1024
            limit_mb = limit / 1024 / 1024

            cpu_stats = stats.get('cpu_stats', {})
            precpu = stats.get('precpu_stats', {})
            cpu_delta = cpu_stats.get('cpu_usage', {}).get('total_usage', 0) - precpu.get('cpu_usage', {}).get('total_usage', 0)
            system_delta = cpu_stats.get('system_cpu_usage', 0) - precpu.get('system_cpu_usage', 0)
            online_cpus = cpu_stats.get('online_cpus') or len(cpu_stats.get('cpu_usage', {}).get('percpu_usage', []) or [1])
            if system_delta > 0 and cpu_delta > 0:
                cpu_pct = (cpu_delta / system_delta) * online_cpus * 100.0
        except Exception:
            pass
        return cpu_pct, mem_pct, used_mb, limit_mb

    def update_token_count(self, delta: int):
        """실행 엔진으로부터 토큰 증분을 수신합니다."""
        self._tok_cum += delta
        self.tok_data.append(self._tok_cum)
        self.tok_curve.setData(self.tok_data)

    def log_bench(self, text: str):
        self.console.append(text)
        if self.is_streaming_enabled:
            self.console.verticalScrollBar().setValue(
                self.console.verticalScrollBar().maximum()
            )

    def log_sys(self, text: str):
        self.sys_console.append(text)
        if self.is_streaming_enabled:
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
        """QTimer 100ms 마다 CPU/RAM을 측정합니다."""
        cpu = psutil.cpu_percent(interval=None)
        ram_percent = 0.0
        ram_label_text = "RAM Usage: 0%"

        stats = self._get_container_stats()
        if stats is not None:
            cpu_pct, mem_pct, used_mb, limit_mb = self._parse_container_stats(stats)
            if cpu_pct > 0:
                cpu = cpu_pct
            ram_percent = mem_pct
            ram_label_text = f"RAM Usage: {ram_percent:.1f}%"
            if limit_mb > 0:
                ram_label_text += f" ({used_mb:.1f}/{limit_mb:.0f}MB)"
        else:
            mem = psutil.virtual_memory()
            ram_percent = mem.percent
            used_mb = mem.used / 1024 / 1024
            total_mb = mem.total / 1024 / 1024
            ram_label_text = f"RAM Usage: {ram_percent:.1f}% ({used_mb:.0f}/{total_mb:.0f}MB)"

        self.lbl_ram_usage.setText(ram_label_text)

        self.cpu_data.append(cpu)
        self.ram_data.append(ram_percent)

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
                self.gpu_data.append(gpu_pct)
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
        if self.toast_label.isVisible():
            self._position_toast()
        super().resizeEvent(event)