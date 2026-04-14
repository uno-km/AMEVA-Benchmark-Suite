import os
import pyqtgraph as pg
from PySide6.QtWidgets import (QApplication, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QTextEdit, QComboBox, QGroupBox, 
                               QLineEdit, QProgressBar, QTabWidget, QFrame)
from PySide6.QtCore import Qt, Signal
from models.hardware import HardwareService

class DashUI(QWidget):
    run_benchmark_signal = Signal()
    chaos_monkey_signal = Signal()
    shutdown_signal = Signal()

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.specs = HardwareService.detect_capabilities()
        
        self.time_data = list(range(100))
        self.cpu_data = [0]*100
        self.ram_data = [0]*100
        self._setup()

    def _setup(self):
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        
        # 1. 상단 제어 바
        ctrl_card = QFrame()
        ctrl_card.setObjectName("ControlCard")
        ctrl_card.setStyleSheet("background-color: #161b22; border-radius: 12px; border: 1px solid #30363d;")
        cl = QHBoxLayout(ctrl_card)
        
        self.lbl_engine_info = QLabel("매트릭스 상태: 대기 중")
        self.lbl_engine_info.setStyleSheet("color: #00ffcc; font-weight: bold; border: none;")
        cl.addWidget(self.lbl_engine_info)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["qwen2.5:0.5b", "llama3.2:1b"])
        cl.addWidget(QLabel("모델:"))
        cl.addWidget(self.model_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "추론 모드 (기본)", 
            "스트레스 테스트 모드 (llama-bench)", 
            "전력 효율 모드"
        ])
        cl.addWidget(QLabel("모드:"))
        cl.addWidget(self.mode_combo)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("LLM 판정용 키 (OpenAI)")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setFixedWidth(200)
        cl.addWidget(self.api_key_input)

        self.btn_run = QPushButton("⚡ 태스크 시작")
        self.btn_run.setObjectName("RunButton")
        self.btn_run.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold; padding: 10px 20px;")
        self.btn_run.clicked.connect(self.run_benchmark_signal.emit)
        cl.addWidget(self.btn_run)

        self.btn_chaos = QPushButton("💀 카오스")
        self.btn_chaos.setStyleSheet("background-color: #f59e0b; color: black;")
        self.btn_chaos.clicked.connect(self.chaos_monkey_signal.emit)
        cl.addWidget(self.btn_chaos)

        self.btn_back = QPushButton("🚫 셧다운")
        self.btn_back.setStyleSheet("background-color: #ef4444; color: white;")
        self.btn_back.clicked.connect(self._on_shutdown_clicked)
        cl.addWidget(self.btn_back)
        
        l.addWidget(ctrl_card)

        # 2. 텔레메트리 바
        tel_layout = QHBoxLayout()
        
        # 가상 배터리 (시스템 건전성 체크용)
        bat_group = QGroupBox("업타임 / 배터리")
        bl = QVBoxLayout()
        self.bar_battery = QProgressBar()
        self.bar_battery.setValue(100)
        self.lbl_battery = QLabel("잔량: 100%")
        bl.addWidget(self.lbl_battery)
        bl.addWidget(self.bar_battery)
        bat_group.setLayout(bl)
        tel_layout.addWidget(bat_group)

        # 블랙아웃 표시기
        self.lbl_blackout = QLabel("")
        self.lbl_blackout.setStyleSheet("color: #ef4444; font-weight: bold;")
        tel_layout.addWidget(self.lbl_blackout)
        
        l.addLayout(tel_layout)

        # 3. 그래프 섹션
        graph_box = QHBoxLayout()
        pg.setConfigOption('background', '#0d1117')
        
        self.cpu_plot = pg.PlotWidget(title="코어 부하 (%)")
        self.cpu_plot.setYRange(0, 100)
        self.cpu_curve = self.cpu_plot.plot(pen=pg.mkPen('#00ffcc', width=2))
        graph_box.addWidget(self.cpu_plot)

        self.ram_plot = pg.PlotWidget(title="메모리 사용량 (MB)")
        self.ram_curve = self.ram_plot.plot(pen=pg.mkPen('#3b82f6', width=2))
        graph_box.addWidget(self.ram_plot)
        
        # GPU 그래프 - 조건부 표시
        if self.specs.has_nvidia:
            self.gpu_plot = pg.PlotWidget(title="신경망 부하 (GPU %)")
            self.gpu_plot.setYRange(0, 100)
            self.gpu_curve = self.gpu_plot.plot(pen=pg.mkPen('#ef4444', width=2))
            graph_box.addWidget(self.gpu_plot)
        
        l.addLayout(graph_box)

        # 4. 콘솔 탭
        self.tabs = QTabWidget()
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.tabs.addTab(self.console, "📊 분석 / 결과")
        
        self.sys_console = QTextEdit()
        self.sys_console.setReadOnly(True)
        self.sys_console.setStyleSheet("background-color: #010409; color: #00ffcc; font-family: 'Consolas';")
        self.tabs.addTab(self.sys_console, "⚙️ 커널 로그")
        
        l.addWidget(self.tabs)

    def _on_shutdown_clicked(self):
        reply = QMessageBox.question(self, '커널 종료', 
                                    '현재 매트릭스 아레나를 파괴하고 메인 화면으로 돌아가시겠습니까?',
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.shutdown_signal.emit()

    def update_telemetry(self, cpu, mem_u, mem_l, bat_pct, gpu=None):
        self.cpu_data = self.cpu_data[1:] + [cpu]
        self.ram_data = self.ram_data[1:] + [mem_u]
        self.cpu_curve.setData(self.time_data, self.cpu_data)
        self.ram_curve.setData(self.time_data, self.ram_data)
        self.ram_plot.setYRange(0, mem_l)
        
        self.bar_battery.setValue(int(bat_pct))
        self.lbl_battery.setText(f"잔량: {bat_pct:.1f}%")
        
        if self.specs.has_nvidia and gpu is not None:
            if not hasattr(self, 'gpu_data'): self.gpu_data = [0]*100
            self.gpu_data = self.gpu_data[1:] + [gpu]
            self.gpu_curve.setData(self.time_data, self.gpu_data)

    def log_bench(self, text):
        self.console.append(text)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def log_sys(self, text):
        self.sys_console.append(text)
        self.sys_console.verticalScrollBar().setValue(self.sys_console.verticalScrollBar().maximum())

    def update_engine_status(self, text):
        self.lbl_engine_info.setText(f"MATRIX STATUS: {text}")