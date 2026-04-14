import sys
import os
import csv

# Ensure local source packages load before any top-level workspace folders like /models
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox
from PySide6.QtCore import Qt

# 모델 (데이터 및 사양)
from models.hardware import HardwareService
from models.report_db import ReportManager
from models.settings import BenchmarkSession

# UI (뷰)
from ui.wizard_ui import WizardUI
from ui.dash_ui import DashUI
from ui.style import PremiumStyle
from ui.harness_ui import HarnessManagerUI

# 엔진 (실행 로직)
from core.matrix_engine import MatrixEngine
from core.benchmark_manager import ExecutionEngine
from core.boot_thread import BootThread


class AMEVAController(QMainWindow):
    """[V5.5] 메인 컨트롤러 (MVC)"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMEVA EDGE MATRIX v5.5")
        # 노트북 친화적 크기
        self.setGeometry(100, 80, 1100, 750)
        self.setMinimumSize(900, 620)

        # ── 테마 ──────────────────────────────────────────────────────
        self.is_dark_mode = True
        self.setStyleSheet(PremiumStyle.get_qss(self.is_dark_mode))

        # ── 구성 요소 초기화 ──────────────────────────────────────────
        self.hardware       = HardwareService.detect_capabilities()
        self.db             = ReportManager()
        self.engine         = MatrixEngine()
        self.active_session = None
        self.active_runner  = None
        self._boot_thread   = None

        # ── 내비게이션 스택 ───────────────────────────────────────────
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.view_wizard  = WizardUI(self)
        self.view_dash    = DashUI(self)

        self.stack.addWidget(self.view_wizard)   # 0
        self.stack.addWidget(self.view_dash)     # 1

        # ── 시그널 연결 ───────────────────────────────────────────────
        self.view_dash.run_benchmark_signal.connect(self.handle_run_request)
        self.view_dash.chaos_monkey_signal.connect(self.engine.inject_chaos)
        self.view_dash.shutdown_signal.connect(self.handle_shutdown)

    # ──────────────────────────────────────────────────────────────────
    # Theme
    # ──────────────────────────────────────────────────────────────────

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.setStyleSheet(PremiumStyle.get_qss(self.is_dark_mode))
        self.view_dash.apply_theme_to_graphs(self.is_dark_mode)

    # ──────────────────────────────────────────────────────────────────
    # Boot Sequence  (#6 즉시 화면 전환 + #7 로그탭 포커스)
    # ──────────────────────────────────────────────────────────────────

    def execute_boot_sequence(self, session: BenchmarkSession):
        self.active_session = session

        # 1. 로그 초기화 (#10)
        self.view_dash.clear_logs()

        # 2. 즉시 대시보드로 전환 (#6)
        self.stack.setCurrentIndex(1)

        # 3. 커널 텔레메트리 탭 포커스 (#7)
        self.view_dash.focus_log_tab()

        # 4. 비동기 부팅 스레드 시작 (#8, #9)
        self._boot_thread = BootThread(
            config={
                "engine":    session.boot_config.engine,
                "cpu_cores": session.boot_config.cpu_cores,
                "ram_mb":    session.boot_config.ram_mb,
                "gpu_layers": session.boot_config.gpu_layers,
            },
            engine=self.engine
        )
        self._boot_thread.log_signal.connect(self.view_dash.log_sys)
        self._boot_thread.done_signal.connect(self._on_boot_done)
        self._boot_thread.start()

    def _on_boot_done(self, success: bool, msg: str):
        if success:
            self.view_dash.update_engine_status(msg)
            self.view_dash.log_sys(f"✅ 부팅 완료: {msg}")
            self.view_dash.show_toast("커널 온라인. 안전하게 연결되었습니다.")
        else:
            QMessageBox.critical(self, "커널 패닉", f"부팅 실패:\n{msg}")
            self.stack.setCurrentIndex(0)

    # ──────────────────────────────────────────────────────────────────
    # Benchmark Run (#13 sys_log_signal 연결)
    # ──────────────────────────────────────────────────────────────────

    def handle_run_request(self):
        if not self.active_session:
            return

        self.active_session.boot_config.model_name = self.view_dash.model_combo.currentText()
        self.active_session.run_mode               = self.view_dash.mode_combo.currentText()
        self.active_session.judge_key              = self.view_dash.api_key_input.text().strip()

        harness = self._load_harness_data()
        if not harness:
            QMessageBox.warning(
                self, "하네스 데이터 없음",
                "harness_v4.csv 파일이 없거나, 태스크가 없습니다.\n"
                "HARNESS MANAGER에서 태스크를 추가한 뒤 다시 실행하세요."
            )
            return

        self.view_dash.btn_run.setEnabled(False)
        self.active_runner = ExecutionEngine(
            self.active_session, harness, self.engine
        )
        # Analytics 탭
        self.active_runner.log_signal.connect(self.view_dash.log_bench)
        # Kernel Telemetry 탭 (엔진 원시 출력) (#13)
        self.active_runner.sys_log_signal.connect(self.view_dash.log_sys)
        # Token 그래프 (#12)
        self.active_runner.token_signal.connect(self.view_dash.update_token_count)
        # 완료 처리
        self.active_runner.report_signal.connect(self.handle_report_generation)
        self.active_runner.start()

    def handle_report_generation(self, results):
        self.db.insert_batch(results)
        self.view_dash.log_bench(
            f"\n📊 {len(results)}건 결과가 Edge_v5_Singularity_Report.csv 에 저장되었습니다."
        )
        self.view_dash.btn_run.setEnabled(True)
        self.view_dash.show_toast("벤치마크 완료. 결과가 안전하게 저장되었습니다.")

    # ──────────────────────────────────────────────────────────────────
    # Shutdown  (#10 로그 초기화 보장)
    # ──────────────────────────────────────────────────────────────────

    def handle_shutdown(self):
        if self.active_runner and self.active_runner.isRunning():
            answer = QMessageBox.question(
                self, "작업 취소 확인",
                "현재 벤치마크가 진행중입니다.\n작업을 취소하고 메인 화면으로 돌아가시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return
            self.active_runner.requestInterruption()
            self.view_dash.show_toast("벤치마크 취소 요청 중... 안전하게 종료합니다.")
            self.active_runner.wait(2000)

        elif self._boot_thread and self._boot_thread.isRunning():
            answer = QMessageBox.question(
                self, "부팅 취소 확인",
                "커널 부팅 또는 초기화가 진행중입니다.\n메인 화면으로 돌아가시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return
            self._boot_thread.requestInterruption()
            self.view_dash.show_toast("부팅 취소 요청 중... 안전하게 돌아갑니다.")
            self._boot_thread.wait(2000)

        self.engine.shutdown()
        self.active_session = None
        self.active_runner = None
        self._boot_thread = None
        self.view_dash.btn_run.setEnabled(True)
        # 위저드로 복귀 전 로그 초기화 (#10)
        self.view_dash.clear_logs()
        self.stack.setCurrentIndex(0)
        self.view_dash.show_toast("커널 닫기, 마운트 해제, 접속 해제가 완료되었습니다.")

    def show_harness_manager(self):
        dialog = HarnessManagerUI(self)
        dialog.exec()

    def _load_harness_data(self):
        fname = "harness_v4.csv"
        data = []
        if os.path.exists(fname):
            with open(fname, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                data = list(reader)
        return data


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    controller = AMEVAController()
    controller.show()

    sys.exit(app.exec())