import sys, os, csv
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox
from core.docker_engine import MatrixEngine
from core.benchmark import SystemMonitor, BenchmarkRunner
from ui.wizard_ui import WizardUI
from ui.dash_ui import DashUI

class MainController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("THE CODE GOD: EdgeMatrix Pro v4.0 [Singularity]")
        self.setGeometry(100, 100, 1200, 850)
        
        qss_path = os.path.join(os.path.dirname(__file__), "..", "resources", "theme.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f: self.setStyleSheet(f.read())

        self.engine = MatrixEngine()
        self.monitor = None
        self.runner = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.wizard = WizardUI(self)
        self.dash = DashUI(self)
        self.stack.addWidget(self.wizard)
        self.stack.addWidget(self.dash)

    def execute_boot(self, config):
        self.wizard.boot_btn.setEnabled(False)
        self.wizard.boot_btn.setText("커널 접속 중...")
        QApplication.processEvents()

        success, msg = self.engine.boot_matrix(config)
        if success:
            self.stack.setCurrentIndex(1)
            self.monitor = SystemMonitor(self.engine.container, self.engine)
            self.monitor.stats_signal.connect(self.dash.update_stats)
            self.monitor.blackout_signal.connect(self.dash.trigger_blackout)
            self.monitor.start()
        else:
            QMessageBox.critical(self, "Kernel Panic", f"부팅 실패:\n{msg}")
        
        self.wizard.boot_btn.setEnabled(True)
        self.wizard.boot_btn.setText(" 하드코어 매트릭스 강제 부팅")
        
    def start_benchmark(self, model_name, custom_dataset, judge_key):
        self.runner = BenchmarkRunner(model_name, custom_dataset, judge_key)
        self.runner.current_blackout_state = False
        self.runner.log_signal.connect(self.dash.log)
        self.runner.report_signal.connect(self._save_report)
        self.runner.start()

    def _save_report(self, results):
        fname = "Edge_v4_Singularity_Report.csv"
        try:
            with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=["Task", "Judge_Result", "TTFT(s)", "Total_Time(s)", "TPS", "Blackout_During_Test", "Output_Preview"])
                writer.writeheader()
                writer.writerows(results)
            self.dash.log(f"\n [완료] 특이점 리포트 저장됨: {os.path.abspath(fname)}")
        except Exception as e: self.dash.log(f"오류: {e}")
        self.dash.btn_run.setEnabled(True)

    def closeEvent(self, event):
        if self.monitor: self.monitor.stop()
        self.engine.shutdown()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainController()
    w.show()
    sys.exit(app.exec())