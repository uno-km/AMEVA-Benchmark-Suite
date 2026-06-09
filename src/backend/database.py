import os
import csv
import sqlite3
import datetime
from typing import List, Dict, Any

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ameva_benchmark.db"))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 외래키 활성화
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def db_init():
    """데이터베이스 테이블 생성 및 최초 마이그레이션 실행"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 모델 레지스트리 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS model_registry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        category TEXT NOT NULL,
        tag TEXT,
        description TEXT,
        min_ram_gb REAL DEFAULT 2.0,
        size_gb REAL DEFAULT 0.0,
        filename TEXT,
        ollama_tag TEXT,
        hf_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. 하네스 태스크 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS harness_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT UNIQUE NOT NULL,
        prompt TEXT NOT NULL,
        expected_regex TEXT,
        eval_type TEXT NOT NULL DEFAULT 'llm_judge',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 3. 벤치마크 런 테이블 (공통 정보)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS benchmark_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        model_name TEXT NOT NULL,
        engine_type TEXT NOT NULL,
        run_mode TEXT NOT NULL,
        cpu_cores REAL,
        ram_mb INTEGER,
        gpu_layers INTEGER,
        threads INTEGER,
        n_ctx INTEGER,
        temperature REAL,
        repeat_penalty REAL,
        system_prompt TEXT,
        judge_model TEXT
    );
    """)
    
    # 4. 벤치마크 개별 결과 테이블 (태스크별 결과)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS benchmark_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        task_name TEXT NOT NULL,
        category TEXT NOT NULL,
        prompt_text TEXT,
        response_text TEXT,
        ttft_ms REAL,
        prompt_eval_ms_t REAL,
        avg_gpu_w REAL,
        tokens_per_joule REAL,
        e2e_latency_sec REAL,
        tps REAL,
        peak_vram_mb REAL,
        system_load TEXT,
        warm_cold_tag TEXT,
        sampling_time_ms REAL,
        judge_score TEXT,
        judge_reason TEXT,
        FOREIGN KEY (run_id) REFERENCES benchmark_runs(id) ON DELETE CASCADE
    );
    """)
    
    conn.commit()
    
    # ── 마이그레이션 수행 ──
    seed_model_registry(conn)
    migrate_csv_data(conn)
    conn.close()

SEED_MODEL_CATALOGUE = [
    {
        "id":          "qwen2.5-1.5b",
        "display":     "Qwen2.5-1.5B-Instruct",
        "category":    "Lite",
        "tag":         "⚡ 밸런스 · 한국어 명령",
        "desc":        "범용 소형 모델. 한국어 지시문 이해 우수. 노트북CPU에서도 빠름.",
        "min_ram_gb":  2.0,
        "size_gb":     1.0,
        "filename":    "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "hf_url":      "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "ollama_tag":  "qwen2.5:1.5b",
    },
    {
        "id":          "llama-3.2-1b",
        "display":     "Llama-3.2-1B-Instruct",
        "category":    "Lite",
        "tag":         "🪶 초경량 · JSON 포맷팅",
        "desc":        "가장 작은 모델. JSON 출력·구조화 태스크에 최적. RAM 2GB 이하 OK.",
        "min_ram_gb":  2.0,
        "size_gb":     0.7,
        "filename":    "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "ollama_tag":  "llama3.2:1b",
    },
    {
        "id":          "deepseek-r1-1.5b",
        "display":     "DeepSeek-R1-Distill-Qwen-1.5B",
        "category":    "Lite",
        "tag":         "🧠 논리 추론 · 경로 판단",
        "desc":        "추론 특화 증류 모델. 수학·논리·단계적 사고 강점. 1.5B 대비 성능 이상.",
        "min_ram_gb":  2.0,
        "size_gb":     1.0,
        "filename":    "DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
        "ollama_tag":  "deepseek-r1:1.5b",
    },
    {
        "id":          "gemma-2-2b",
        "display":     "Gemma-2-2B-It",
        "category":    "Lite",
        "tag":         "🏷️ 분류 · 객관식 판단",
        "desc":        "Google DeepMind 2B 모델. 분류·선택형 판단 우수. 효율 대비 품질 높음.",
        "min_ram_gb":  3.0,
        "size_gb":     1.6,
        "filename":    "gemma-2-2b-it-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "ollama_tag":  "gemma2:2b",
    },
    {
        "id":          "qwen2.5-3b",
        "display":     "Qwen2.5-3B-Instruct",
        "category":    "Medium",
        "tag":         "💻 코딩 · 로직 분석",
        "desc":        "코딩·로직 분석 3B 최강. 파이썬/JS 함수 작성, 알고리즘 추론 탁월.",
        "min_ram_gb":  4.0,
        "size_gb":     2.0,
        "filename":    "qwen2.5-3b-instruct-q4_k_m.gguf",
        "hf_url":      "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        "ollama_tag":  "qwen2.5:3b",
    },
    {
        "id":          "llama-3.2-3b",
        "display":     "Llama-3.2-3B-Instruct",
        "category":    "Medium",
        "tag":         "🔗 논리 추론 · 맥락 유지",
        "desc":        "Meta 3B. 긴 문맥 유지·대화 흐름 일관성 우수. 범용 중형 추천.",
        "min_ram_gb":  4.0,
        "size_gb":     2.0,
        "filename":    "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "ollama_tag":  "llama3.2:3b",
    },
    {
        "id":          "exaone-7.8b",
        "display":     "EXAONE-3.5-7.8B-Instruct",
        "category":    "Heavy",
        "tag":         "🇰🇷 한국어 뉘앙스 · 최고 성능",
        "desc":        "LG AI Research 7.8B 한국어 최신 모델. 문맥·뉘앙스·존댓말 완벽 이해.",
        "min_ram_gb":  8.0,
        "size_gb":     4.8,
        "filename":    "EXAONE-3.5-7.8B-Instruct-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/EXAONE-3.0-7.8B-Instruct-GGUF/resolve/main/EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf",
        "ollama_tag":  "exaone3.5:7.8b",
    },
    {
        "id":          "kullm3-8b",
        "display":     "KULLM3-8B",
        "category":    "Heavy",
        "tag":         "🌐 Llama3 기반 한국어 패치",
        "desc":        "Korea Univ. Llama3 파인튜닝. 한국어 교육·상식·추론 특화. 8B급 안정성.",
        "min_ram_gb":  8.0,
        "size_gb":     4.9,
        "filename":    "KULLM3-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/KULLM3-GGUF/resolve/main/KULLM3-Q4_K_M.gguf",
        "ollama_tag":  "kullm3",
    },
    {
        "id":          "eeve-10.8b",
        "display":     "EEVE-Korean-10.8B",
        "category":    "Heavy",
        "tag":         "📚 어휘력 특화 · 대형 모델",
        "desc":        "Yanolja 10.8B 한국어 어휘력 특화. 문학·법률·의학 어휘 이해 최상위.",
        "min_ram_gb":  12.0,
        "size_gb":     6.6,
        "filename":    "EEVE-Korean-Instruct-10.8B-v1.0-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/EEVE-Korean-Instruct-10.8B-v1.0-GGUF/resolve/main/EEVE-Korean-Instruct-10.8B-v1.0-Q4_K_M.gguf",
        "ollama_tag":  "eeve-korean:10.8b",
    },
    {
        "id":          "bitnet-b1.58-3b",
        "display":     "BitNet-b1.58-3B",
        "category":    "Heavy",
        "tag":         "🟢 1-bit · 초저전력",
        "desc":        "Microsoft BitNet 1.58비트 모델. CPU에서 GPU급 속도 구현. 에너지 효율 극대화.",
        "min_ram_gb":  4.0,
        "size_gb":     2.1,
        "filename":    "bitnet_b1_58-3b-i1-matrix.gguf",
        "hf_url":      "https://huggingface.co/2121-ai/BitNet-b1.58-3B-GGUF/resolve/main/bitnet_b1_58-3b-i1-matrix.gguf",
        "ollama_tag":  "bitnet:3b",
    },
]

def seed_model_registry(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM model_registry;")
    if cursor.fetchone()[0] == 0:
        print("[Seed] 기존 MODEL_CATALOGUE 데이터를 model_registry DB에 주입하는 중...")
        try:
            for m in SEED_MODEL_CATALOGUE:
                cursor.execute("""
                INSERT OR IGNORE INTO model_registry (
                    model_id, display_name, category, tag, description, min_ram_gb, size_gb, filename, ollama_tag, hf_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    m["id"], m["display"], m["category"], m["tag"], m["desc"],
                    m["min_ram_gb"], m["size_gb"], m["filename"], m["ollama_tag"], m["hf_url"]
                ))
            conn.commit()
            print("[Seed] 시드 데이터 주입 성공.")
        except Exception as e:
            print(f"[Seed Warning] 시드 데이터 삽입 에러: {e}")



