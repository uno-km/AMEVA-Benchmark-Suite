import os
import csv
import time
import re
import json
import threading
import psutil
import subprocess
import requests
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from core.constants import OLLAMA_BASE_URL, LLAMA_CPP_HOST, LLAMA_CPP_PORT
from core.judge_service import JudgeService
from core.prompt_utils import PromptFactory, get_stop_tokens
from backend.state import state
from backend.routers.logs import broadcaster

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Harness Default & Schemas
# ─────────────────────────────────────────────────────────────────────────────

HARNESS_FILE = "harness_v4.csv"

DEFAULT_HARNESS = [
    {"task": "K-Math-Basic",        "prompt": "영희는 사과 12개, 철수는 영희의 절반보다 2개 더 많고, 민수는 철수보다 3개 적어. 총 합계는?",   "expected_regex": r"\b23\b",                              "eval_type": "regex"},
    {"task": "K-Logic-Intermediate","prompt": "A가 B보다 3살 많고, B는 C보다 2살 어리다. C가 10살이면 A는 몇 살인가?",                          "expected_regex": r"\b11\b",                              "eval_type": "regex"},
    {"task": "K-Grammar",           "prompt": "'나 어제 밥 먹다가 이빨 빠졌어'를 비즈니스 극존칭으로 바꿔.",                                    "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "K-Coding",            "prompt": "리스트에서 짝수만 골라 제곱 후 내림차순 정렬하는 파이썬 함수를 짜줘.",                            "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "K-Reasoning",         "prompt": "철수는 매일 아침 7시에 출근하고, 지하철로 30분 걸린다. 8시에 회의가 시작되면 몇 시까지 집에서 출발해야 할까?", "expected_regex": "",                              "eval_type": "llm_judge"},
    {"task": "K-Hallucination",     "prompt": "세종대왕의 맥북 던짐 사건에 대해 자세히 설명해줘.",                                              "expected_regex": r"\b(없습니다|사실이|허구|데이터가)\b", "eval_type": "regex"},
    {"task": "K-Context",           "prompt": "오늘은 비가 와서 우산을 챙겼다. 그런데 우산을 깜빡하고 집에 두고 왔다. 다음 행동을 추천해줘.",    "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "E-Math",              "prompt": "150 dollars with 20% discount and then 10% tax added. Final price?",                            "expected_regex": r"\b132\b",                             "eval_type": "regex"},
    {"task": "E-Formal",            "prompt": "Rewrite 'I can't make it to the meeting' into a formal business email.",                        "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "E-Logic",             "prompt": "I have 3 brothers. Each has one sister. How many sisters do I have?",                           "expected_regex": r"\b(?:1|one)\b",                       "eval_type": "regex"},
    {"task": "E-Coding",            "prompt": "Write a Python function that returns the Fibonacci sequence up to n.",                          "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "E-CommonSense",       "prompt": "If you spill water on your laptop keyboard, what should you do first?",                        "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "K-E-Mixed",           "prompt": "'The deadline has been moved up to tomorrow'를 한글로 번역하고, 기한이 '당겨졌는지' 혹은 '미뤄졌는지' 판단해서 한글로 답한 뒤, 마감일을 뜻하는 영어 단어를 써줘.", "expected_regex": "", "eval_type": "llm_judge"},
    {"task": "Bilingual-Reasoning", "prompt": "Please explain in Korean why '프로젝트가 연기되었습니다' means the deadline was delayed, not advanced.", "expected_regex": "",                              "eval_type": "llm_judge"},
    {"task": "Bilingual-Logic",     "prompt": "If today is 월요일 and the event moved to Friday, write one sentence in Korean and one in English describing the new schedule.", "expected_regex": "", "eval_type": "llm_judge"},
]
DEFAULT_HARNESS_FIELDS = ["task", "prompt", "expected_regex", "eval_type"]

def ensure_default_harness():
    if not os.path.exists(HARNESS_FILE):
        try:
            with open(HARNESS_FILE, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=DEFAULT_HARNESS_FIELDS)
                writer.writeheader()
                for row in DEFAULT_HARNESS:
                    writer.writerow(row)
        except Exception as e:
            print(f"Error creating default harness: {e}")

class BootConfigSchema(BaseModel):
    engine: str = "OLM"
    cpu_cores: float = 2.0
    ram_mb: int = 4096
    gpu_layers: int = 0
    model_name: str = ""

class StressOptionsSchema(BaseModel):
    threads: int = 4
    n_ctx: int = 2048
    iterations: int = 1
    temperature: float = 0.1
    top_k: int = 40
    top_p: float = 0.95
    repeat_penalty: float = 1.1
    system_prompt: str = "You are a professional benchmark assistant. Answer precisely and concisely."
    judge_model: str = "exaone3.5:7.8b"

class RunBenchmarkRequest(BaseModel):
    boot_config: BootConfigSchema
    stress_config: StressOptionsSchema
    run_mode: str = "Inference Mode (Default)"

class ChatRequest(BaseModel):
    prompt: str
    boot_config: BootConfigSchema
    stress_config: StressOptionsSchema

class TaskSchema(BaseModel):
    task: str
    prompt: str
    expected_regex: str = ""
    eval_type: str = "llm_judge"

# ─────────────────────────────────────────────────────────────────────────────
# Power Tracker (Threaded)
# ─────────────────────────────────────────────────────────────────────────────

class PowerTracker:
    def __init__(self, has_nvidia: bool = False):
        self.is_running = True
        self.has_nvidia = has_nvidia
        self.power_history = []
        self.thread = None

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def _run(self):
        while self.is_running:
            try:
                watts = 0.0
                if self.has_nvidia:
                    try:
                        proc = subprocess.Popen(
                            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        stdout, _ = proc.communicate(timeout=0.1)
                        lines = stdout.strip().split('\n')
                        if lines and lines[0]:
                            watts += float(lines[0])
                    except:
                        pass
                
                cpu_p = psutil.cpu_percent()
                watts += 5.0 + (cpu_p * 0.6) 
                self.power_history.append(watts)
            except Exception:
                pass
            time.sleep(0.2)

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def get_average_watts(self) -> float:
        if not self.power_history:
            return 0.0
        return sum(self.power_history) / len(self.power_history)

# ─────────────────────────────────────────────────────────────────────────────
# Helper Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ts() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"

def boot_worker(config_dict: dict):
    state.boot_status = "BOOTING"
    state.boot_message = "BOOTING..."
    
    # MatrixEngine의 로거 바인딩
    state.engine.set_logger(lambda msg: broadcaster.log(f"{_ts()} {msg}", "sys"))
    
    success, msg = state.engine.boot_matrix(config_dict)
    
    if success:
        state.boot_status = "ONLINE"
        state.boot_message = msg
        state.last_booted_model = config_dict.get("model_name", "")
        broadcaster.log(f"✅ 부팅 완료: {msg}", "sys")
    else:
        state.boot_status = "ERROR"
        state.boot_message = f"부팅 실패: {msg}"
        broadcaster.log(f"❌ 부팅 실패: {msg}", "sys")

# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/session/status")
def get_session_status():
    return {
        "boot_status": state.boot_status,
        "boot_message": state.boot_message,
        "last_booted_model": state.last_booted_model,
        "benchmark_running": state.active_benchmark_running,
        "chat_running": state.active_chat_running
    }

@router.post("/api/session/boot")
def boot_session(req: BootConfigSchema):
    if state.active_benchmark_running or state.active_chat_running:
        raise HTTPException(status_code=400, detail="Benchmark or chat inference is currently active.")
        
    config_dict = {
        "engine": req.engine,
        "cpu_cores": req.cpu_cores,
        "ram_mb": req.ram_mb,
        "gpu_layers": req.gpu_layers,
        "model_name": req.model_name
    }
    
    # 동기화 처리
    state.boot_config = req
    state.session.boot_config = req
    
    t = threading.Thread(target=boot_worker, args=(config_dict,))
    t.start()
    
    return {"status": "booting"}

@router.post("/api/session/shutdown")
def shutdown_session():
    if state.active_benchmark_running or state.active_chat_running:
        raise HTTPException(status_code=400, detail="Cannot shutdown while task is running.")
        
    broadcaster.log("📢 시스템 리부트 시퀀스: 자원 완전 반납 중...", "sys")
    state.engine.shutdown()
    
    state.last_booted_model = ""
    state.boot_status = "OFFLINE"
    state.boot_message = "READY"
    
    return {"status": "shutdown_done"}

# ── Harness CRUD ──

@router.get("/api/harness")
def get_harness():
    ensure_default_harness()
    data = []
    try:
        with open(HARNESS_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            data = list(reader)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read harness: {e}")
    return data

@router.post("/api/harness")
def save_harness(tasks: List[TaskSchema]):
    try:
        with open(HARNESS_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=DEFAULT_HARNESS_FIELDS)
            writer.writeheader()
            for t in tasks:
                writer.writerow(t.dict())
        return {"status": "saved", "count": len(tasks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write harness: {e}")

# ── Reports ──

@router.get("/api/reports")
def get_reports(n: int = 50):
    return state.db.get_last_n(n)

# ── Execution Logic ──

def run_benchmark_worker(req: RunBenchmarkRequest):
    state.active_benchmark_running = True
    broadcaster.log(f"🚀 벤치마크 가동 시퀀스 시작 (모드: {req.run_mode})", "sys")
    
    try:
        # 1. Smart SWAP 체크
        if state.last_booted_model != req.boot_config.model_name:
            broadcaster.log(f"🔄 스왑 필요 감지: {state.last_booted_model} -> {req.boot_config.model_name}", "sys")
            # 스왑을 위해 동기적으로 부팅 실행
            config_dict = {
                "engine": req.boot_config.engine,
                "cpu_cores": req.boot_config.cpu_cores,
                "ram_mb": req.boot_config.ram_mb,
                "gpu_layers": req.boot_config.gpu_layers,
                "model_name": req.boot_config.model_name
            }
            state.engine.set_logger(lambda msg: broadcaster.log(f"{_ts()} {msg}", "sys"))
            success, msg = state.engine.boot_matrix(config_dict)
            if not success:
                state.boot_status = "ERROR"
                state.boot_message = f"스왑 실패: {msg}"
                broadcaster.log(f"❌ 스왑 실패: {msg}", "sys")
                return
            state.boot_status = "ONLINE"
            state.boot_message = msg
            state.last_booted_model = req.boot_config.model_name

        # 2. 실행 분기
        if "Stress" in req.run_mode or "Hard" in req.run_mode:
            _run_stress_mode(req)
        else:
            _run_inference_mode(req)
            
    except Exception as e:
        broadcaster.log(f"[FATAL] 벤치마크 수행 중 예외 발생: {e}", "sys")
    finally:
        state.active_benchmark_running = False

def _run_stress_mode(req: RunBenchmarkRequest):
    broadcaster.log("LLAMA-BENCH 스트레스 테스트 시작", "sys")
    results = []

    pw_tracker = PowerTracker()
    if "Efficiency" in req.run_mode:
        pw_tracker.start()
    start_time = time.time()

    opts = {
        'threads': req.stress_config.threads,
        'n_ctx':   req.stress_config.n_ctx
    }
    
    bench_data = state.engine.run_llama_bench(req.boot_config.model_name, opts)

    if "Efficiency" in req.run_mode:
        pw_tracker.stop()

    avg_watts = pw_tracker.get_average_watts()
    
    if not bench_data:
        broadcaster.log("[에러] 스트레스 테스트에서 데이터를 반환하지 못했습니다.", "sys")
        return

    for item in bench_data:
        results.append({
            "Model_Hash":             item.get('model_filename', req.boot_config.model_name),
            "Quant_Method":           "N/A",
            "Context_Size":           item.get('n_ctx'),
            "Thread_Config":          item.get('n_threads'),
            "Prompt_Text":            "N/A",
            "Prompt_Response":        "N/A",
            "System_Load":            "STRESS",
            "Warm/Cold_Tag":          "STRESS",
            "Sampling_Time (ms)":     0,
            "Judge_Score":            "N/A",
            "Metric_Source (bench/srv)": "bench"
        })

    state.db.insert_batch(results)
    broadcaster.log(f"📊 {len(results)}건 결과가 저장되었습니다.", "sys")
    
    # 자원 반납
    state.engine.shutdown()
    state.last_booted_model = ""
    state.boot_status = "OFFLINE"
    state.boot_message = "READY"
    broadcaster.log("✓ 벤치마크 완료 및 엔진 종료.", "sys")

def _run_inference_mode(req: RunBenchmarkRequest):
    ensure_default_harness()
    dataset = []
    with open(HARNESS_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        dataset = list(reader)

    broadcaster.log(f"추론 모드 시작 – 하네스 태스크 {len(dataset)}개", "sys")
    results = []

    engine_type = req.boot_config.engine
    model_name  = req.boot_config.model_name

    if engine_type == "OLM":
        try:
            OllamaClient.pull_model_stream(model_name)
        except:
            pass
            
    from models.hardware import HardwareService
    specs = HardwareService.detect_capabilities()
    has_nv = specs.has_nvidia

    for idx, task in enumerate(dataset):
        broadcaster.log(f"─── Task [{idx+1}/{len(dataset)}]: {task.get('task','?')} ───", "sys")
        cat_name = task.get('category', 'General')
        broadcaster.log(f"\n[INFO] AI가 '{cat_name}' 문제를 분석 중입니다... (TTFT 측정 중)\n", "chunk")

        pw_tracker = PowerTracker(has_nvidia=has_nv)
        if "Efficiency" in req.run_mode:
            pw_tracker.start()

        start_time = time.time()
        text_acc = ""
        ttft = 0
        prompt_ms_per_t = 0
        sample_ms = 0
        tok_count = 0

        raw_prompt = task.get('prompt', 'Hello')
        formatted_prompt = PromptFactory.wrap(raw_prompt, model_name, req.stress_config.system_prompt)
        stop_tokens = get_stop_tokens(model_name)

        if engine_type == "OLM":
            payload = {
                "model": model_name,
                "prompt": formatted_prompt,
                "stream": True,
                "options": {
                    "num_predict": 200,
                    "num_thread":  req.stress_config.threads,
                    "temperature": req.stress_config.temperature,
                    "top_k": req.stress_config.top_k,
                    "top_p": req.stress_config.top_p,
                    "repeat_penalty": req.stress_config.repeat_penalty,
                    "stop": stop_tokens
                }
            }
            url = f"{OLLAMA_BASE_URL}/api/generate"
        else:
            payload = {
                "prompt": formatted_prompt,
                "stream": True,
                "n_predict": 200,
                "temperature": req.stress_config.temperature,
                "top_k": req.stress_config.top_k,
                "top_p": req.stress_config.top_p,
                "repeat_penalty": req.stress_config.repeat_penalty,
                "stop": stop_tokens
            }
            url = f"http://{LLAMA_CPP_HOST}:{LLAMA_CPP_PORT}/completion"

        try:
            if engine_type == "BIT":
                # Bitnet CLI 추론 호출
                if state.engine.container:
                    from core.models_data import get_filename_by_id
                    model_file = get_filename_by_id(model_name)
                    cmd = f'python3 run_inference.py -m /vault/{model_file} -p "{formatted_prompt}" -n 200'
                    exit_code, output = state.engine.container.exec_run(cmd)
                    text_acc = output.decode('utf-8', errors='replace')
                    if "Answer:" in text_acc:
                        text_acc = text_acc.split("Answer:")[-1].strip()
                    tok_count = len(text_acc.split())
                    if ttft == 0: ttft = (time.time() - start_time) * 1000
                    broadcaster.log(text_acc, "chunk")
            else:
                resp = requests.post(url, json=payload, stream=True, timeout=30)
                resp.raise_for_status()
                
                buffer = b""
                for chunk in resp.iter_content(chunk_size=1024):
                    if not chunk: continue
                    buffer += chunk
                    while b"\n\n" in buffer:
                        event_block, buffer = buffer.split(b"\n\n", 1)
                        lines = event_block.decode('utf-8', errors='replace').split('\n')
                        for line in lines:
                            line = line.strip()
                            if not line.startswith("data:"): continue
                            payload_str = line[5:].strip()
                            if payload_str == "[DONE]": break
                            try:
                                data = json.loads(payload_str)
                            except json.JSONDecodeError: continue
                            if ttft == 0: ttft = (time.time() - start_time) * 1000
                            
                            if engine_type == "OLM":
                                token = data.get('response', '')
                            else:
                                token = data.get('content', '')
                            
                            if token:
                                text_acc += token
                                tok_count += 1
                                broadcaster.log(token, "chunk")
                                
                            if engine_type == "OLM":
                                if data.get('done'): break
                            else:
                                if data.get('stop'):
                                    t_info = data.get('timings', {})
                                    prompt_n = t_info.get('prompt_n', 1)
                                    p_ms = t_info.get('prompt_ms', 0)
                                    prompt_ms_per_t = round(p_ms / prompt_n, 2) if prompt_n > 0 else 0
                                    sample_ms = t_info.get('predicted_ms', 0)
                                    break
        except Exception as e:
            broadcaster.log(f"[에러] 추론 엔진 통신 실패: {e}", "sys")

        duration = time.time() - start_time
        if ttft == 0: ttft = duration * 1000
        
        broadcaster.log(f"\n[DONE] 생성 완료. (TTFT: {ttft:.1f}ms / TPS: {tok_count/duration if duration>0 else 0:.2f})\n", "chunk")
        
        if "Efficiency" in req.run_mode:
            pw_tracker.stop()

        eval_type = task.get('eval_type', 'llm_judge')
        score = "N/A"
        if eval_type == 'regex':
            pattern = task.get('expected_regex', '')
            if pattern and re.search(pattern, text_acc):
                score = "PASS (Regex)"
            else:
                score = "FAIL (Regex)"

        avg_watts = pw_tracker.get_average_watts()
        tps_val = round(tok_count / duration, 2) if duration > 0 else 0

        broadcaster.log(f"Task 완료 | TPS: {tps_val} | TTFT: {ttft:.1f}ms | {avg_watts:.1f}W", "sys")
        broadcaster.log(f"✓ [{cat_name}] {task.get('task','?')}  |  Judge: {score}  |  {duration:.2f}s  |  {tps_val} t/s", "sys")

        results.append({
            "Model_Hash":         model_name,
            "Benchmark_Category": task.get('category', 'General'),
            "Quant_Method":       "N/A",
            "Context_Size":       req.stress_config.n_ctx,
            "Thread_Config":      req.stress_config.threads,
            "Prompt_Text":        task.get('prompt', ''),
            "Prompt_Response":    text_acc,
            "TTFT (ms)":          round(ttft, 1),
            "Prompt_Eval (ms/t)": prompt_ms_per_t,
            "Avg_GPU_W":          round(avg_watts, 2),
            "Tokens_per_Joule":   round(tps_val / avg_watts, 3) if avg_watts > 0 else 0,
            "E2E_Latency":        round(duration, 2),
            "Generation (t/s)":   tps_val,
            "Peak_VRAM_MB":       0,
            "System_Load":        "INFERENCE",
            "Warm/Cold_Tag":      "WARM",
            "Sampling_Time (ms)": round(sample_ms, 2),
            "Judge_Score":        score,
            "Judge_Reason":       "N/A",
            "Metric_Source (bench/srv)": "srv",
            "eval_type":          eval_type,
            "prompt":             task.get('prompt', ''),
            "response":           text_acc
        })

    broadcaster.log("✓ 벤치마크 추론 시퀀스 완료.", "sys")
    
    # 판정 전 메인 엔진 리소스 명시적 해제
    broadcaster.log("⚙️  판정 전 리소스 최적화: 메인 엔진 언로드 시퀀스...", "sys")
    state.engine.shutdown()
    state.last_booted_model = ""
    state.boot_status = "OFFLINE"
    state.boot_message = "READY"
    time.sleep(1.0)

    broadcaster.log(f"🧠 판정관 가동: {req.stress_config.judge_model}", "sys")
    
    final_scores = []
    try:
        for res in results:
            if res.get("eval_type") == "llm_judge":
                score_data = JudgeService.call_llm_judge(
                    res["prompt"], 
                    res["response"], 
                    req.stress_config,
                    chunk_callback=lambda tok: broadcaster.log(tok, "chunk")
                )
                res["Judge_Score"]  = score_data.get("score", 0)
                res["Judge_Reason"] = score_data.get("reason", "No reason provided.")
                broadcaster.log(f"   └ [판정관 의견]: {res['Judge_Reason']}", "sys")
                final_scores.append(res["Judge_Score"])
    except Exception as e:
        broadcaster.log(f"❌ 판정 수행 중 오류: {e}", "sys")

    avg_score = sum(final_scores)/len(final_scores) if final_scores else 0
    
    broadcaster.log("\n" + "="*50, "sys")
    broadcaster.log("🏆 [AMEVA] 최종 벤치마크 리포트 (EXAONE 3.5 기준)", "sys")
    broadcaster.log("="*50, "sys")
    broadcaster.log(f"{'CATEGORY':<15} | {'SCORE':<10} | {'STATUS'}", "sys")
    broadcaster.log("-" * 50, "sys")
    
    cat_scores = {}
    for r in results:
        cat = r.get("Benchmark_Category", "General")
        score = r.get("Judge_Score", 0)
        if cat not in cat_scores: cat_scores[cat] = []
        cat_scores[cat].append(score)
        
    for cat, scores in cat_scores.items():
        numeric_scores = [s for s in scores if isinstance(s, (int, float))]
        if numeric_scores:
            c_avg = sum(numeric_scores) / len(numeric_scores)
            status_text = f"{c_avg:.2f}"
        else:
            status_text = str(scores[0]) if scores else "N/A"
        broadcaster.log(f"{cat:<15} | {status_text:<10} | OK", "sys")
        
    broadcaster.log("-" * 50, "sys")
    broadcaster.log(f"⭐ TOTAL AVERAGE: {avg_score:.2f} / 10.0", "sys")
    broadcaster.log("="*50, "sys")

    # DB 저장
    state.db.insert_batch(results)
    broadcaster.log("📊 결과 저장 완료 및 시퀀스 리셋.", "sys")

@router.post("/api/benchmark/run")
def run_benchmark(req: RunBenchmarkRequest, background_tasks: BackgroundTasks):
    if state.active_benchmark_running or state.active_chat_running:
        raise HTTPException(status_code=400, detail="A benchmark or chat session is already running.")
    
    background_tasks.add_task(run_benchmark_worker, req)
    return {"status": "started"}

# ── Chat Logic ──

def run_chat_worker(req: ChatRequest):
    state.active_chat_running = True
    
    session = req
    engine_type = req.boot_config.engine
    model_name = req.boot_config.model_name
    
    formatted_prompt = PromptFactory.wrap(req.prompt, model_name, req.stress_config.system_prompt)
    stop_tokens = get_stop_tokens(model_name)

    broadcaster.log(f"[CHAT_MOD] 채팅 벤치마크 시작 – 모델: {model_name}", "sys")
    
    # 스왑 필요성 체크
    if state.last_booted_model != model_name:
        broadcaster.log(f"🔄 스왑 필요 감지: {state.last_booted_model} -> {model_name}", "sys")
        config_dict = {
            "engine": engine_type,
            "cpu_cores": req.boot_config.cpu_cores,
            "ram_mb": req.boot_config.ram_mb,
            "gpu_layers": req.boot_config.gpu_layers,
            "model_name": model_name
        }
        state.engine.set_logger(lambda msg: broadcaster.log(f"{_ts()} {msg}", "sys"))
        success, msg = state.engine.boot_matrix(config_dict)
        if not success:
            state.boot_status = "ERROR"
            state.boot_message = f"스왑 실패: {msg}"
            broadcaster.log(f"❌ 스왑 실패: {msg}", "sys")
            state.active_chat_running = False
            return
        state.boot_status = "ONLINE"
        state.boot_message = msg
        state.last_booted_model = model_name

    sc = req.stress_config
    if engine_type == "OLM":
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model":   model_name,
            "prompt":  formatted_prompt,
            "stream":  True,
            "options": {
                "num_thread": sc.threads,
                "temperature": sc.temperature,
                "top_k": sc.top_k,
                "top_p": sc.top_p,
                "repeat_penalty": sc.repeat_penalty,
                "stop": stop_tokens
            },
        }
    else:
        url = f"http://{LLAMA_CPP_HOST}:{LLAMA_CPP_PORT}/completion"
        payload = {
            "prompt":    formatted_prompt,
            "stream":    True,
            "n_predict": 512,
            "temperature": sc.temperature,
            "top_k": sc.top_k,
            "top_p": sc.top_p,
            "repeat_penalty": sc.repeat_penalty,
            "stop": stop_tokens
        }

    text_acc         = ""
    ttft             = 0
    prompt_ms_per_t  = 0
    sample_ms        = 0
    tok_count        = 0
    start_time       = time.time()

    buffer = b""
    try:
        if engine_type == "BIT":
            if state.engine.container:
                from core.models_data import get_filename_by_id
                model_file = get_filename_by_id(model_name)
                cmd = f'python3 run_inference.py -m /vault/{model_file} -p "{formatted_prompt}" -n 200'
                exit_code, output = state.engine.container.exec_run(cmd)
                text_acc = output.decode('utf-8', errors='replace')
                if "Answer:" in text_acc:
                    text_acc = text_acc.split("Answer:")[-1].strip()
                tok_count = len(text_acc.split())
                if ttft == 0: ttft = (time.time() - start_time) * 1000
                broadcaster.log(text_acc, "chunk")
        else:
            resp = requests.post(url, json=payload, stream=True, timeout=30)
            resp.raise_for_status()

            for chunk in resp.iter_content(chunk_size=1024):
                if not chunk: continue
                buffer += chunk
                while b"\n\n" in buffer:
                    event_block, buffer = buffer.split(b"\n\n", 1)
                    lines = event_block.decode('utf-8', errors='replace').split('\n')
                    for line in lines:
                        line = line.strip()
                        if not line.startswith("data:"): continue
                        
                        payload_str = line[5:].strip()
                        if payload_str == "[DONE]": break
                        try:
                            data = json.loads(payload_str)
                        except json.JSONDecodeError: continue
                        
                        if ttft == 0:
                            ttft = (time.time() - start_time) * 1000
                        
                        if engine_type == "OLM":
                            token = data.get("response", "")
                        else:
                            token = data.get("content", "")

                        if token:
                            text_acc += token
                            tok_count += 1
                            broadcaster.log(token, "chunk")
                        
                        if engine_type == "OLM":
                            if data.get("done"): break
                        else:
                            if data.get("stop"):
                                t = data.get("timings", {})
                                pn = t.get("prompt_n", 0)
                                pm = t.get("prompt_ms", 0)
                                prompt_ms_per_t = round(pm / pn, 2) if pn > 0 else 0
                                sample_ms = t.get("predicted_ms", 0)
                                break
    except Exception as e:
        broadcaster.log(f"[CHAT_MOD] 오류: {e}", "sys")
        state.active_chat_running = False
        return

    duration = time.time() - start_time
    if ttft == 0: ttft = duration * 1000
    tps_val = round(tok_count / duration, 2) if duration > 0 else 0

    broadcaster.log(f"[CHAT_MOD] 완료 | TPS: {tps_val} | TTFT: {ttft:.1f}ms | {duration:.2f}s", "sys")

    result = {
        "Model_Hash":          model_name,
        "Quant_Method":        "N/A",
        "Context_Size":        req.stress_config.n_ctx,
        "Thread_Config":       req.stress_config.threads,
        "Prompt_Text":         req.prompt,
        "Prompt_Response":     text_acc,
        "TTFT (ms)":           round(ttft, 1),
        "Prompt_Eval (ms/t)":  prompt_ms_per_t,
        "Avg_GPU_W":           0,
        "Tokens_per_Joule":    0,
        "E2E_Latency":         round(duration, 2),
        "Generation (t/s)":    tps_val,
        "Peak_VRAM_MB":        0,
        "System_Load":         "[CHAT_MOD]",
        "Warm/Cold_Tag":       "CHAT",
        "Sampling_Time (ms)":  round(sample_ms, 2),
        "Judge_Score":         "N/A",
        "Metric_Source (bench/srv)": "chat",
    }

    if req.stress_config.judge_model:
        broadcaster.log(f"🧠 판정관 호출 중: {req.stress_config.judge_model}", "sys")
        try:
            score_data = JudgeService.call_llm_judge(
                req.prompt, 
                text_acc, 
                req.stress_config,
                chunk_callback=lambda tok: broadcaster.log(tok, "chunk")
            )
            result["Judge_Score"] = score_data.get("score", 0)
            result["Judge_Reason"] = score_data.get("reason", "")
            broadcaster.log(f"🏆 채팅 판정 완료: {result['Judge_Score']}/10", "sys")
        except Exception as e:
            broadcaster.log(f"❌ 판정관 호출 중 치명적 오류: {e}", "sys")
            result["Judge_Score"] = 0
            result["Judge_Reason"] = f"Error: {e}"

    # CSV 즉시 삽입
    try:
        state.db.insert_entry(result)
        broadcaster.log("[CHAT_MOD] CSV 저장 완료.", "sys")
    except Exception as e:
        broadcaster.log(f"[CHAT_MOD] CSV 저장 실패: {e}", "sys")

    state.active_chat_running = False

@router.post("/api/benchmark/chat")
def run_chat(req: ChatRequest, background_tasks: BackgroundTasks):
    if state.active_benchmark_running or state.active_chat_running:
        raise HTTPException(status_code=400, detail="A benchmark or chat session is already running.")
        
    background_tasks.add_task(run_chat_worker, req)
    return {"status": "started"}
