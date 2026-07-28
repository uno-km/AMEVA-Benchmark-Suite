import json
import os
from core.matrix_engine import MatrixEngine
from models.settings import BenchmarkSession, BootstrapConfig, StressOptions
from backend.database import db_init

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config.json"))

class AppState:
    def __init__(self):
        # 1. DB 초기화
        db_init()
        
        # 2. 기본 설정 로드
        self.config_data = {
            "vault_dir": "D:/ameva/models/llm",
            "bit_vault_dir": "D:/ameva/models/bitnet",
            "default_judge_model": "exaone3.5:7.8b",
            "last_used_engine": "OLM",
            "last_used_cores": 2.0,
            "last_used_ram": 4096,
            "last_used_gpu_layers": 0
        }
        self.load_config()
        
        self.engine = MatrixEngine()
        
        self.boot_config = BootstrapConfig(
            engine=self.config_data["last_used_engine"],
            cpu_cores=self.config_data["last_used_cores"],
            ram_mb=self.config_data["last_used_ram"],
            gpu_layers=self.config_data["last_used_gpu_layers"]
        )
        self.stress_config = StressOptions(
            judge_model=self.config_data["default_judge_model"]
        )
        self.session = BenchmarkSession(boot_config=self.boot_config, stress_config=self.stress_config)
        
        self.last_booted_model = ""
        self.boot_status = "OFFLINE"  # OFFLINE, BOOTING, ONLINE, ERROR
        self.boot_message = "READY"
        
        self.active_benchmark_running = False
        self.active_chat_running = False

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.config_data.update(loaded)
            except Exception as e:
                print(f"[AppState Warning] config.json 로드 중 실패: {e}")

    def save_config(self, updates: dict = None):
        if updates:
            self.config_data.update(updates)
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[AppState Warning] config.json 저장 실패: {e}")

state = AppState()

