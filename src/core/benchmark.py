import time
import requests
import json
import re
from openai import OpenAI
from PySide6.QtCore import QThread, Signal

DEFAULT_HARNESS = [
    {"task": "Coding_Algorithm", "system": "You are a Python Expert.", "prompt": "Write a python function to reverse a string.", "eval_type": "llm_judge"},
    {"task": "Math_Logic", "system": "Think step-by-step.", "prompt": "x=3, y=4, calc x*y+2.", "expected_regex": r"14", "eval_type": "regex"}
]

class SystemMonitor(QThread):
    stats_signal = Signal(float, float, float, float, float) # cpu, mem, mem_lim, power, battery%
    blackout_signal = Signal(bool)

    def __init__(self, container, engine):
        super().__init__()
        self.container = container
        self.engine = engine
        self.is_running = True
        
        # [기능 2] 배터리 모델링
        # 4000mAh 모바일 배터리 = 약 54,000 Joules. 
        # 단, 벤치마크 시간(몇 분) 내에 시각적 변화를 보기 위해 배터리 소모율을 100배 가속(Accelerated Drain)합니다.
        self.total_joules_capacity = 54000.0
        self.remaining_joules = 54000.0
        self.is_blackout = False

    def run(self):
        last_time = time.time()
        while self.is_running and self.container:
            try:
                stats = self.container.stats(stream=False)
                mem_u = stats['memory_stats'].get('usage', 0) / (1024 * 1024)
                mem_l = stats['memory_stats'].get('limit', 1) / (1024 * 1024)
                
                cpu_d = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                sys_d = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                cpu_p = (cpu_d / sys_d) * stats['cpu_stats']['online_cpus'] * 100.0 if sys_d > 0 else 0.0
                
                # 전력 계산 (TDP 15W 기준)
                pw = (cpu_p / 100.0) * 15.0
                
                # 배터리 소모 계산 (가속 계수 x100)
                current_time = time.time()
                elapsed = current_time - last_time
                last_time = current_time
                
                consumed_joules = pw * elapsed * 100.0 
                self.remaining_joules -= consumed_joules
                battery_percent = max(0.0, (self.remaining_joules / self.total_joules_capacity) * 100.0)

                self.stats_signal.emit(cpu_p, mem_u, mem_l, pw, battery_percent)

                # 블랙아웃 트리거 (단, 테스트는 멈추지 않음)
                if battery_percent <= 0 and not self.is_blackout:
                    self.is_blackout = True
                    self.blackout_signal.emit(True)

            except: pass
            time.sleep(0.5)

    def stop(self): self.is_running = False

class BenchmarkRunner(QThread):
    log_signal = Signal(str)
    report_signal = Signal(list)

    def __init__(self, model_name, custom_dataset=None, judge_key=""):
        super().__init__()
        self.model_name = model_name
        self.dataset = custom_dataset if custom_dataset else DEFAULT_HARNESS
        self.judge_key = judge_key

    def _call_llm_judge(self, prompt, response_text):
        """[기능 1] OpenAI API를 활용한 LLM-as-a-Judge 정성 평가"""
        if not self.judge_key:
            return "SKIPPED (No API Key)"
        try:
            client = OpenAI(api_key=self.judge_key)
            judge_prompt = f"Evaluate if this response perfectly answers the prompt.\nPrompt: {prompt}\nResponse: {response_text}\nOutput ONLY 'PASS' or 'FAIL'."
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": judge_prompt}],
                max_tokens=10, temperature=0.0
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"JUDGE_ERROR: {str(e)}"

    def run(self):
        self.log_signal.emit(f" [{self.model_name}] v4.0 파이프라인 가동 (LLM Judge & Chaos Ready)...")
        results = []
        try: requests.post("http://127.0.0.1:11434/api/pull", json={"name": self.model_name}, timeout=120)
        except: pass

        for task in self.dataset:
            self.log_signal.emit(f"\n [Task] {task.get('task', 'Custom')}")
            start_time = time.time()
            first_token_time, ttft, tps = 0, 0, 0
            text_acc = ""
            
            payload = {"model": self.model_name, "system": task.get("system", ""), "prompt": task.get("prompt", ""), "stream": True, "options": task.get("params", {})}
            
            try:
                resp = requests.post("http://127.0.0.1:11434/api/generate", json=payload, stream=True)
                for line in resp.iter_lines():
                    if line:
                        if first_token_time == 0:
                            first_token_time = time.time()
                            ttft = first_token_time - start_time
                            self.log_signal.emit(f"   TTFT 감지: {ttft:.3f}초")

                        data = json.loads(line.decode('utf-8'))
                        if 'response' in data: text_acc += data['response']
                        if data.get('done'):
                            ed = data.get('eval_duration', 0)
                            if ed > 0: tps = data.get('eval_count', 0) / (ed / 1e9)
                            break
            except Exception as e: text_acc = str(e)

            duration = time.time() - start_time
            
            # 평가 로직 분기
            eval_result = ""
            if task.get("eval_type") == "llm_judge":
                self.log_signal.emit("   LLM Judge 채점 중...")
                eval_result = self._call_llm_judge(task.get("prompt"), text_acc)
            else:
                is_match = bool(re.search(task.get("expected_regex", ".*"), text_acc))
                eval_result = "PASS" if is_match else "FAIL"
            
            self.log_signal.emit(f"   결과: {eval_result} (총 소요시간: {duration:.2f}초 | 속도: {tps:.2f} TPS)")
            
            # [기능 2 연계] 시스템 블랙아웃 상태면 리포트에 기록 (하지만 루프는 계속 돔)
            blackout_status = "O" if getattr(self, 'current_blackout_state', False) else "X"

            results.append({
                "Task": task.get('task', 'Custom'), "Judge_Result": eval_result,
                "TTFT(s)": round(ttft, 3), "Total_Time(s)": round(duration, 2), "TPS": round(tps, 2),
                "Blackout_During_Test": blackout_status,
                "Output_Preview": text_acc[:40].replace('\n', ' ')
            })
            time.sleep(1)

        self.log_signal.emit("\n Eval 파이프라인 검증 완료.")
        self.report_signal.emit(results)
