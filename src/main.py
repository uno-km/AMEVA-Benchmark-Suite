"""
main.py  –  AMEVA EDGE MATRIX v5.6 메인 컨트롤러 (MVC)
변경: 채팅 벤치마크 핸들러 + 모델명 상태 연동
"""
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
from core.chat_benchmark_engine import ChatBenchmarkEngine


class AMEVAController(QMainWindow):
    """[V5.6] 메인 컨트롤러 (MVC)"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMEVA EDGE MATRIX v5.6")
        self.setGeometry(100, 80, 1180, 760)
        self.setMinimumSize(920, 640)

        # ── 테마 ─────────────────────────────────────────────────────────
        self.is_dark_mode = True
        self.setStyleSheet(PremiumStyle.get_qss(self.is_dark_mode))

        # ── 구성 요소 초기화 ──────────────────────────────────────────────
        self.hardware       = HardwareService.detect_capabilities()
        self.db             = ReportManager()
        self.engine         = MatrixEngine()
        self.active_session = None
        self.active_runner  = None
        self._boot_thread   = None
        self._chat_runner   = None

        # ── 내비게이션 스택 ───────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.view_wizard = WizardUI(self)
        self.view_dash   = DashUI(self)

        self.stack.addWidget(self.view_wizard)   # 0
        self.stack.addWidget(self.view_dash)     # 1

        # ── 시그널 연결 ───────────────────────────────────────────────────
        self.view_dash.run_benchmark_signal.connect(self.handle_run_request)
        self.view_dash.chaos_monkey_signal.connect(self.engine.inject_chaos)
        self.view_dash.shutdown_signal.connect(self.handle_shutdown)
        self.view_dash.chat_panel.chat_submitted.connect(self.handle_chat_prompt)
        self.view_dash.chat_panel.chat_interrupted.connect(self._on_chat_interrupted)

    def _on_chat_interrupted(self):
        if self._chat_runner and self._chat_runner.isRunning():
            self._chat_runner.requestInterruption()
            self.view_dash.log_bench("🛑 채팅 벤치마크 중단 요청됨.")
            self.view_dash.show_toast("채팅 중단됨.")

    # ──────────────────────────────────────────────────────────────────────
    # Theme
    # ──────────────────────────────────────────────────────────────────────

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.setStyleSheet(PremiumStyle.get_qss(self.is_dark_mode))
        self.view_dash.apply_theme_to_graphs(self.is_dark_mode)

    # ──────────────────────────────────────────────────────────────────────
    # Boot Sequence
    # ──────────────────────────────────────────────────────────────────────

    def execute_boot_sequence(self, session: BenchmarkSession):
        self.active_session = session

        # 기본 모델명을 세션에 주입
        self.active_session.boot_config.model_name = (
            self.view_dash.get_active_model()
        )

        self.view_dash.clear_logs()
        self.stack.setCurrentIndex(1)
        self.view_dash.focus_log_tab()

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

    # ──────────────────────────────────────────────────────────────────────
    # Benchmark Run
    # ──────────────────────────────────────────────────────────────────────

    def handle_run_request(self):
        if not self.active_session:
            return

        # 모델명을 DashUI 레이블에서 읽음 (콤보박스 제거)
        self.active_session.boot_config.model_name = self.view_dash.get_active_model()
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

        # 채팅 패널이 열려 있으면 Run 차단
        if self.view_dash.chat_panel.is_open():
            QMessageBox.information(
                self, "채팅 모드 활성",
                "대화형 벤치마크 모드가 켜져 있습니다.\n"
                "채팅 벤치마크 버튼을 눌러 종료한 뒤 RUN을 사용하세요."
            )
            return

        self.view_dash.btn_run.setEnabled(False)
        self.view_dash.btn_chat.setEnabled(False)

        self.active_runner = ExecutionEngine(
            self.active_session, harness, self.engine
        )
        self.active_runner.log_signal.connect(self.view_dash.log_bench)
        self.active_runner.sys_log_signal.connect(self.view_dash.log_sys)
        self.active_runner.token_signal.connect(self.view_dash.update_token_count)
        self.active_runner.report_signal.connect(self.handle_report_generation)
        self.active_runner.start()

    def handle_report_generation(self, results):
        self.db.insert_batch(results)
        self.view_dash.log_bench(
            f"\n📊 {len(results)}건 결과가 Edge_v5_Singularity_Report.csv 에 저장되었습니다."
        )
        self.view_dash.btn_run.setEnabled(True)
        self.view_dash.btn_chat.setEnabled(True)
        self.view_dash.show_toast("벤치마크 완료. 결과가 안전하게 저장되었습니다.")

    # ──────────────────────────────────────────────────────────────────────
    # Chat Benchmark
    # ──────────────────────────────────────────────────────────────────────

    def handle_chat_prompt(self, prompt: str):
        """DashUI 채팅창에서 프롬프트가 전송되면 호출됩니다."""
        if not self.active_session:
            self.view_dash.show_toast("⚠ 먼저 커널 부팅 시퀀스를 시작하세요.")
            return

        if self._chat_runner and self._chat_runner.isRunning():
            self.view_dash.show_toast("⏳ 이전 채팅 추론이 진행 중입니다.")
            return

        # 세션 모델명 동기화
        self.active_session.boot_config.model_name = self.view_dash.get_active_model()
        self.active_session.judge_key = self.view_dash.api_key_input.text().strip()

        # AI 말풍선 미리 생성 (스트리밍 청크가 여기에 쌓임)
        self.view_dash.chat_panel.set_waiting(True, "⏳ AI 추론 중…")
        self.view_dash.chat_panel.append_ai_message("")   # 빈 버블 생성

        self._chat_runner = ChatBenchmarkEngine(
            prompt=prompt,
            session=self.active_session,
            engine_core=self.engine,
            db=self.db,
        )
        self._chat_runner.token_signal.connect(self.view_dash.update_token_count)
        self._chat_runner.sys_log_signal.connect(self.view_dash.log_sys)
        self._chat_runner.chunk_signal.connect(self.view_dash.chat_panel.append_ai_chunk)
        self._chat_runner.done_signal.connect(self.handle_chat_done)
        self._chat_runner.error_signal.connect(self._on_chat_error)
        self._chat_runner.start()

    def handle_chat_done(self, result: dict, response_text: str):
        self.view_dash.chat_panel.set_waiting(False)
        tps = result.get("Generation (t/s)", 0)
        ttft = result.get("TTFT (ms)", 0)
        self.view_dash.log_bench(
            f"💬 [CHAT_MOD]  TTFT: {ttft}ms  |  {tps} t/s  |  CSV 저장 완료"
        )
        self.view_dash.show_toast(f"✅ 채팅 벤치마크 완료 – {tps} t/s")

    def _on_chat_error(self, msg: str):
        self.view_dash.chat_panel.set_waiting(False)
        self.view_dash.chat_panel.append_ai_message(f"❌ 오류: {msg}")
        self.view_dash.show_toast(f"❌ 채팅 추론 오류: {msg[:60]}")

    # ──────────────────────────────────────────────────────────────────────
    # Shutdown
    # ──────────────────────────────────────────────────────────────────────

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

        # 채팅 러너도 정리
        if self._chat_runner and self._chat_runner.isRunning():
            self._chat_runner.requestInterruption()
            self._chat_runner.wait(1000)

        self.engine.shutdown()
        self.active_session = None
        self.active_runner  = None
        self._boot_thread   = None
        self._chat_runner   = None
        self.view_dash.btn_run.setEnabled(True)
        self.view_dash.btn_chat.setEnabled(True)
        self.view_dash.clear_logs()
        self.stack.setCurrentIndex(0)
        self.view_dash.show_toast("커널 닫기, 마운트 해제, 접속 해제가 완료되었습니다.")

    def show_harness_manager(self):
        dialog = HarnessManagerUI(self)
        dialog.exec()

    def _load_harness_data(self):
        fname = "harness_v4.csv"
        data  = []
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