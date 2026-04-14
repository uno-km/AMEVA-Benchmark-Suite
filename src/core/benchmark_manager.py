import time
import json
import requests
import subprocess
from datetime import datetime
from openai import OpenAI
from PySide6.QtCore import QThread, Signal
from models.settings import BenchmarkSession
from models.hardware import HardwareService


def _ts() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"


class PowerTracker(QThread):
    """전력 소모(Watts)를 0.2s 주기로 비동기 폴링합니다."""

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.power_history = []

    def run(self):
        while self.is_running:
            try:
                proc = subprocess.Popen(
                    ["nvidia-smi", "--query-gpu=power.draw",
                     "--format=csv,noheader,nounits"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
                stdout, _ = proc.communicate()
                lines = stdout.strip().split('\n')
                if lines and lines[0]:
                    watts = float(lines[0])
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
    """[V5.5] 벤치마크 실행 엔진 – 추론 / 스트레스 테스트를 담당합니다."""

    log_signal     = Signal(str)   # Analytics 탭 로그
    sys_log_signal = Signal(str)   # Kernel Telemetry 탭 로그 (엔진 원시 출력)
    token_signal   = Signal(int)   # 누적 토큰 증분 (+N)
    report_signal  = Signal(list)  # 최종 결과 리스트

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

    def _call_llm_judge(self, prompt: str, response_text: str) -> str:
        if not self.session.judge_key:
            return "건너뜀 (API 키 없음)"
        try:
            client = OpenAI(api_key=self.session.judge_key)
            judge_prompt = (
                f"프롬프트: {prompt}\n응답: {response_text}\n"
                "'PASS' 또는 'FAIL' 중 하나만 출력하세요."
            )
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": judge_prompt}],
                max_tokens=10, temperature=0.0
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"판정_에러: {e}"

    # ── Thread entry ───────────────────────────────────────────────────

    def run(self):
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
                "TTFT (ms)":              0,
                "Prompt_Eval (ms/t)":     round(item.get('test_time_ms', 0) / max(item.get('n_prompt', 1), 1), 2),
                "Avg_GPU_W":              round(avg_watts, 2),
                "Tokens_per_Joule":       round(tps_val / avg_watts, 3) if avg_watts > 0 else 0,
                "E2E_Latency":            round(e2e, 2),
                "Generation (t/s)":       tps_val,
                "Peak_VRAM_MB":           0,
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
            url = "http://127.0.0.1:11434/api/generate"
            self._slog(f"Ollama API 엔드포인트: {url}")
            try:
                requests.post(
                    "http://127.0.0.1:11434/api/pull",
                    json={"name": model_name}, timeout=5
                )
                self._slog(f"모델 풀 완료: {model_name}")
            except Exception as e:
                self._slog(f"[WARN] 모델 풀 실패 (이미 존재할 수 있음): {e}")
        else:
            url = "http://127.0.0.1:8080/completion"
            self._slog(f"LLAMA.CPP 엔드포인트: {url}")

        for idx, task in enumerate(self.dataset):
            self._slog(f"─── Task [{idx+1}/{len(self.dataset)}]: {task.get('task','?')} ───")

            pw_tracker = PowerTracker()
            if "Efficiency" in self.session.run_mode:
                pw_tracker.start()

            start_time = time.time()
            text_acc = ""
            ttft = 0
            prompt_ms_per_t = 0
            sample_ms = 0
            tok_count = 0

            payload = {
                "model":   model_name,
                "prompt":  task.get('prompt', ''),
                "stream":  True,
                "options": {"num_thread": self.session.stress_config.threads}
            }
            if engine_type == "ENG":
                payload = {
                    "prompt": task.get('prompt', ''),
                    "stream": True, "n_predict": 512
                }

            try:
                if engine_type == "ENG":
                    resp = requests.post(url, json=payload, stream=True, timeout=120)
                    if resp.status_code != 200:
                        self._slog(f"[에러] LLAMA.CPP 서버 상태 {resp.status_code}: {resp.text[:200]}")
                    else:
                        for raw_line in resp.iter_lines(decode_unicode=True):
                            if not raw_line:
                                continue
                            decoded = raw_line.strip()
                            if not decoded.startswith("data: "):
                                continue
                            decoded = decoded[6:]
                            if decoded == "[DONE]":
                                break

                            data = json.loads(decoded)
                            if ttft == 0:
                                ttft = (time.time() - start_time) * 1000

                            token = data.get('content', '')
                            text_acc += token
                            tok_count += len(data.get('tokens', [])) or len(token.split())
                            self._slog(f"[CPP] token: {repr(token)}")
                            self.token_signal.emit(1)

                            if data.get('stop'):
                                t_info = data.get('timings', {})
                                pn = t_info.get('prompt_n', 0)
                                pm = t_info.get('prompt_ms', 0)
                                prompt_ms_per_t = round(pm / pn, 2) if pn > 0 else 0
                                sample_ms = t_info.get('predicted_ms', 0)
                                break
                else:
                    resp = requests.post(url, json=payload, stream=True, timeout=120)
                    for raw_line in resp.iter_lines(decode_unicode=True):
                        if not raw_line:
                            continue
                        decoded = raw_line.strip()

                        data = json.loads(decoded)

                        if ttft == 0:
                            ttft = (time.time() - start_time) * 1000

                        if engine_type == "OLM":
                            token = data.get('response', '')
                            text_acc += token
                            tok_count += 1
                            # 실시간 엔진 로그
                            self._slog(f"[OLM] token: {repr(token)}")
                            self.token_signal.emit(1)
                            if data.get('done'):
                                break

            except Exception as e:
                self._slog(f"[에러] 추론 실패: {e}")
                self._log(f"[에러] {e}")

            duration = time.time() - start_time
            if "Efficiency" in self.session.run_mode:
                pw_tracker.stop()

            avg_watts = pw_tracker.get_average_watts()
            score = self._call_llm_judge(task.get('prompt', ''), text_acc)
            tps_val = round(tok_count / duration, 2) if duration > 0 else 0

            self._slog(f"Task 완료 | TPS: {tps_val} | TTFT: {ttft:.1f}ms | {avg_watts:.1f}W")
            self._log(f"✓ {task.get('task','?')}  |  Judge: {score}  |  {duration:.2f}s  |  {tps_val} t/s")

            results.append({
                "Model_Hash":         model_name,
                "Quant_Method":       "N/A",
                "Context_Size":       self.session.stress_config.n_ctx,
                "Thread_Config":      self.session.stress_config.threads,
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
                "Metric_Source":      "srv"
            })

        self.report_signal.emit(results)
