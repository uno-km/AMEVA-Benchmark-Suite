import time
import json
import subprocess
import re
from datetime import datetime
from openai import OpenAI
import psutil
import requests

from ui.qt_bridge import *
from .ollama_client import OllamaClient
from .constants import OLLAMA_BASE_URL, LLAMA_CPP_HOST, LLAMA_CPP_PORT
from models.settings import BenchmarkSession
from models.hardware import HardwareService
from core.prompt_utils import format_chatml, get_stop_tokens
from .judge_service import JudgeService

def _ts() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"


import psutil

class PowerTracker(QThread):
    """[Engineering] 전력 소모(Watts)를 0.2s 주기로 정밀 폴링 및 추정합니다."""

    def __init__(self, has_nvidia: bool = False):
        super().__init__()
        self.is_running = True
        self.has_nvidia = has_nvidia
        self.power_history = []
        self.cpu_count = psutil.cpu_count()

    def run(self):
        while self.is_running:
            try:
                watts = 0.0
                # 1. GPU 전력 가용 시 우선 수집
                if self.has_nvidia:
                    try:
                        proc = subprocess.Popen(
                            ["nvidia-smi", "--query-gpu=power.draw",
                             "--format=csv,noheader,nounits"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        stdout, _ = proc.communicate(timeout=0.1)
                        lines = stdout.strip().split('\n')
                        if lines and lines[0]:
                            watts += float(lines[0])
                    except:
                        pass
                
                # 2. CPU 전력 추정 (가상 디바이스 프로필 기반: Load% * TDP_base)
                # TDP 65W급 CPU 기준 추정 모델: idle(5W) + (load% * 0.6)
                cpu_p = psutil.cpu_percent()
                watts += 5.0 + (cpu_p * 0.6) 

                self.power_history.append(watts)
            except Exception:
                pass
            time.sleep(0.2)

    def stop(self):
        self.is_running = False
        self.wait()

    def get_average_watts(self) -> float:
        if not self.power_history:
            return 0.0
        return sum(self.power_history) / len(self.power_history)


class ExecutionEngine(QThread):
    """[Engineering] 벤치마크 실행 엔진 – 정밀 데이터 수집 및 가상 환경 최적화."""

    log_signal     = Signal(str)   # UI Analytics
    sys_log_signal = Signal(str)   # Kernel Telemetry
    token_signal   = Signal(int)   # Token cumulative
    chunk_signal   = Signal(str)   # Real-time text chunk for streaming tab
    report_signal  = Signal(list)  # Data verification report

    def __init__(self, session: BenchmarkSession, dataset: list, engine_core):
        super().__init__()
        self.session = session
        self.dataset = dataset
        self.engine_core = engine_core

    # ── 내부 유틸 ──────────────────────────────────────────────────────

    def _slog(self, msg: str):
        """타임스탬프 붙여 sys_log_signal 로 emit."""
        self.sys_log_signal.emit(f"{_ts()} {msg}")

    def _log(self, msg: str):
        self.log_signal.emit(msg)

    def _call_llm_judge(self, prompt: str, response: str) -> dict:
        """[Engineering] 판정관 서비스 대행."""
        # 스트리밍 창에 판정관 출근 알림
        self.chunk_signal.emit(f"\n\n--- 🧠 Local Judge Thought ({self.session.stress_config.judge_model}) ---\n")
        
        result = JudgeService.call_llm_judge(
            prompt, 
            response, 
            self.session.stress_config,
            chunk_callback=self.chunk_signal.emit
        )
        
        self.chunk_signal.emit("\n--- End of Thought ---\n")
        return result

    def _post_stream_with_fallback(self, base_url: str, payload: dict, engine_type: str):
        endpoints = [base_url]
        if engine_type == "ENG":
            if base_url.endswith("/completion"):
                endpoints.append(base_url.replace("/completion", "/v1/completions"))
        else:
            if base_url.endswith("/api/generate"):
                endpoints.append(base_url.replace("/api/generate", "/v1/completions"))

        last_error = None
        for endpoint in endpoints:
            try:
                resp = requests.post(endpoint, json=payload, stream=True, timeout=20)
                if resp.status_code == 200:
                    if endpoint != base_url:
                        self._slog(f"[INFO] 대체 엔드포인트 사용: {endpoint}")
                    return resp
                self._slog(f"[WARN] {endpoint} HTTP {resp.status_code} - {resp.text[:180]}")
            except Exception as e:
                self._slog(f"[WARN] {endpoint} 연결 실패: {e}")
                last_error = e
        if last_error:
            raise last_error
        raise RuntimeError("엔드포인트를 찾을 수 없습니다.")

    # ── Thread entry ───────────────────────────────────────────────────

    def run(self):
        if self.isInterruptionRequested():
            return
        if "Stress" in self.session.run_mode or "Hard" in self.session.run_mode:
            self._run_stress_mode()
        else:
            self._run_inference_mode()

    # ── Stress mode ────────────────────────────────────────────────────

    def _run_stress_mode(self):
        self._slog("LLAMA-BENCH 스트레스 테스트 시작")
        results = []

        pw_tracker = PowerTracker()
        if "Efficiency" in self.session.run_mode:
            pw_tracker.start()
        start_time = time.time()

        if self.isInterruptionRequested():
            self._slog("[INFO] 스트레스 테스트 취소 요청 수신.")
            return

        opts = {
            'threads': self.session.stress_config.threads,
            'n_ctx':   self.session.stress_config.n_ctx
        }
        bench_data = self.engine_core.run_llama_bench(
            self.session.boot_config.model_name, opts
        )

        if "Efficiency" in self.session.run_mode:
            pw_tracker.stop()

        avg_watts = pw_tracker.get_average_watts()
        e2e = time.time() - start_time

        if not bench_data:
            self._log("[에러] 스트레스 테스트에서 데이터를 반환하지 못했습니다.")
            return

        for item in bench_data:
            tps_val = round(item.get('t/s', 0), 2)
            results.append({
                "Model_Hash":             item.get('model_filename', self.session.boot_config.model_name),
                "Quant_Method":           "N/A",
                "Context_Size":           item.get('n_ctx'),
                "Thread_Config":          item.get('n_threads'),
                    "Prompt_Text":            "N/A",
                    "Prompt_Response":        "N/A",
                "System_Load":            "STRESS",
                "Warm/Cold_Tag":          "STRESS",
                "Sampling_Time (ms)":     0,
                "Judge_Score":            "N/A",
                "Metric_Source":          "bench"
            })

        self.report_signal.emit(results)

    # ── Inference mode ─────────────────────────────────────────────────

    def _run_inference_mode(self):
        self._slog(f"추론 모드 시작 – 하네스 태스크 {len(self.dataset)}개")
        results = []

        engine_type = self.session.boot_config.engine
        model_name  = self.session.boot_config.model_name

        if engine_type == "OLM":
            url = f"{OLLAMA_BASE_URL}/api/generate"
            self._slog(f"Ollama API 엔드포인트: {url}")
            try:
                # OllamaClient 활용
                OllamaClient.pull_model_stream(model_name)
                self._slog(f"모델 풀 완료: {model_name}")
            except Exception as e:
                self._slog(f"[WARN] 모델 풀 실패 (이미 존재할 수 있음): {e}")
        else:
            url = f"http://{LLAMA_CPP_HOST}:{LLAMA_CPP_PORT}/completion"
            self._slog(f"LLAMA.CPP 엔드포인트: {url}")

        has_nv = self.engine_core.container is not None # 컨테이너가 있고 nvida-smi 가능 시 True
        # 실제 HardwareService 기반 감지로 보강
        from models.hardware import HardwareService
        specs = HardwareService.detect_capabilities()
        has_nv = specs.has_nvidia

        for idx, task in enumerate(self.dataset):
            if self.isInterruptionRequested():
                self._slog("[INFO] 벤치마크 취소 요청 수신.")
                break

            self._slog(f"─── Task [{idx+1}/{len(self.dataset)}]: {task.get('task','?')} ───")
            cat_name = task.get('category', 'General')
            self.chunk_signal.emit(f"\n\n[INFO] AI가 '{cat_name}' 문제를 분석 중입니다... (TTFT 측정 중)\n")

            pw_tracker = PowerTracker(has_nvidia=has_nv)
            if "Efficiency" in self.session.run_mode:
                pw_tracker.start()

            start_time = time.time()
            text_acc = ""
            ttft = 0
            prompt_ms_per_t = 0
            sample_ms = 0
            tok_count = 0
            repeat_count = 0
            last_token = ""

            # 사용자의 원래 질문
            raw_prompt = task.get('prompt', '')

            # 1. [페이로드 튜닝] Qwen 0.5B의 창의성을 거세하고 팩트 기계로 만듭니다.
            sample_ms = 0

            # 1. 페이로드 준비 (ChatML 적용 및 동적 튜닝 피드백)
            raw_prompt = task.get('prompt', 'Hello')
            sc = self.session.stress_config
            formatted_prompt = format_chatml(raw_prompt, sc.system_prompt)
            stop_tokens = get_stop_tokens(engine_type)

            if engine_type == "OLM":
                payload = {
                    "model": model_name,
                    "prompt": formatted_prompt,
                    "stream": True,
                    "options": {
                        "num_predict": 200,
                        "num_thread":  sc.threads, # CPU 가속 활성화
                        "temperature": sc.temperature,
                        "top_k": sc.top_k,
                        "top_p": sc.top_p,
                        "repeat_penalty": sc.repeat_penalty,
                        "stop": stop_tokens
                    }
                }
            else:
                payload = {
                    "prompt": formatted_prompt,
                    "stream": True,
                    "n_predict": 200,
                    "temperature": sc.temperature,
                    "top_k": sc.top_k,
                    "top_p": sc.top_p,
                    "repeat_penalty": sc.repeat_penalty,
                    "stop": stop_tokens
                }

            # 2. [스트림 통신부] 정교한 바이트 단위 SSE 파서 구현 (한글 깨짐 방지)
            try:
                resp = requests.post(url, json=payload, stream=True, timeout=30)
                resp.raise_for_status()
                
                buffer = b""
                # SSE 규격상 하나의 이벤트는 \n\n 으로 끝납니다.
                for chunk in resp.iter_content(chunk_size=1024):
                    if self.isInterruptionRequested():
                        break
                    if not chunk:
                        continue
                    
                    buffer += chunk
                    
                    while b"\n\n" in buffer:
                        event_block, buffer = buffer.split(b"\n\n", 1)
                        
                        # 각 라인을 돌며 data: 접두사가 있는지 확인
                        lines = event_block.decode('utf-8', errors='replace').split('\n')
                        for line in lines:
                            line = line.strip()
                            if not line.startswith("data:"):
                                continue
                            
                            payload_str = line[5:].strip()
                            if payload_str == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(payload_str)
                            except json.JSONDecodeError:
                                continue
                            
                            # 데이터 추출 및 TTFT 측정
                            if ttft == 0:
                                ttft = (time.time() - start_time) * 1000
                            
                            if engine_type == "OLM":
                                token = data.get('response', '')
                            else:
                                token = data.get('content', '')
                                
                            if token:
                                text_acc += token
                                tok_count += 1
                                self.token_signal.emit(1)
                                self.chunk_signal.emit(token)
                                
                            # 종료 조건 체크
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
                self._slog(f"[에러] 스트림 통신 실패: {e}")
                self._log(f"[에러] {e}")

            duration = time.time() - start_time
            if ttft == 0:
                ttft = duration * 1000
            
            # 스트리밍 창에 완료 알림
            self.chunk_signal.emit(f"\n[DONE] 생성 완료. (TTFT: {ttft:.1f}ms / TPS: {tok_count/duration if duration>0 else 0:.2f})\n")
            if "Efficiency" in self.session.run_mode:
                pw_tracker.stop()

            # [Engineering] CSV 설정에 따른 자동 채점 분기 처리 (Regex vs LLM Judge)
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


            self._slog(f"Task 완료 | TPS: {tps_val} | TTFT: {ttft:.1f}ms | {avg_watts:.1f}W")
            category = task.get('category', 'General')
            self._log(f"✓ [{category}] {task.get('task','?')}  |  Judge: {score}  |  {duration:.2f}s  |  {tps_val} t/s")

            results.append({
                "Model_Hash":         model_name,
                "Benchmark_Category": task.get('category', 'General'),
                "Quant_Method":       "N/A",
                "Context_Size":       self.session.stress_config.n_ctx,
                "Thread_Config":      self.session.stress_config.threads,
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

        self._log("✓ 벤치마크 추론 시퀀스 완료.")

        # --- [Phase: Resourcing] ---
        # 저사양 환경을 위해 판정 전 메인 엔진 리소스 명시적 해제
        self._log("⚙️  판정 전 리소스 최적화: 메인 엔진 언로드 시퀀스...")
        if hasattr(self.engine_core, "shutdown"):
            self.engine_core.shutdown()
        time.sleep(1.0) # OS 레벨 RAM 반납 대기

        self._log(f"🧠 판정관 가동: {self.session.stress_config.judge_model}")
        
        # --- [Phase: Judging] ---
        final_scores = []
        for res in results:
            if res.get("eval_type") == "llm_judge":
                score_data = self._call_llm_judge(res["prompt"], res["response"])
                res["Judge_Score"]  = score_data.get("score", 0)
                res["Judge_Reason"] = score_data.get("reason", "No reason provided.")
                self._log(f"   └ [판정관 의견]: {res['Judge_Reason']}")
                final_scores.append(res["Judge_Score"])

        avg_score = sum(final_scores)/len(final_scores) if final_scores else 0
        
        # --- [Phase: Scorecard Visualization] ---
        self._log("\n" + "="*50)
        self._log("🏆 [AMEVA] 최종 벤치마크 리포트 (EXAONE 3.5 기준)")
        self._log("="*50)
        self._log(f"{'CATEGORY':<15} | {'SCORE':<10} | {'REASON SUMMARY'}")
        self._log("-" * 50)
        
        cat_scores = {}
        for r in results:
            cat = r.get("Benchmark_Category", "General")
            score = r.get("Judge_Score", 0)
            if cat not in cat_scores: cat_scores[cat] = []
            cat_scores[cat].append(score)
            
        for cat, scores in cat_scores.items():
            c_avg = sum(scores)/len(scores)
            self._log(f"{cat:<15} | {c_avg:<10.2f} | PASS")
            
        self._log("-" * 50)
        self._log(f"⭐ TOTAL AVERAGE: {avg_score:.2f} / 10.0")
        self._log("="*50)
        
        # 업데이트된 결과 다시 전송
        self.report_signal.emit(results)