def safe_float(val):
    if not val:
        return 0.0
    val_str = str(val).strip().upper()
    if val_str in ("N/A", "NONE", "NULL", ""):
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0

def migrate_csv_data(conn):
    cursor = conn.cursor()
    
    # 1. 하네스 마이그레이션 (harness_v4.csv)
    cursor.execute("SELECT COUNT(*) FROM harness_tasks;")
    if cursor.fetchone()[0] == 0:
        csv_path = "harness_v4.csv"
        if os.path.exists(csv_path):
            print(f"[Migration] {csv_path} 데이터를 DB로 가져오는 중...")
            try:
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # 중복 방지
                        task_id = row.get("task", "")
                        if not task_id:
                            continue
                        cursor.execute("""
                        INSERT OR IGNORE INTO harness_tasks (task_id, prompt, expected_regex, eval_type)
                        VALUES (?, ?, ?, ?);
                        """, (task_id, row.get("prompt", ""), row.get("expected_regex", ""), row.get("eval_type", "llm_judge")))
                conn.commit()
                print("[Migration] 하네스 데이터 마이그레이션 성공.")
            except Exception as e:
                print(f"[Migration Warning] 하네스 마이그레이션 중 오류: {e}")
                
    # 2. 결과 리포트 마이그레이션 (Edge_v5_Singularity_Report.csv)
    cursor.execute("SELECT COUNT(*) FROM benchmark_runs;")
    if cursor.fetchone()[0] == 0:
        csv_path = "Edge_v5_Singularity_Report.csv"
        if os.path.exists(csv_path):
            print(f"[Migration] {csv_path} 데이터를 SQLite DB로 이전하는 중...")
            try:
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                
                # Timestamp와 Model_Hash를 기준으로 그룹화하여 하나의 Benchmark Run으로 간주
                runs_map = {}
                for r in rows:
                    ts = r.get("Timestamp", "")
                    model = r.get("Model_Hash", "")
                    if not ts or not model:
                        continue
                    key = (ts, model)
                    if key not in runs_map:
                        runs_map[key] = []
                    runs_map[key].append(r)
                
                for (ts, model), group in runs_map.items():
                    first = group[0]
                    
                    # 벤치마크 런 추가
                    # 스키마 및 옵션 파싱
                    try:
                        n_ctx = int(first.get("Context_Size", 2048))
                    except:
                        n_ctx = 2048
                    try:
                        threads = int(first.get("Thread_Config", 4))
                    except:
                        threads = 4
                        
                    cursor.execute("""
                    INSERT INTO benchmark_runs (
                        timestamp, model_name, engine_type, run_mode, cpu_cores, ram_mb, gpu_layers, 
                        threads, n_ctx, temperature, repeat_penalty, system_prompt, judge_model
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        ts, model, first.get("Metric_Source (bench/srv)", "srv").upper(), 
                        first.get("System_Load", "INFERENCE"), 
                        2.0, 4096, 0, threads, n_ctx, 0.1, 1.1, 
                        "You are a professional assistant.", first.get("Judge_Score", "exaone3.5:7.8b")
                    ))
                    
                    run_id = cursor.lastrowid
                    
                    # 개별 결과 추가
                    for item in group:
                        # 점수 형 변환 시도
                        score_raw = item.get("Judge_Score", "N/A")
                        
                        cursor.execute("""
                        INSERT INTO benchmark_results (
                            run_id, task_name, category, prompt_text, response_text, ttft_ms, 
                            prompt_eval_ms_t, avg_gpu_w, tokens_per_joule, e2e_latency_sec, tps, 
                            peak_vram_mb, system_load, warm_cold_tag, sampling_time_ms, judge_score, judge_reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, (
                            run_id, 
                            item.get("Benchmark_Category", "General"), 
                            item.get("Benchmark_Category", "General"),
                            item.get("Prompt_Text", ""),
                            item.get("Prompt_Response", ""),
                            safe_float(item.get("TTFT (ms)", 0.0)),
                            safe_float(item.get("Prompt_Eval (ms/t)", 0.0)),
                            safe_float(item.get("Avg_GPU_W", 0.0)),
                            safe_float(item.get("Tokens_per_Joule", 0.0)),
                            safe_float(item.get("E2E_Latency", 0.0)),
                            safe_float(item.get("Generation (t/s)", 0.0)),
                            safe_float(item.get("Peak_VRAM_MB", 0.0)),
                            item.get("System_Load", "INFERENCE"),
                            item.get("Warm/Cold_Tag", "WARM"),
                            safe_float(item.get("Sampling_Time (ms)", 0.0)),
                            score_raw,
                            item.get("Judge_Reason", "N/A")
                        ))
                conn.commit()
                print(f"[Migration] 결과 리포트 {len(runs_map)}건 마이그레이션 완료.")
            except Exception as e:
                print(f"[Migration Warning] 결과 마이그레이션 중 오류: {e}")

