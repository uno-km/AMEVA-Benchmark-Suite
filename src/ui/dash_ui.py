import pyqtgraph as pg
from PySide6.QtWidgets import (QApplication, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QTextEdit, QComboBox, QGroupBox, 
                               QLineEdit, QProgressBar, QTabWidget)

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
        
        # ✅ [신규 기능] 뒤로 가기 (마운트 해제) 버튼 추가!
        self.btn_back = QPushButton(" ◀ 뒤로 가기 (자원 반납)")
        self.btn_back.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold;") # 빨간색 경고 스타일
        self.btn_back.clicked.connect(self.on_back_button_clicked)
        ctrl_layout.addWidget(self.btn_back)
        
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
        
        self.tabs = QTabWidget()
        
        # 1번 탭: 벤치마크 결과창 (기존 콘솔)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.tabs.addTab(self.console, "📊 벤치마크 리포트")
        
        # 2번 탭: 매트릭스 시스템 콘솔 (해커 스타일 텍스트창)
        self.sys_console = QTextEdit()
        self.sys_console.setReadOnly(True)
        self.sys_console.setStyleSheet("background-color: #0a0a0a; color: #10b981; font-family: Consolas, monospace; font-size: 13px;")
        self.tabs.addTab(self.sys_console, "⚙️ 시스템 콘솔 (Matrix)")
        
        l.addWidget(self.tabs)
        
    # ================= ✅ [신규] 뒤로 가기 및 셧다운 메서드 =================
    def on_back_button_clicked(self):
        # 1. 안전 확인 팝업 (경고창) 띄우기
        reply = QMessageBox.question(
            self,
            '매트릭스 마운트 해제 및 자원 반납',
            '현재 구동 중인 매트릭스의 자원을 반납하고 마운트를 해제하시겠습니까?\n(컨테이너가 파괴되며 메인 화면으로 돌아갑니다)',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No # 기본값은 '아니오'로 설정하여 실수 방지
        )

        # 2. 사용자가 '예(Yes)'를 눌렀을 경우
        if reply == QMessageBox.StandardButton.Yes:
            print("\n[UI] 아키텍트 승인: 매트릭스 마운트 해제 시퀀스 가동.")
            self.log("\n[SYSTEM] 매트릭스 파괴 및 호스트 자원 반납 시퀀스 가동...") # UI 콘솔에도 출력
            
            # 3. 도커 자원 및 마운트 안전 해제 (ctrl.engine 호출!)
            if hasattr(self.ctrl, 'engine'): 
                self.ctrl.engine.shutdown()
                self.log("[SYSTEM] 🟢 모든 자원 반환 완료. 메인 통제실로 복귀합니다.")
            
            # 4. 화면 전환 (메인 화면으로 돌아가기)
            # (현재 아키텍트님의 QStackedWidget이나 Main Window를 제어하는 함수를 여기에 연결하세요!)
            # 예시: self.parent().parent().setCurrentIndex(0) 
            print("[UI] 메인 통제실로 복귀 완료.")
        
        # 3. 사용자가 '아니오(No)'를 눌렀을 경우
        else:
            print("\n[UI] 마운트 해제 취소. 모니터링을 계속 유지합니다.")
            self.log("[UI] 마운트 해제 취소. 현재 통제권을 유지합니다.")
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
        """1번 탭: 벤치마크용 로그"""
        self.console.append(text)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
        QApplication.processEvents() # UI 즉각 업데이트

    def log_sys(self, text):
        """2번 탭: 도커 엔진 시스템용 로그"""
        self.sys_console.append(text)
        self.sys_console.verticalScrollBar().setValue(self.sys_console.verticalScrollBar().maximum())
        QApplication.processEvents() # UI 즉각 업데이트 (스피너 애니메이션을 위해 필수!)
