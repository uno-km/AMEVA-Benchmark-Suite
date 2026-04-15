import psutil
import os, csv, datetime, subprocess
import subprocess
try:
    import GPUtil
except ImportError:
    GPUtil = None
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class HardwareSpecs:
    cpu_count: int
    ram_total_gb: float
    gpu_name: Optional[str] = None
    has_nvidia: bool = False 

class HardwareService:
    @staticmethod
    def detect_capabilities() -> HardwareSpecs:
        """현재 시스템의 하드웨어 성능을 감지합니다."""
        cpu_count = psutil.cpu_count(logical=True)
        ram_total = round(psutil.virtual_memory().total / (1024**3), 2)
        
        gpu_name = None
        has_nvidia = False
        
        try:
            # 존재 여부 확인을 위해 subprocess를 먼저 시도 (가장 신뢰성 높음)
            res = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], 
                                 capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            gpu_name = res.stdout.strip().split('\n')[0]
            has_nvidia = True
        except (subprocess.CalledProcessError, FileNotFoundError, Exception):
            # 사용 가능할 경우 GPUtil로 폴백(fallback) 시도
            if GPUtil:
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu_name = gpus[0].name
                        has_nvidia = True
                except:
                    pass
            
        return HardwareSpecs(
            cpu_count=cpu_count,
            ram_total_gb=ram_total,
            gpu_name=gpu_name,
            has_nvidia=has_nvidia
        )

@dataclass
class ReportManager:
    """[V5.5] CSV 데이터베이스 매니저 - 리포팅을 구조화된 데이터베이스처럼 관리합니다."""
    
    SCHEMA = [
        "Timestamp", "Model_Hash", "Quant_Method", "Context_Size", "Thread_Config", 
        "TTFT (ms)", "Prompt_Eval (ms/t)", "Avg_GPU_W", "Tokens_per_Joule", 
        "E2E_Latency", "Generation (t/s)", "Peak_VRAM_MB", "System_Load", 
        "Warm/Cold_Tag", "Sampling_Time (ms)", "Judge_Score", "Metric_Source (bench/srv)"
    ]

    def __init__(self, db_path: str = "Edge_v5_Singularity_Report.csv"):
        self.db_path = db_path
        self._ensure_file()

    def _ensure_file(self):
        """리포트 파일이 존재하는지 확인하고 없으면 헤더와 함께 생성합니다."""
        if not os.path.exists(self.db_path):
            with open(self.db_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.SCHEMA)
                writer.writeheader()

    def insert_entry(self, data: Dict[str, Any]):
        """새로운 벤치마크 항목을 '데이터베이스'에 삽입합니다."""
        # 타임스탬프가 없는 경우 추가
        if "Timestamp" not in data or not data["Timestamp"]:
            data["Timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        # 스키마에 기반하여 데이터 필터링 및 검증
        entry = {k: data.get(k, "N/A") for k in self.SCHEMA}
        
        with open(self.db_path, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.SCHEMA)
            writer.writerow(entry)

    def insert_batch(self, batch: List[Dict[str, Any]]):
        """여러 항목을 한 번에 삽입합니다."""
        for entry in batch:
            self.insert_entry(entry)

    def get_last_n(self, n: int = 10) -> List[Dict[str, Any]]:
        """데이터베이스에서 마지막 N개의 항목을 가져옵니다."""
        results = []
        if not os.path.exists(self.db_path):
            return results
        
        with open(self.db_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            data = list(reader)
            results = data[-n:]
        return results

    def get_all(self) -> List[Dict[str, Any]]:
        """모든 항목을 가져옵니다."""
        if not os.path.exists(self.db_path):
            return []
        with open(self.db_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            return list(reader)
