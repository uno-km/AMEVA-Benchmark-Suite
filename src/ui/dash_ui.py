import pyqtgraph as pg
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextEdit, QComboBox, QGroupBox, QLineEdit, QProgressBar)

class DashUI(QWidget):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.time_data = list(range(100))
        self.cpu_data = [0]*100
        self.ram_data = [0]*100
        self._setup()

    def _setup(self):
        l = QVBoxLayout(self)
        
        # 상단 제어부
        ctrl_layout = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems(["qwen2.5:0.5b", "llama3.2:1b"])
        ctrl_layout.addWidget(QLabel("타겟 모델:"))
        ctrl_layout.addWidget(self.model_combo)

        # [기능 1] OpenAI API Key 입력창
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("LLM Judge용 OpenAI API Key (선택)")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        ctrl_layout.addWidget(self.api_key_input)

        self.btn_run = QPushButton(" 자동화 테스트 런닝")
        self.btn_run.clicked.connect(self._run)
        ctrl_layout.addWidget(self.btn_run)
        
        # [기능 3] 카오스 몽키 버튼
        self.btn_chaos = QPushButton(" 카오스 노이즈 주입")
        self.btn_chaos.setStyleSheet("background-color: #f59e0b; color: black;")
        self.btn_chaos.clicked.connect(self._inject_chaos)
        ctrl_layout.addWidget(self.btn_chaos)
        
        l.addLayout(ctrl_layout)
        
        # 배터리 바 [기능 2]
        bat_layout = QHBoxLayout()
        self.lbl_battery = QLabel(" 배터리 100%")
        self.bar_battery = QProgressBar()
        self.bar_battery.setValue(100)
        self.bar_battery.setStyleSheet("QProgressBar::chunk {background-color: #10b981;}")
        bat_layout.addWidget(self.lbl_battery)
        bat_layout.addWidget(self.bar_battery)
        l.addLayout(bat_layout)

        self.lbl_blackout = QLabel("")
        self.lbl_blackout.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 16px;")
        l.addWidget(self.lbl_blackout)

        # 그래프
        graph_group = QGroupBox(" 실시간 자원 모니터링")
        gl = QHBoxLayout()
        pg.setConfigOption('background', '#111827')
        self.cpu_plot = pg.PlotWidget(title="CPU Usage (%)"); self.cpu_plot.setYRange(0, 100)
        self.cpu_curve = self.cpu_plot.plot(pen=pg.mkPen('#ef4444', width=2))
        gl.addWidget(self.cpu_plot)
        self.ram_plot = pg.PlotWidget(title="RAM Usage (MB)")
        self.ram_curve = self.ram_plot.plot(pen=pg.mkPen('#10b981', width=2))
        gl.addWidget(self.ram_plot)
        graph_group.setLayout(gl)
        l.addWidget(graph_group)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        l.addWidget(self.console)

    def update_stats(self, cpu, mem_u, mem_l, pw, bat_pct):
        self.cpu_data = self.cpu_data[1:] + [cpu]
        self.ram_data = self.ram_data[1:] + [mem_u]
        self.cpu_curve.setData(self.time_data, self.cpu_data)
        self.ram_curve.setData(self.time_data, self.ram_data)
        self.ram_plot.setYRange(0, mem_l)
        
        self.bar_battery.setValue(int(bat_pct))
        self.lbl_battery.setText(f" 배터리 {bat_pct:.1f}%")
        
        # 배터리 경고 색상 변경
        if bat_pct < 20: self.bar_battery.setStyleSheet("QProgressBar::chunk {background-color: #ef4444;}")

    def trigger_blackout(self):
        self.lbl_blackout.setText(" 시스템 셧다운 (블랙아웃 발생) - 배터리 방전! (테스트는 멈추지 않고 리포트에 기록됩니다)")
        self.log(" [경고] 가상 배터리가 방전되었습니다. 이후 생성되는 토큰은 초과 데이터(Overdraft)로 기록됩니다.")
        # Runner 쓰레드에 블랙아웃 상태 전달
        if self.ctrl.runner:
            self.ctrl.runner.current_blackout_state = True

    def _inject_chaos(self):
        success = self.ctrl.engine.inject_chaos_monkey()
        if success: self.log(" [카오스 몽키] 백그라운드 OS 노이즈 주입 성공! (3초간 CPU 100% 점유율 폭발)")

    def _run(self):
        self.btn_run.setEnabled(False)
        self.console.clear()
        self.lbl_blackout.setText("")
        key = self.api_key_input.text().strip()
        self.ctrl.start_benchmark(self.model_combo.currentText(), None, key)

    def log(self, text):
        self.console.append(text)
