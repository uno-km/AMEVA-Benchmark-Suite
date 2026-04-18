import os
import csv
import datetime
from typing import List, Dict, Any

class ReportManager:
    """[V5.5] CSV Database Manager - Handles reporting as a structured database."""
    
    SCHEMA = [
        "Timestamp", "Model_Hash", "Quant_Method", "Context_Size", "Thread_Config", 
        "Prompt_Text", "Prompt_Response",
        "TTFT (ms)", "Prompt_Eval (ms/t)", "Avg_GPU_W", "Tokens_per_Joule", 
        "E2E_Latency", "Generation (t/s)", "Peak_VRAM_MB", "System_Load", 
        "Warm/Cold_Tag", "Sampling_Time (ms)", "Judge_Score", "Judge_Reason", "Metric_Source (bench/srv)"
    ]

    def __init__(self, db_path: str = "Edge_v5_Singularity_Report.csv"):
        self.db_path = db_path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.db_path):
            with open(self.db_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.SCHEMA)
                writer.writeheader()
        else:
            with open(self.db_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                existing_rows = list(reader)
                existing_headers = reader.fieldnames or []

            if existing_headers != self.SCHEMA:
                with open(self.db_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=self.SCHEMA)
                    writer.writeheader()
                    for row in existing_rows:
                        merged = {k: row.get(k, 'N/A') for k in self.SCHEMA}
                        writer.writerow(merged)

    def insert_entry(self, data: Dict[str, Any]):
        """Inserts a new benchmark entry into the 'database'."""
        # Ensure timestamp if missing
        if "Timestamp" not in data or not data["Timestamp"]:
            data["Timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        # Filter and validate data based on schema
        entry = {k: data.get(k, "N/A") for k in self.SCHEMA}
        
        with open(self.db_path, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.SCHEMA)
            writer.writerow(entry)

    def insert_batch(self, batch: List[Dict[str, Any]]):
        """Inserts multiple entries."""
        for entry in batch:
            self.insert_entry(entry)

    def get_last_n(self, n: int = 10) -> List[Dict[str, Any]]:
        """Retrieves the last N entries from the database."""
        results = []
        if not os.path.exists(self.db_path):
            return results
        
        with open(self.db_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            data = list(reader)
            results = data[-n:]
        return results

    def get_all(self) -> List[Dict[str, Any]]:
        """Retrieves all entries."""
        if not os.path.exists(self.db_path):
            return []
        with open(self.db_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            return list(reader)
