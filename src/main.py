import sys, os, csv
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

class AMEVAController(QMainWindow):
    """[V5.5] 메인 컨트롤러 (MVC) - 벤치마크 슈트 전체를 조율합니다."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMEVA EDGE MATRIX v5.5 [집약체]")
        self.setGeometry(100, 100, 1280, 900)
        
        # 프리미엄 테마 적용
        self.setStyleSheet(PremiumStyle.MAIN_QSS)

        # 1. 구성 요소 초기화
        self.hardware = HardwareService.detect_capabilities()
        self.db = ReportManager()
        self.engine = MatrixEngine()
        self.active_session = None
        self.active_runner = None

        # 2. 내비게이션 스택 설정
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.view_wizard = WizardUI(self)
        self.view_dash = DashUI(self)
        self.view_harness = HarnessManagerUI(self)

        self.stack.addWidget(self.view_wizard)  # 인덱스 0
        self.stack.addWidget(self.view_dash)    # 인덱스 1
        self.stack.addWidget(self.view_harness) # 인덱스 2

        # 3. 시그널 연결 (SRP 흐름)
        self.view_dash.run_benchmark_signal.connect(self.handle_run_request)
        self.view_dash.chaos_monkey_signal.connect(self.engine.inject_chaos)
        self.view_dash.shutdown_signal.connect(self.handle_shutdown)

    def execute_boot_sequence(self, session: BenchmarkSession):
        """위저드에서 대시보드로 전환하며 도커 부팅을 실행합니다."""
        self.active_session = session
        
        # UI 전환
        self.view_dash.log_sys("🚀 매트릭스 커널 초기화 중...")
        self.stack.setCurrentIndex(1)
        
        # 엔진 부팅
        self.engine.set_logger(self.view_dash.log_sys)
        success, msg = self.engine.boot_matrix({
            "engine": session.boot_config.engine,
            "cpu_cores": session.boot_config.cpu_cores,
            "ram_mb": session.boot_config.ram_mb,
            "gpu_layers": session.boot_config.gpu_layers
        })

        if success:
            self.view_dash.update_engine_status(msg)
            self.view_dash.log_sys("✅ 커널 온라인. 명령 대기 중.")
        else:
            QMessageBox.critical(self, "커널 패닉", f"부팅 실패: {msg}")
            self.stack.setCurrentIndex(0)

    def handle_run_request(self):
        """대시보드에서 '런 태스크'가 클릭되었을 때 트리거됩니다."""
        if not self.active_session: return
        
        # UI에서 선택된 현재 상태로 세션 업데이트
        self.active_session.boot_config.model_name = self.view_dash.model_combo.currentText()
        self.active_session.run_mode = self.view_dash.mode_combo.currentText()
        self.active_session.judge_key = self.view_dash.api_key_input.text().strip()

        # 하네스 데이터 로드 (DB 스타일)
        harness = self._load_harness_data()
        
        self.view_dash.btn_run.setEnabled(False)
        self.active_runner = ExecutionEngine(self.active_session, harness, self.engine)
        self.active_runner.log_signal.connect(self.view_dash.log_bench)
        self.active_runner.report_signal.connect(self.handle_report_generation)
        self.active_runner.start()

    def handle_report_generation(self, results):
        """테스트를 마무리하고 CSV DB에 기록합니다."""
        self.db.insert_batch(results)
        self.view_dash.log_bench(f"\n📊 데이터가 Edge_v5_Singularity_Report.csv 에 영구 보존되었습니다.")
        self.view_dash.btn_run.setEnabled(True)

    def handle_shutdown(self):
        """매트릭스를 파괴하고 위저드 화면으로 복귀합니다."""
        self.engine.shutdown()
        self.active_session = None
        self.stack.setCurrentIndex(0)

    def show_harness_manager(self):
        self.stack.setCurrentIndex(2)

    def _load_harness_data(self):
        # 데이터셋 로딩 구현 (추후 모델로 이동 가능)
        fname = "harness_v4.csv"
        data = []
        if os.path.exists(fname):
            with open(fname, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                data = list(reader)
        return data

if __name__ == "__main__":
    # 고해상도 DPI 스케일링 설정
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    controller = AMEVAController()
    controller.show()
    
    sys.exit(app.exec())