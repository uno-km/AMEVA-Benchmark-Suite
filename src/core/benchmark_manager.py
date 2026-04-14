import subprocess
from openai import OpenAI
from PySide6.QtCore import QThread, Signal
from models.settings import BenchmarkSession
from models.hardware import HardwareService

class PowerTracker(QThread):
    def __init__(self):
        super().__init__()
        self.is_running = True
        self.power_history = []
        
    def run(self):
        while self.is_running:
            try:
                # nvidia-smi 사용 가능 시 사용
                cmd = ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                stdout, _ = proc.communicate()
                lines = stdout.strip().split('\n')
                if lines and lines[0]:
                    try:
                        watts = float(lines[0])
                        self.power_history.append(watts)
                    except ValueError: pass
            except Exception: pass
            time.sleep(0.2)
            
    def stop(self):
        self.is_running = False
        self.wait()
        
    def get_average_watts(self):
        if not self.power_history: return 0.0
        return sum(self.power_history) / len(self.power_history)

class ExecutionEngine(QThread):
    """[V5.5] 실행 엔진 - 벤치마크 로직(추론 및 스트레스 테스트)을 담당합니다."""
    log_signal = Signal(str)
    report_signal = Signal(list)
    
    def __init__(self, session: BenchmarkSession, dataset: list, engine_core):
        super().__init__()
        self.session = session
        self.dataset = dataset
        self.engine_core = engine_core
        self.is_blackout = False

    def _call_llm_judge(self, prompt, response_text):
        if not self.session.judge_key:
            return "건너뜀 (API 키 없음)"
        try:
            client = OpenAI(api_key=self.session.judge_key)
            judge_prompt = f"다음 응답이 프롬프트에 완벽하게 답변하는지 평가하세요.\n프롬프트: {prompt}\n응답: {response_text}\n'PASS' 또는 'FAIL' 중 하나만 출력하세요."
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": judge_prompt}],
                max_tokens=10, temperature=0.0
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"판정_에러: {str(e)}"

    def run(self):
        if "Stress" in self.session.run_mode:
            self._run_stress_mode()
        else:
            self._run_inference_mode()

    def _run_stress_mode(self):
        self.log_signal.emit(f"[스트레스] LLAMA-BENCH 콜드 부팅 시작 중...")
        results = []
        
        # 요청된 경우 전력 추적 시작
        pw_tracker = PowerTracker()
        if "Power" in self.session.run_mode:
            pw_tracker.start()

        start_time = time.time()
        
        # 세션에서 스트레스 옵션 가져오기
        opts = {
            'threads': self.session.stress_config.threads,
            'n_ctx': self.session.stress_config.n_ctx
        }
        
        bench_data = self.engine_core.run_llama_bench(self.session.boot_config.model_name, opts)
        
        if "Power" in self.session.run_mode:
            pw_tracker.stop()
        
        avg_watts = pw_tracker.get_average_watts()
        e2e = time.time() - start_time
        
        if not bench_data:
            self.log_signal.emit("[에러] 스트레스 테스트에서 데이터를 반환하지 못했습니다.")
            return

        for item in bench_data:
            tps_val = round(item.get('t/s', 0), 2)
            results.append({
                "Model_Hash": item.get('model_filename', self.session.boot_config.model_name),
                "Quant_Method": "N/A",
                "Context_Size": item.get('n_ctx'),
                "Thread_Config": item.get('n_threads'),
                "TTFT (ms)": 0,
                "Prompt_Eval (ms/t)": round(item.get('test_time_ms', 0) / item.get('n_prompt', 1), 2) if item.get('n_prompt', 0) > 0 else 0,
                "Avg_GPU_W": round(avg_watts, 2),
                "Tokens_per_Joule": round(tps_val / avg_watts, 3) if avg_watts > 0 else 0,
                "E2E_Latency": round(e2e, 2),
                "Generation (t/s)": tps_val,
                "Peak_VRAM_MB": 0,
                "System_Load": "STRESS",
                "Warm/Cold_Tag": "STRESS",
                "Sampling_Time (ms)": 0,
                "Judge_Score": "N/A",
                "Metric_Source (bench/srv)": "bench"
            })
        
        self.report_signal.emit(results)

    def _run_inference_mode(self):
        self.log_signal.emit(f"[추론] 하네스 실행 중: {len(self.dataset)} 개의 태스크")
        results = []
        
        engine_type = self.session.boot_config.engine
        model_name = self.session.boot_config.model_name
        
        if engine_type == "OLM":
            url = "http://127.0.0.1:11434/api/generate"
            try: requests.post("http://127.0.0.1:11434/api/pull", json={"name": model_name}, timeout=5)
            except: pass
        else:
            url = "http://127.0.0.1:8080/completion"

        for task in self.dataset:
            # 전력 추적
            pw_tracker = PowerTracker()
            if "Power" in self.session.run_mode:
                pw_tracker.start()

            start_time = time.time()
            text_acc = ""
            ttft = 0
            prompt_ms_per_t = 0
            sample_ms = 0
            prompt_n = 0
            predict_n = 0
            
            payload = {
                "model": model_name,
                "prompt": task.get('prompt', ''),
                "stream": True,
                "options": {"num_thread": self.session.stress_config.threads}
            }
            if engine_type == "ENG":
                payload = {"prompt": task.get('prompt', ''), "stream": True, "n_predict": 512}

            try:
                resp = requests.post(url, json=payload, stream=True)
                for line in resp.iter_lines():
                    if not line: continue
                    decoded = line.decode('utf-8')
                    
                    if engine_type == "ENG":
                        if not decoded.startswith("data: "): continue
                        decoded = decoded[6:]
                        if decoded.strip() == "[DONE]": break
                    
                    data = json.loads(decoded)
                    
                    if ttft == 0:
                        ttft = (time.time() - start_time) * 1000
                    
                    if engine_type == "OLM":
                        token = data.get('response', '')
                        text_acc += token
                        if data.get('done'): break
                    else:
                        token = data.get('content', '')
                        text_acc += token
                        if data.get('stop'):
                            t_info = data.get('timings', {})
                            prompt_n = t_info.get('prompt_n', 0)
                            predict_n = t_info.get('predicted_n', 0)
                            p_ms = t_info.get('prompt_ms', 0)
                            prompt_ms_per_t = round(p_ms / prompt_n, 2) if prompt_n > 0 else 0
                            sample_ms = t_info.get('sample_ms', 0)
                            break
            except Exception as e:
                self.log_signal.emit(f"[에러] {e}")

            duration = time.time() - start_time
            
            if "Power" in self.session.run_mode:
                pw_tracker.stop()

            avg_watts = pw_tracker.get_average_watts()
            score = self._call_llm_judge(task.get('prompt'), text_acc)
            tps_val = round(len(text_acc.split()) / duration, 2)
            
            results.append({
                "Model_Hash": model_name,
                "Quant_Method": "N/A",
                "Context_Size": self.session.stress_config.n_ctx,
                "Thread_Config": self.session.stress_config.threads,
                "TTFT (ms)": round(ttft, 1),
                "Prompt_Eval (ms/t)": prompt_ms_per_t,
                "Avg_GPU_W": round(avg_watts, 2),
                "Tokens_per_Joule": round(tps_val / avg_watts, 3) if avg_watts > 0 else 0,
                "E2E_Latency": round(duration, 2),
                "Generation (t/s)": tps_val,
                "Peak_VRAM_MB": 0,
                "System_Load": "INFERENCE",
                "Warm/Cold_Tag": "WARM",
                "Sampling_Time (ms)": round(sample_ms, 2),
                "Judge_Score": score,
                "Metric_Source (bench/srv)": "srv"
            })
            self.log_signal.emit(f"태스크 완료: {score} | {duration:.2f}초 | {avg_watts:.1f}W")

        self.report_signal.emit(results)
