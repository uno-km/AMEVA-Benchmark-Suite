from core.matrix_engine import MatrixEngine
from models.settings import BenchmarkSession, BootstrapConfig, StressOptions
from models.report_db import ReportManager

# 글로벌 상태 관리자
class AppState:
    def __init__(self):
        self.engine = MatrixEngine()
        self.db = ReportManager()
        
        self.boot_config = BootstrapConfig()
        self.stress_config = StressOptions()
        self.session = BenchmarkSession(boot_config=self.boot_config, stress_config=self.stress_config)
        
        self.last_booted_model = ""
        self.boot_status = "OFFLINE"  # OFFLINE, BOOTING, ONLINE, ERROR
        self.boot_message = "READY"
        
        self.active_benchmark_running = False
        self.active_chat_running = False

state = AppState()
