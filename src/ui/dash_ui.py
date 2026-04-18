from ui.qt_bridge import *
import pyqtgraph as pg
import psutil
from datetime import datetime
from core.constants import OLLAMA_BASE_URL, LLAMA_CPP_HOST, DEFAULT_INFERENCE_MODEL, DEFAULT_JUDGE_MODEL
from models.hardware import HardwareService
from ui.log_overlay import LogOverlay
from ui.chat_panel import ChatPanel


def _ts() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"


class DashUI(QWidget):
    run_benchmark_signal = Signal()
    chaos_monkey_signal  = Signal()
    shutdown_signal      = Signal()
    chat_prompt_signal   = Signal(str)   # 채팅 프롬프트 → 컨트롤러

    # 히스토리 길이 (0.1s × 300 = 30초 분량)
    _HISTORY = 300

    def __init__(self, ctrl):
        super().__init__(ctrl)
        self.ctrl  = ctrl
        self.specs = HardwareService.detect_capabilities()

        # 텔레메트리 버퍼
        self.cpu_data  = []
        self.ram_data  = []
        self.gpu_data  = []
        self.tok_data  = []
        self.cpu_x     = []
        self.ram_x     = []
        self.gpu_x     = []
        self.tok_x     = []
        self._tok_cum  = 0
        self._telemetry_index = 0
        self._user_panned = False
        self._suppress_range_change = False

        # 스트리밍 모드
        self.is_streaming_enabled = False
        self._stream_buttons = []

        # 현재 선택 모델명 및 엔진 (콤보박스 대체)
        self._active_model  = ""
        self._active_engine = ""

        self._setup()

        # 오버레이
        self._overlay = LogOverlay(self)

        # Toast
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

        # 0.1s 텔레메트리
        self._tel_timer = QTimer(self)
        self._tel_timer.setInterval(100)
        self._tel_timer.timeout.connect(self._poll_telemetry)
        self._tel_timer.start()

    # ────────────────────────────────────────────────────────────────────────
    # Layout
    # ────────────────────────────────────────────────────────────────────────

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        root.addWidget(self._build_control_bar())
        root.addLayout(self._build_telemetry_bar())

        # ── Side-by-side: 중앙 컨텐츠 + 채팅 사이드바 ─────────────────
        center_and_chat = QHBoxLayout()
        center_and_chat.setSpacing(0)
        center_and_chat.setContentsMargins(0, 0, 0, 0)

        # 중앙 컨텐츠 (그래프 + 콘솔)
        self._content_area = QWidget()
        content_vl = QVBoxLayout(self._content_area)
        content_vl.setContentsMargins(0, 0, 0, 0)
        content_vl.setSpacing(10)
        content_vl.addLayout(self._build_graphs(), stretch=3)
        content_vl.addWidget(self._build_console_tabs(), stretch=4)

        self.chat_panel = ChatPanel()
        self.chat_panel.chat_submitted.connect(self.chat_prompt_signal.emit)

        center_and_chat.addWidget(self._content_area, 1)
        center_and_chat.addWidget(self.chat_panel, 0)

        root.addLayout(center_and_chat, stretch=7)

        self.apply_theme_to_graphs(True)

    # ── Control bar ──────────────────────────────────────────────────────

    def _build_control_bar(self) -> QFrame:
        card = QFrame()
        card.setObjectName("ControlCard")
        card.setStyleSheet(
            "QFrame#ControlCard { background-color: #1e293b;"
            " border-radius: 8px; border: 1px solid #334155; }"
        )
        cl = QHBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(8)

        self.lbl_engine_info = QLabel("MATRIX STATUS: INITIALIZING...")
        self.lbl_engine_info.setStyleSheet(
            "color: #3b82f6; font-weight: 800; border: none; font-size: 13px;"
        )
        cl.addWidget(self.lbl_engine_info)
        cl.addStretch()

        # ── 모델 현황 버튼 (콤보박스 대체) ─────────────────────────────
        self._lbl_active_model = QLabel("모델: 미선택")
        self._lbl_active_model.setStyleSheet(
            "color: #94a3b8; font-size: 11px; border: none;"
        )
        cl.addWidget(self._lbl_active_model)

        self.btn_model = QPushButton("📊 모델 현황")
        self.btn_model.setObjectName("ModelBtn")
        self.btn_model.setFixedWidth(100)
        self.btn_model.setToolTip("모델 갤러리 열기")
        self.btn_model.clicked.connect(self._open_model_gallery)
        cl.addWidget(self.btn_model)

        # ── mode 콤보박스 ────────────────────────────────────────────────
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
        self.api_key_input.setFixedWidth(150)
        cl.addWidget(self.api_key_input)

        # ── Judge 선택 ────────────────────────────────────────────────
        self.judge_combo = QComboBox()
        self.judge_combo.addItems([
            "exaone3:7.8b",
            "qwen2.5:3b",
            "llama3.2:3b",
            "gpt-4o-mini"
        ])
        self.judge_combo.setFixedWidth(110)
        self.judge_combo.setToolTip("결과를 채점할 AI 판정관 모델 선택")
        self.judge_combo.currentIndexChanged.connect(self._on_judge_change)
        cl.addWidget(QLabel("Judge:"))
        cl.addWidget(self.judge_combo)

        # ── 채팅 토글 버튼 ───────────────────────────────────────────────
        self.btn_chat = QPushButton("🗨️ 대화형 벤치마크")
        self.btn_chat.setObjectName("ChatToggleBtn")
        self.btn_chat.setCheckable(True)
        self.btn_chat.setFixedWidth(130)
        self.btn_chat.setToolTip("채팅 벤치마크 패널 열기/닫기")
        self.btn_chat.clicked.connect(self._toggle_chat)
        self.btn_chat.setStyleSheet(
            "QPushButton#ChatToggleBtn { background-color: #1e293b;"
            " border: 1px solid #334155; border-radius: 6px; color: #94a3b8;"
            " font-weight: 600; font-size: 11px; }"
            "QPushButton#ChatToggleBtn:checked { background-color: #1d4ed8;"
            " border: 1px solid #3b82f6; color: white; }"
            "QPushButton#ChatToggleBtn:hover { border-color: #3b82f6; }"
        )
        cl.addWidget(self.btn_chat)

        # ── Tuning 버튼 ────────────────────────────────────────────────
        self.btn_tuning = QPushButton("⚙️ Tuning")
        self.btn_tuning.setObjectName("TuningBtn")
        self.btn_tuning.setFixedWidth(80)
        self.btn_tuning.setToolTip("모델 샘플링 파라미터 미세 조정")
        self.btn_tuning.clicked.connect(self._open_tuning_dialog)
        cl.addWidget(self.btn_tuning)

        # ── RUN 버튼 ─────────────────────────────────────────────────────
        self.btn_run = QPushButton("⚡  RUN")
        self.btn_run.setObjectName("RunButton")
        self.btn_run.setFixedWidth(90)
        self.btn_run.clicked.connect(self.run_benchmark_signal.emit)
        cl.addWidget(self.btn_run)

        # ── 보고서 버튼 ──────────────────────────────────────────────────
        self.btn_report = QPushButton("📊 보고서")
        self.btn_report.setFixedWidth(84)
        self.btn_report.setToolTip("벤치마크 결과 CSV 뷰어")
        self.btn_report.clicked.connect(self._open_report)
        cl.addWidget(self.btn_report)

        self.btn_chaos = QPushButton("🔥")
        self.btn_chaos.setFixedWidth(38)
        self.btn_chaos.setCheckable(True)  # 토글 가능하게
        self.btn_chaos.setToolTip("Chaos Monkey – 토글 ON/OFF")
        self.btn_chaos.setStyleSheet("background-color: #f59e0b; color: #0f172a; border: none; border-radius: 4px;")
        self.btn_chaos.clicked.connect(self._on_chaos_toggle)  # 직접 신호 대신 함수 호출
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

    # ── Telemetry bar ────────────────────────────────────────────────────

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

    # ── Graph section ────────────────────────────────────────────────────

    def _build_graphs(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self.cpu_plot = pg.PlotWidget(title="CPU Load (%)")
        self.cpu_plot.setYRange(0, 100)
        self.cpu_plot.showGrid(x=True, y=True, alpha=0.5)
        self.cpu_plot.getAxis('left').setTicks([[(i, str(i)) for i in range(0, 101, 5)]])
        self.cpu_curve    = self.cpu_plot.plot(pen=pg.mkPen('#3b82f6', width=2))
        self.cpu_ma_curve = self.cpu_plot.plot(pen=pg.mkPen('#93c5fd', width=1, style=Qt.DashLine))
        self.cpu_hover    = pg.TextItem('', anchor=(0, 1), color='#f8fafc')
        self.cpu_plot.addItem(self.cpu_hover, ignoreBounds=True)
        self._configure_plot(self.cpu_plot)
        row.addWidget(self.cpu_plot)

        self.ram_plot = pg.PlotWidget(title="RAM Usage (%)")
        self.ram_plot.setYRange(0, 100)
        self.ram_plot.showGrid(x=True, y=True, alpha=0.5)
        self.ram_plot.getAxis('left').setTicks([[(i, str(i)) for i in range(0, 101, 5)]])
        self.ram_curve    = self.ram_plot.plot(pen=pg.mkPen('#10b981', width=2))
        self.ram_ma_curve = self.ram_plot.plot(pen=pg.mkPen('#6ee7b7', width=1, style=Qt.DashLine))
        self.ram_hover    = pg.TextItem('', anchor=(0, 1), color='#f8fafc')
        self.ram_plot.addItem(self.ram_hover, ignoreBounds=True)
        self._configure_plot(self.ram_plot)
        row.addWidget(self.ram_plot)

        if self.specs.has_nvidia:
            self.gpu_plot = pg.PlotWidget(title="GPU (%)")
            self.gpu_plot.setYRange(0, 100)
            self.gpu_curve    = self.gpu_plot.plot(pen=pg.mkPen('#f59e0b', width=2))
            self.gpu_ma_curve = self.gpu_plot.plot(pen=pg.mkPen('#fde68a', width=1, style=Qt.DashLine))
            self.gpu_hover    = pg.TextItem('', anchor=(0, 1), color='#f8fafc')
            self.gpu_plot.addItem(self.gpu_hover, ignoreBounds=True)
            self._configure_plot(self.gpu_plot)
            row.addWidget(self.gpu_plot)

        self.tok_plot = pg.PlotWidget(title="Token Usage (cumulative)")
        self.tok_curve    = self.tok_plot.plot(pen=pg.mkPen('#a855f7', width=2))
        self.tok_ma_curve = self.tok_plot.plot(pen=pg.mkPen('#c084fc', width=1, style=Qt.DashLine))
        self.tok_hover    = pg.TextItem('', anchor=(0, 1), color='#f8fafc')
        self.tok_plot.addItem(self.tok_hover, ignoreBounds=True)
        self._configure_plot(self.tok_plot)
        row.addWidget(self.tok_plot)

        return row

    def _configure_plot(self, plot: pg.PlotWidget):
        plot.setMouseEnabled(x=True, y=True)
        plot.setMenuEnabled(False)
        view = plot.getViewBox()
        view.setMouseMode(pg.ViewBox.PanMode)
        view.sigRangeChanged.connect(self._on_view_range_changed)
        plot.scene().sigMouseMoved.connect(lambda pos, p=plot: self._on_plot_hover(pos, p))

    def _moving_average(self, data, window=10):
        if not data or window <= 1:
            return []
        if len(data) < window:
            window = len(data)
        ma = []
        acc = 0.0
        for i, value in enumerate(data):
            acc += value
            if i >= window:
                acc -= data[i - window]
            if i >= window - 1:
                ma.append(round(acc / window, 2))
        return ma

    def _set_plot_xrange(self, plot, xmin, xmax):
        self._suppress_range_change = True
        plot.getViewBox().setXRange(xmin, xmax, padding=0)
        self._suppress_range_change = False

    def _on_view_range_changed(self, view_box, ranges):
        if self._suppress_range_change:
            return
        self._user_panned = True

    def _on_plot_hover(self, scene_pos, plot):
        if not plot.sceneBoundingRect().contains(scene_pos):
            return
        view_pos = plot.getViewBox().mapSceneToView(scene_pos)
        if view_pos is None:
            return

        if plot is self.cpu_plot:
            x_data, y_data, hover_item = self.cpu_x, self.cpu_data, self.cpu_hover
        elif plot is self.ram_plot:
            x_data, y_data, hover_item = self.ram_x, self.ram_data, self.ram_hover
        elif plot is getattr(self, 'gpu_plot', None):
            x_data, y_data, hover_item = self.gpu_x, self.gpu_data, self.gpu_hover
        elif plot is self.tok_plot:
            x_data, y_data, hover_item = self.tok_x, self.tok_data, self.tok_hover
        else:
            return

        if not x_data or not y_data:
            hover_item.hide()
            return

        index = int(round(view_pos.x()))
        if index < 0 or index >= len(x_data):
            hover_item.hide()
            return

        value = y_data[index]
        
        # [Fix] pyqtgraph의 타이틀 라벨 텍스트를 안전하게 추출
        try:
            p_item = plot.getPlotItem()
            title = p_item.titleLabel.text if hasattr(p_item.titleLabel, 'text') and not callable(p_item.titleLabel.text) else "Metric"
            # 만약 callable이라면 호출
            if hasattr(p_item.titleLabel, 'text') and callable(p_item.titleLabel.text):
                title = p_item.titleLabel.text()
        except:
            title = "Metric"

        hover_item.setText(f"{title}\nIndex: {index}\nValue: {value:.2f}")
        hover_item.setPos(x_data[index], y_data[index])
        hover_item.show()

    # ── Console tabs ─────────────────────────────────────────────────────

    def _build_console_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        analytics_widget = self._wrap_console(self.console, "📊  ANALYTICS & INSIGHTS")
        self.tabs.addTab(analytics_widget, "📊  ANALYTICS")

        self.sys_console = QTextEdit()
        self.sys_console.setReadOnly(True)
        kernel_widget = self._wrap_console(self.sys_console, "⚙️  KERNEL TELEMETRY")
        self.tabs.addTab(kernel_widget, "⚙️  KERNEL TELEMETRY")

        self.stream_console = QTextEdit()
        self.stream_console.setReadOnly(True)
        self.stream_console.setStyleSheet("font-family: 'Consolas', 'Courier New'; font-size: 13px; color: #10b981;")
        streaming_widget = self._wrap_console(self.stream_console, "🛰️  REAL-TIME INFERENCE STREAM")
        self.tabs.addTab(streaming_widget, "🛰️  STREAMING")

        return self.tabs

    def _wrap_console(self, console: QTextEdit, title: str) -> QWidget:
        wrapper = QWidget()
        vl = QVBoxLayout(wrapper)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        hdr = QWidget()
        hdr.setFixedHeight(30)
        hdr.setStyleSheet("background-color: #1e293b; border-bottom: 1px solid #334155;")
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

    # ────────────────────────────────────────────────────────────────────────
    # Chat toggle & model gallery
    # ────────────────────────────────────────────────────────────────────────

    def _toggle_chat(self):
        is_opening = self.btn_chat.isChecked()
        self.chat_panel.toggle()
        self.btn_run.setEnabled(not is_opening)

    def _open_model_gallery(self):
        from ui.model_gallery import ModelGalleryDialog
        dlg = ModelGalleryDialog(current_model=self._active_model, parent=self)
        dlg.model_selected.connect(self.set_active_model)
        dlg.exec()

    def _open_tuning_dialog(self):
        from ui.model_tuning_dialog import ModelTuningDialog
        
        # [Safety Check] 커널 부팅 전에는 세션이 없으므로 경고
        if not self.ctrl.active_session:
            self.show_toast("⚠ 커널을 먼저 부팅해야 튜닝이 가능합니다.")
            return

        # 현재 세션의 스트레스 설정(Tuning 포함) 로드
        dlg = ModelTuningDialog(current_options=self.ctrl.active_session.stress_config, parent=self)
        
        def on_settings_save(new_opts):
            self.ctrl.active_session.stress_config = new_opts
            self.show_toast("✅ Tuning parameters applied.")
            self.log_bench(f"[SYSTEM] Parameters Updated: Temp={new_opts.temperature}, Penalty={new_opts.repeat_penalty}")
            
        dlg.settings_updated.connect(on_settings_save)
        dlg.exec()

    def _open_report(self):
        from ui.data_table_dialog import open_report_viewer
        open_report_viewer("Edge_v5_Singularity_Report.csv", parent=self)

    # ────────────────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────────────────

    def set_active_model(self, name: str, engine_type: str):
        self._active_model = name
        self._active_engine = engine_type
        self._lbl_active_model.setText(f"모델: {name} ({engine_type})")
        self.show_toast(f"✅ 모델 변경됨: {name} [{engine_type}]")

    def get_active_engine(self) -> str:
        return self._active_engine

    def get_active_model(self) -> str:
        return self._active_model

    def clear_logs(self):
        self.console.clear()
        self.sys_console.clear()
        self.cpu_data  = []
        self.ram_data  = []
        self.gpu_data  = []
        self.tok_data  = []
        self.cpu_x     = []
        self.ram_x     = []
        self.gpu_x     = []
        self.tok_x     = []
        self._tok_cum  = 0
        self._telemetry_index = 0
        self._user_panned = False
        self.cpu_curve.setData([])
        self.cpu_ma_curve.setData([])
        self.ram_curve.setData([])
        self.ram_ma_curve.setData([])
        self.tok_curve.setData([])
        self.tok_ma_curve.setData([])
        if self.specs.has_nvidia:
            self.gpu_curve.setData([])
            self.gpu_ma_curve.setData([])
        self.lbl_engine_info.setText("MATRIX STATUS: INITIALIZING...")
        self.lbl_ram_usage.setText("RAM Usage: 0%")
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
            w, h
        )

    def focus_log_tab(self):
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
            used_mb  = usage / 1024 / 1024
            limit_mb = limit / 1024 / 1024

            cpu_stats = stats.get('cpu_stats', {})
            precpu    = stats.get('precpu_stats', {})
            cpu_delta    = cpu_stats.get('cpu_usage', {}).get('total_usage', 0) - precpu.get('cpu_usage', {}).get('total_usage', 0)
            system_delta = cpu_stats.get('system_cpu_usage', 0) - precpu.get('system_cpu_usage', 0)
            online_cpus  = cpu_stats.get('online_cpus') or len(cpu_stats.get('cpu_usage', {}).get('percpu_usage', []) or [1])
            if system_delta > 0 and cpu_delta > 0:
                cpu_pct = (cpu_delta / system_delta) * online_cpus * 100.0
        except Exception:
            pass
        return cpu_pct, mem_pct, used_mb, limit_mb

    def update_token_count(self, delta: int):
        self._tok_cum += delta
        self.tok_x.append(len(self.tok_x))
        self.tok_data.append(self._tok_cum)
        self._update_plot_data(
            plot=self.tok_plot, curve=self.tok_curve,
            ma_curve=self.tok_ma_curve,
            x_data=self.tok_x, y_data=self.tok_data
        )

    def _update_plot_data(self, plot, curve, ma_curve, x_data, y_data):
        curve.setData(x_data, y_data)
        ma = self._moving_average(y_data, window=10)
        if ma:
            ma_curve.setData(x_data[-len(ma):], ma)
        else:
            ma_curve.setData([], [])
        if not self._user_panned and x_data:
            self._set_plot_xrange(plot, max(0, x_data[-1] - self._HISTORY), x_data[-1])

    def _on_judge_change(self):
        if self.ctrl.active_session:
            model = self.judge_combo.currentText()
            self.ctrl.active_session.stress_config.judge_model = model
            self.log_bench(f"⚖️ 판정관 변경됨: {model}")

    def append_stream(self, text: str):
        """실시간 스트리밍 탭에 텍스트 청크 추가"""
        cursor = self.stream_console.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.stream_console.ensureCursorVisible()

    def clear_stream(self):
        """스트리밍 창 초기화"""
        self.stream_console.clear()
        self.stream_console.append("<span style='color:#64748b;'>📡 Waiting for inference stream...</span><br>")

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
        bg    = '#020617' if is_dark else '#ffffff'
        fg    = '#f8fafc' if is_dark else '#0f172a'  # 훨씬 밝은 텍스트
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
            # 차트 제목 폰트 크기 확대
            if hasattr(p, 'titleLabel') and p.titleLabel:
                p.titleLabel.setStyleSheet(f"color: {fg}; font-weight: bold; font-size: 12px;")

        console_style = (
            f"background-color: {bg}; color: {'#94a3b8' if is_dark else '#1e293b'};"
            " border: none; border-radius: 0;"
            " font-family: 'JetBrains Mono','Consolas',monospace; font-size: 11px; padding: 8px;"
        )
        self.sys_console.setStyleSheet(console_style)

    def update_telemetry(self, cpu, mem_u, mem_l, bat_pct, gpu=None):
        self.bar_battery.setValue(int(bat_pct))
        self.lbl_battery.setText(f"Reliability: {bat_pct:.1f}%")

    # ── 0.1s Telemetry Polling ───────────────────────────────────────────

    def _poll_telemetry(self):
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
            used_mb  = mem.used / 1024 / 1024
            total_mb = mem.total / 1024 / 1024
            ram_label_text = f"RAM Usage: {ram_percent:.1f}% ({used_mb:.0f}/{total_mb:.0f}MB)"

        self.lbl_ram_usage.setText(ram_label_text)

        self._telemetry_index += 1
        self.cpu_x.append(self._telemetry_index)
        self.ram_x.append(self._telemetry_index)
        self.cpu_data.append(cpu)
        self.ram_data.append(ram_percent)

        self._update_plot_data(
            plot=self.cpu_plot, curve=self.cpu_curve,
            ma_curve=self.cpu_ma_curve,
            x_data=self.cpu_x, y_data=self.cpu_data
        )
        self._update_plot_data(
            plot=self.ram_plot, curve=self.ram_curve,
            ma_curve=self.ram_ma_curve,
            x_data=self.ram_x, y_data=self.ram_data
        )

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
                self.gpu_x.append(self._telemetry_index)
                self.gpu_data.append(gpu_pct)
                self._update_plot_data(
                    plot=self.gpu_plot, curve=self.gpu_curve,
                    ma_curve=self.gpu_ma_curve,
                    x_data=self.gpu_x, y_data=self.gpu_data
                )
            except Exception:
                pass

    # ── Slots ────────────────────────────────────────────────────────────

    def _on_chaos_toggle(self):
        """[Engineering] 카오스 모드 토글 시 시각적 피드백 강화"""
        is_on = self.btn_chaos.isChecked()
        if is_on:
            # ON: 오렌지 엑센트 강화
            self.btn_chaos.setStyleSheet("background-color: #ff6b35; color: #fff; border: 2px solid #ff9500; border-radius: 4px; font-weight: bold;")
            # 컨트롤 바 배경을 약간 붉은색계열로 변경하여 위험 상태 알림
            self.findChild(QFrame, "ControlCard").setStyleSheet(
                "QFrame#ControlCard { background-color: #451a03; border: 1px solid #f97316; border-radius: 8px; }"
            )
            self.show_toast("🔥 CHAOS MODE: 인젝션 활성화 (Virtual Stress ON)")
        else:
            # OFF: 원래대로 복구
            self.btn_chaos.setStyleSheet("background-color: #f59e0b; color: #0f172a; border: none; border-radius: 4px;")
            self.findChild(QFrame, "ControlCard").setStyleSheet(
                "QFrame#ControlCard { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }"
            )
            self.show_toast("✅ CHAOS MODE: 해제됨")
        
        self.chaos_monkey_signal.emit()


    def _on_shutdown_clicked(self):
        self.shutdown_signal.emit()

    def resizeEvent(self, event):
        if self._overlay.isVisible():
            self._overlay.setGeometry(0, 0, self.width(), self.height())
        if self.toast_label.isVisible():
            self._position_toast()
        super().resizeEvent(event)