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

from ui.qt_bridge import *
from core.constants import OLLAMA_BASE_URL, LLAMA_CPP_HOST, LLAMA_CPP_PORT
from core.judge_service import JudgeService

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
from core.service_monitor import ServiceMonitorThread
from ui.status_bar import AMEVAStatusBar


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
        self._last_booted_model = "" # 엔진 스왑 감지용
        self._dl_workers    = {} # 백그라운드 다운로드 일꾼 저장소

        # ── 내비게이션 스택 ───────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.view_wizard = WizardUI(self)
        self.view_dash   = DashUI(self)

        self.stack.addWidget(self.view_wizard)   # 0
        self.stack.addWidget(self.view_dash)     # 1

        # ── 상태 표시줄 (Status Bar) ─────────────────────────────────────
        self.ameva_status = AMEVAStatusBar(self)
        self.setStatusBar(self.ameva_status)

        # ── 서비스 모니터링 시작 ──────────────────────────────────────────
        self._monitor = ServiceMonitorThread()
        self._monitor.status_updated.connect(self.ameva_status.update_service_status)
        self.ameva_status.service_request.connect(self._handle_service_request)
        self._monitor.start()

        # ── 시그널 연결 ───────────────────────────────────────────────────
        self.view_dash.run_benchmark_signal.connect(self.handle_run_request)
        self.view_dash.chaos_monkey_signal.connect(self.engine.inject_chaos)
        self.view_dash.shutdown_signal.connect(self.handle_shutdown)
        self.view_dash.chat_panel.chat_submitted.connect(self.handle_chat_prompt)
        self.view_dash.chat_panel.chat_interrupted.connect(self._on_chat_interrupted)
        self.view_dash.model_changed_signal.connect(self._handle_immediate_swap)
        self.view_wizard.start_signal.connect(self._open_gallery_from_wizard)
        
        # 모델 갤러리와의 연동 (백그라운드 다운로드 신호)
        # DashUI나 WizardUI에서 갤러리를 열 때 컨트롤러와 연결되도록 처리 필요

    def _on_chat_interrupted(self):
        if self._chat_runner and self._chat_runner.isRunning():
            self._chat_runner.requestInterruption()
            self.view_dash.log_bench("🛑 채팅 벤치마크 중단 요청됨.")
            self.view_dash.show_toast("채팅 중단됨.")

    def _handle_service_request(self, name: str):
        success, msg = self._monitor.attempt_start(name)
        if success:
            self.view_dash.show_toast(f"ℹ️ {msg}")
        else:
            QMessageBox.warning(self, "Service Error", msg)

    # ──────────────────────────────────────────────────────────────────────
    # Theme
    # ──────────────────────────────────────────────────────────────────────

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.setStyleSheet(PremiumStyle.get_qss(self.is_dark_mode))
        self.view_dash.apply_theme_to_graphs(self.is_dark_mode)

    # ──────────────────────────────────────────────────────────────────────
    # Boot Sequence
    def _open_gallery_from_wizard(self):
        """[Scenario Step 2] 메인에서 부팅 시 모델 갤러리를 먼저 오픈"""
        session = self.view_wizard.get_session_config()
        self.active_session = session 
        self.view_dash._open_model_gallery(preferred_engine=session.boot_config.engine)

    def _handle_immediate_swap(self, name: str, engine_type: str):
        """갤러리에서 모델 선택 시 즉각 반응 (최초 부팅 포함)"""
        # 엔진이 꺼져 있거나(최초/초기화 상태) 모델이 바뀌었을 때
        if not self.engine.container or self._last_booted_model != name:
            self.view_dash.log_sys(f"📢 엔진 가동/스왑 요청됨: {name}")
            if not self.active_session:
                self.active_session = self.view_wizard.get_session_config()
            
            # 모델명 주입 후 부팅
            self.active_session.boot_config.model_name = name
            self.execute_boot_sequence(self.active_session)

    # ──────────────────────────────────────────────────────────────────────

    def execute_boot_sequence(self, session: BenchmarkSession):
        self.active_session = session

        # 기본 모델명을 세션에 주입
        self.active_session.boot_config.model_name = (
            self.view_dash.get_active_model()
        )

        self.view_dash.clear_logs()
        self.view_dash.chat_panel.clear_chat() # 채팅 초기화
        self.stack.setCurrentIndex(1)
        self.view_dash.focus_log_tab()

        self._boot_thread = BootThread(
            config={
                "engine":    session.boot_config.engine,
                "cpu_cores": session.boot_config.cpu_cores,
                "ram_mb":    session.boot_config.ram_mb,
                "gpu_layers": session.boot_config.gpu_layers,
                "model_name": session.boot_config.model_name # 누락된 필드 추가
            },
            engine=self.engine
        )
        self._boot_thread.log_signal.connect(self.view_dash.log_sys)
        self._boot_thread.done_signal.connect(self._on_boot_done)
        self._boot_thread.start()

    def _on_boot_done(self, success: bool, msg: str):
        if success:
            # 마지막으로 성공적으로 부팅된 모델명 기록
            self._last_booted_model = self.active_session.boot_config.model_name
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

        # 모델명 및 엔진 동기화 (레이블 기반)
        model_name = self.view_dash.get_active_model()
        if not model_name:
            self.view_dash.show_toast("🚨 실행 전 모델을 먼저 선택해주세요!")
            self.view_dash._open_model_gallery()
            return

        self.active_session.boot_config.model_name = model_name
        self.active_session.boot_config.engine     = self.view_dash.get_active_engine()
        self.active_session.run_mode               = self.view_dash.mode_combo.currentText()
        self.active_session.judge_key              = self.view_dash.api_key_input.text().strip()

        # [Smart SWAP] 엔진/모델 변경 시 자동 재부팅
        if self._last_booted_model != model_name:
            self.view_dash.log_sys(f"🔄 스왑 필요: {self._last_booted_model} -> {model_name}")
            self.execute_boot_sequence(self.active_session)
            self.view_dash.show_toast("엔진 모델을 교체 중입니다. 완료 후 다시 RUN을 눌러주세요.")
            return

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
        self.active_runner.sys_log_signal.connect(self.view_dash.log_sys)
        self.active_runner.token_signal.connect(self.view_dash.update_token_count)
        self.active_runner.chunk_signal.connect(self.view_dash.append_stream)
        self.active_runner.report_signal.connect(self.handle_report_generation)
        
        # 스트리밍 창 초기화
        self.view_dash.clear_stream()
        self.active_runner.start()

    def handle_report_generation(self, results):
        self.db.insert_batch(results)
        self.view_dash.log_bench(
            f"\n📊 {len(results)}건 결과가 Edge_v5_Singularity_Report.csv 에 저장되었습니다."
        )
        
        # [Scenario Step 11] 시스템 완벽 초기화
        self._last_booted_model = None
        self.ameva_status.set_container_status("OFFLINE", "READY")
        self.view_dash.update_telemetry({"power": 0.0, "temp": 0.0, "ram": 0.0})
        self.view_dash.set_active_model("미선택", "OFFLINE") # 라벨 초기화
        
        self.view_dash.btn_run.setEnabled(True)
        self.view_dash.btn_chat.setEnabled(True)
        self.view_dash.show_toast("벤치마크 완료 및 엔진 종료. 다시 시작하려면 모델을 선택하세요.")

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

        # 세션 모델명 및 엔진 동기화
        model_name = self.view_dash.get_active_model()
        if not model_name:
            self.view_dash.show_toast("🚨 채팅 전 모델을 먼저 선택해주세요!")
            self.view_dash._open_model_gallery()
            return

        self.active_session.boot_config.model_name = model_name
        self.active_session.boot_config.engine     = self.view_dash.get_active_engine()
        self.active_session.judge_key = self.view_dash.api_key_input.text().strip()

        # [Smart SWAP] 채팅 중에도 모델 변경 시 재부팅
        if self._last_booted_model != model_name:
            self.view_dash.log_sys(f"🔄 스왑 필요: {self._last_booted_model} -> {model_name}")
            self.execute_boot_sequence(self.active_session)
            self.view_dash.show_toast("엔진 교체 중... 대시보드를 다시 로딩합니다.")
            return

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
        self._chat_runner.chunk_signal.connect(self.view_dash.append_stream)
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
        """[Scenario Step 15] 메인으로 돌아갈 때 엔진 완전 종료 및 자원 반납"""
        if self.active_runner and self.active_runner.isRunning():
            answer = QMessageBox.question(
                self, "작업 취소 확인",
                "벤치마크가 진행중입니다.\n중단하고 메인으로 돌아가시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes: return
            self.active_runner.requestInterruption()
            self.active_runner.wait(1000)

        elif self._boot_thread and self._boot_thread.isRunning():
            answer = QMessageBox.question(
                self, "부팅 취소 확인",
                "엔진 부팅 중입니다.\n중단하고 메인으로 돌아가시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes: return
            self._boot_thread.requestInterruption()
            self._boot_thread.wait(1000)

        # 1. 모든 엔진 및 자원 완전 파괴 (Strict Reset)
        if self._chat_runner and self._chat_runner.isRunning():
            self._chat_runner.requestInterruption()
            self._chat_runner.wait(1000)

        self.view_dash.log_sys("📢 시스템 리부트 시퀀스: 자원 완전 반납 중...")
        self.engine.shutdown()
        
        # 2. 모든 세션 변수 초기화 (태초의 상태)
        self.active_session = None
        self.active_runner  = None
        self._boot_thread   = None
        self._chat_runner   = None
        self._last_booted_model = None 
        
        # 3. UI 복구 및 초기화
        self.ameva_status.set_container_status("IDLE", "MAIN")
        self.view_dash.clear_logs()
        self.view_dash.btn_run.setEnabled(True)
        self.view_dash.btn_chat.setEnabled(True)
        
        # 4. 메인 화면으로 전환
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

    # ──────────────────────────────────────────────────────────────────────
    # Background Download Manager
    # ──────────────────────────────────────────────────────────────────────

    def _handle_download_request(self, info: dict, is_ollama: bool = False):
        """모델 갤러리에서 날아온 다운로드 요청을 백그라운드에서 처리합니다."""
        from ui.model_gallery import ModelDownloadWorker, OllamaPullWorker, MODELS_DIR
        model_id = info["id"]
        
        if model_id in self._dl_workers:
            return # 이미 진행 중
            
        if is_ollama:
            worker = OllamaPullWorker(info)
            worker.progress_signal.connect(lambda mid, pct: self._on_dl_progress(mid, pct))
        else:
            worker = ModelDownloadWorker(info, MODELS_DIR)
            worker.progress_signal.connect(lambda pct, mid=model_id: self._on_dl_progress(mid, pct))
            
        worker.done_signal.connect(self._on_dl_done)
        self._dl_workers[model_id] = worker
        worker.start()
        
        self.ameva_status.set_download_progress(model_id, 0)
        self.view_dash.log_sys(f"🚀 {model_id} 백그라운드 다운로드 시작...")

    def _on_dl_progress(self, model_id: str, pct: int):
        # 상태바 갱신
        self.ameva_status.set_download_progress(model_id, pct)
        
        # 현재 열려있는 갤러리 창이 있다면 진행도 전파 (UI 싱크)
        # 갤러리는 이벤트를 직접 받지 않고, main.py가 관리하는 _dl_workers를 참조하여 업데이트함

    def _on_dl_done(self, success: bool, model_id: str):
        # 즉시 삭제하지 않고 잠시 후 삭제하여 QThread 메모리 이슈 방지
        # self._dl_workers.pop(model_id, None)
        
        active_count = len([w for w in self._dl_workers.values() if w.isRunning()])
        self.ameva_status.set_download_progress(model_id, 100, is_done=(active_count <= 0))
        
        status = "완료" if success else "실패"
        self.view_dash.log_sys(f"📢 {model_id} 다운로드 {status}")
        self.view_dash.show_toast(f"✅ 모델 {model_id} 설치가 {status}되었습니다.")
        
        # 5초 뒤에 명단에서 제거 (안전 지연)
        QTimer.singleShot(5000, lambda: self._dl_workers.pop(model_id, None))
        
        # 갤러리가 열려있다면 갱신 요청
        # (갤러리는 닫혔다 열릴 때 상태를 강제 갱신하므로 UI 싱크에 유리)
    def closeEvent(self, event):
        """창이 닫힐 때 도커 엔진 및 모든 쓰레드를 정리합니다."""
        print("[AMEVA] 종료 시그널 감지. 엔진 정리 중...")
        try:
            self.engine.shutdown()
        except: pass
        for mid, worker in self._dl_workers.items():
            if worker.isRunning():
                worker.requestInterruption()
                worker.wait(500)
        event.accept()

if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    controller = AMEVAController()
    controller.show()

    sys.exit(app.exec())