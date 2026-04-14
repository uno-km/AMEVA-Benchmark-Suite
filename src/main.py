import sys, os, csv
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox
from core.docker_engine import MatrixEngine
from core.benchmark import SystemMonitor, BenchmarkRunner
from ui.wizard_ui import WizardUI
from ui.dash_ui import DashUI
from ui.harness_ui import HarnessManagerUI # 추가

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
        self.harness_mgr = HarnessManagerUI(self) # ✅ 관리 화면 생성
        
        self.stack.addWidget(self.wizard)      # Index 0
        self.stack.addWidget(self.dash)        # Index 1
        self.stack.addWidget(self.harness_mgr) # ✅ Index 2로 추가


    # [추가] 하네스 관리 화면으로 이동하는 함수
    def show_harness_manager(self):
        self.harness_mgr.load_data() # 열 때마다 최신 CSV 로드
        self.stack.setCurrentIndex(2)
        
    def execute_boot(self, config):
        self.wizard.boot_btn.setEnabled(False)
        self.wizard.boot_btn.setText("커널 접속 중...")
        QApplication.processEvents()

        self.current_engine_type = config.get("engine", "OLM")
        success, msg = self.engine.boot_matrix(config)
        if success:
            # ✅ 대시보드 UI에 현재 엔진 상태를 전송!
            self.dash.set_engine_info(self.current_engine_type)
            
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
        self.runner = BenchmarkRunner(model_name, custom_dataset, judge_key, self.current_engine_type)
        self.runner.current_blackout_state = False
        self.runner.log_signal.connect(self.dash.log)
        self.runner.report_signal.connect(self._save_report)
        self.runner.start()

    def _save_report(self, results):
        fname = "Edge_v4_Singularity_Report.csv"
        
        # ✅ [수정] res["Engine"]과 res["Model"]을 기록하려면 fields에도 이름이 있어야 합니다!
        fields = [
            "Timestamp", "Engine", "Model", "Task", "Judge_Result", 
            "TTFT(s)", "Total_Time(s)", "TPS", "Tokens_Sent", "Tokens_Gen", 
            "Blackout_During_Test", "Full_Response"
        ]
        
        file_exists = os.path.isfile(fname)
        
        try:
            # ✅ 'a' (Append) 모드로 파일 열기
            with open(fname, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                
                # ✅ [수정] 파일이 아예 없을 때 '딱 한 번만' 헤더를 작성합니다.
                if not file_exists:
                    writer.writeheader()
                
                # ✅ [수정] 중복되던 writer.writeheader() 삭제 완료!

                for res in results:
                    # ✅ 데이터 매핑 (benchmark.py에서 보낸 데이터에 추가 정보 삽입)
                    res["Engine"] = self.current_engine_type
                    res["Model"] = self.dash.model_combo.currentText()
                    
                    # ✅ 이제 fields에 Engine과 Model이 있으므로 에러 없이 기록됩니다.
                    writer.writerow(res)
                    
            self.dash.log(f"\n 📑 [확장 리포트] 누적 기록 완료: {os.path.abspath(fname)}")
            
        except Exception as e: 
            self.dash.log(f" ❌ 리포트 저장 실패: {str(e)}")
            print(f"DEBUG ERROR: {e}") # 터미널에서도 확인 가능하게
            
        # UI 버튼 복구
        self.dash.btn_run.setEnabled(True)

    

    
def init_harness_csv():
        fname = "harness_v4.csv"
        if os.path.exists(fname): return # 이미 있으면 스킵
        
        harness_data = [
            {"task": "K-Math", "prompt": "영희는 사과 12개, 철수는 영희의 절반보다 2개 더 많고, 민수는 철수보다 3개 적어. 총 합계는?", "expected_regex": r"23", "eval_type": "regex"},
            {"task": "K-Grammar", "prompt": "'나 어제 밥 먹다가 이빨 빠졌어'를 비즈니스 극존칭으로 바꿔.", "expected_regex": "", "eval_type": "llm_judge"},
            {"task": "K-Coding", "prompt": "리스트에서 짝수만 골라 제곱 후 내림차순 정렬하는 파이썬 함수를 짜줘.", "expected_regex": "", "eval_type": "llm_judge"},
            {"task": "K-Hallucination", "prompt": "세종대왕의 맥북 던짐 사건에 대해 자세히 설명해줘.", "expected_regex": r"(없습니다|사실이|허구|데이터가)", "eval_type": "regex"},
            {"task": "E-Math", "prompt": "150 dollars with 20% discount and then 10% tax added. Final price?", "expected_regex": r"132", "eval_type": "regex"},
            {"task": "E-Formal", "prompt": "Rewrite 'I can't make it to the meeting' into a formal business email.", "expected_regex": "", "eval_type": "llm_judge"},
            {"task": "E-Logic", "prompt": "I have 3 brothers. Each has one sister. How many sisters do I have?", "expected_regex": r"(1|one)", "eval_type": "regex"},
            {"task": "K-E-Mixed", "prompt": "'The deadline has been moved up to tomorrow'를 한글로 번역하고, 기한이 '당겨졌는지' 혹은 '미뤄졌는지' 판단해서 한글로 답한 뒤, 마감일을 뜻하는 영어 단어를 써줘.", "expected_regex": "", "eval_type": "llm_judge"}
        ]
        
        with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=["task", "prompt", "expected_regex", "eval_type"])
            writer.writeheader()
            writer.writerows(harness_data)
        print(f"✅ {fname} 초기화 완료!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainController()
    init_harness_csv()
    w.show()
    sys.exit(app.exec())