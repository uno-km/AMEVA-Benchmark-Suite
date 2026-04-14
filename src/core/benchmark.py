
import datetime
import time
import requests
import json
import re
from openai import OpenAI
from PySide6.QtCore import QThread, Signal

DEFAULT_HARNESS = [
    # --- KOREAN SET (논리, 문법, 코딩, 환각) ---
    {"task": "K-Math", "prompt": "영희는 사과 12개, 철수는 영희의 절반보다 2개 더 많고, 민수는 철수보다 3개 적어. 총 합계는?", "expected_regex": r"23", "eval_type": "regex"},
    {"task": "K-Grammar", "prompt": "'나 어제 밥 먹다가 이빨 빠졌어'를 비즈니스 극존칭으로 바꿔.", "eval_type": "llm_judge"},
    {"task": "K-Coding", "prompt": "리스트에서 짝수만 골라 제곱 후 내림차순 정렬하는 파이썬 함수를 짜줘.", "eval_type": "llm_judge"},
    {"task": "K-Hallucination", "prompt": "세종대왕의 맥북 던짐 사건에 대해 자세히 설명해줘.", "expected_regex": r"(없습니다|사실이|허구|데이터가)", "eval_type": "regex"},

    # --- ENGLISH SET (Math, Formal, Logic) ---
    {"task": "E-Math", "prompt": "150 dollars with 20% discount and then 10% tax added. Final price?", "expected_regex": r"132", "eval_type": "regex"},
    {"task": "E-Formal", "prompt": "Rewrite 'I can't make it to the meeting' into a formal business email.", "eval_type": "llm_judge"},
    {"task": "E-Logic", "prompt": "I have 3 brothers. Each has one sister. How many sisters do I have?", "expected_regex": r"(1|one)", "eval_type": "regex"},

    # --- K-E MIXED SET (Bilingual Reasoning) ---
    {"task": "K-E-Mixed", "prompt": "'The deadline has been moved up to tomorrow'를 한글로 번역하고, 기한이 '당겨졌는지' 혹은 '미뤄졌는지' 판단해서 한글로 답한 뒤, 마감일을 뜻하는 영어 단어를 써줘.", "eval_type": "llm_judge"}
]

class SystemMonitor(QThread):
    stats_signal = Signal(float, float, float, float, float) # cpu, mem, mem_lim, power, battery%
    blackout_signal = Signal(bool)

    def __init__(self, container, engine):
        super().__init__()
        
        self.container = container
        self.engine = engine
        self.is_running = True
        
        # 4000mAh 모바일 배터리 = 약 54,000 Joules
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
                
                pw = (cpu_p / 100.0) * 15.0
                
                current_time = time.time()
                elapsed = current_time - last_time
                last_time = current_time
                
                consumed_joules = pw * elapsed * 100.0 
                self.remaining_joules -= consumed_joules
                battery_percent = max(0.0, (self.remaining_joules / self.total_joules_capacity) * 100.0)

                self.stats_signal.emit(cpu_p, mem_u, mem_l, pw, battery_percent)

                if battery_percent <= 0 and not self.is_blackout:
                    self.is_blackout = True
                    self.blackout_signal.emit(True)
            except: pass
            time.sleep(0.2)
            
    def stop(self): self.is_running = False

class BenchmarkRunner(QThread):
    log_signal = Signal(str)
    report_signal = Signal(list)

    def __init__(self, model_name, custom_dataset=None, judge_key="", engine_type="OLM"):
        super().__init__()
        self.model_name = model_name
        self.dataset = custom_dataset if custom_dataset else DEFAULT_HARNESS
        self.judge_key = judge_key
        self.engine_type = engine_type # 상태 저장 완료!
        
        if custom_dataset:
            self.dataset = custom_dataset
        else:
            self.dataset = self._load_harness_from_csv()
            
    def _load_harness_from_csv(self):
        fname = "harness_v4.csv"
        data = []
        try:
            with open(fname, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
        except:
            # 파일이 없으면 아쉬운 대로 빈 리스트라도...
            return []
        return data
    
    def _call_llm_judge(self, prompt, response_text):
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
        
        # =================================================================
        # ✅ [마법의 로직] 현재 켜져 있는 도커 엔진 자동 감지 (포트 스캐닝)
        # =================================================================
        if self.engine_type == "ENG":
            self.log_signal.emit(" 📡 [통신] llama.cpp 엔진 모드 (포트 8080) 동작 확인.")
        else:
            self.log_signal.emit(" 📡 [통신] Ollama 엔진 모드 (포트 11434) 동작 확인.")
            try: requests.post("http://127.0.0.1:11434/api/pull", json={"name": self.model_name}, timeout=120)
            except: pass

        for task in self.dataset:
            current_time_str = datetime.datetime.now().strftime("%H:%M:%S")
            # 1. 변수 초기화 (루프 밖에서 해야 유실 안 됨!)
            prompt_n = 0
            predict_n = 0
            text_acc = ""
            start_time = time.time()
            first_token_time, ttft, tps = 0, 0, 0
            
            self.log_signal.emit(f"\n [Task] {task.get('task', 'Custom')}")
            
            # =================================================================
            # ✅ 엔진 종류에 맞춰 API 주소와 질문(Payload) 포맷을 다르게 세팅!
            # =================================================================
            if self.engine_type == "ENG":
                url = "http://127.0.0.1:8080/completion"
                full_prompt = f"{task.get('system', '')}\n\n{task.get('prompt', '')}"
                payload = {"prompt": full_prompt, "n_predict": 512, "stream": True}
            else:
                url = "http://127.0.0.1:11434/api/generate"
                payload = {"model": self.model_name, "system": task.get("system", ""), "prompt": task.get("prompt", ""), "stream": True}
            
            try:
                resp = requests.post(url, json=payload, stream=True)
                for line in resp.iter_lines():
                    if not line: continue
                    decoded_line = line.decode('utf-8')
                                       
                    if first_token_time == 0:
                        first_token_time = time.time()
                        ttft = first_token_time - start_time
                        self.log_signal.emit(f"   TTFT 감지: {ttft:.3f}초")
                    
                    # =================================================================
                    # ✅ 파싱 로직 분기 (Ollama의 JSON vs llama.cpp의 SSE)
                    # =================================================================

                    if self.engine_type == "ENG":
                        if decoded_line.startswith("data: "):
                            json_str = decoded_line[6:]
                            if json_str.strip() == "[DONE]": break
                            data = json.loads(json_str)
                            
                            if 'content' in data:
                                token = data['content']
                                text_acc += token
                                # ✅ [UI 개선] 토큰 실황을 '시스템 콘솔'로 전송 (접두사 추가)
                                # MainController에서 이 접두사를 보고 2번 탭으로 보낼 겁니다.
                                self.log_signal.emit(f"SYS_RAW > {token}")

                            if data.get('stop'):
                                timings = data.get('timings', {})
                                tps = timings.get('predicted_per_second', 0)
                                # ✅ [데이터 보존] 변수에 값 할당!
                                prompt_n = timings.get('prompt_n', 0)
                                predict_n = timings.get('predicted_n', 0)
                                break
                    else:
                        data = json.loads(decoded_line)
                        if 'response' in data: text_acc += data['response']
                        if data.get('done'):
                            ed = data.get('eval_duration', 0)
                            if ed > 0: tps = data.get('eval_count', 0) / (ed / 1e9)
                            break
                            
            except Exception as e: 
                text_acc = f"통신 에러: {str(e)}"
                self.log_signal.emit(f"   [에러] {text_acc}")

            duration = time.time() - start_time
            
            # 평가 로직
            eval_result = ""
            if task.get("eval_type") == "llm_judge":
                self.log_signal.emit("   LLM Judge 채점 중...")
                eval_result = self._call_llm_judge(task.get("prompt"), text_acc)
            else:
                is_match = bool(re.search(task.get("expected_regex", ".*"), text_acc))
                eval_result = "PASS" if is_match else "FAIL"
            
            self.log_signal.emit(f"   결과: {eval_result} (총 소요시간: {duration:.2f}초 | 속도: {tps:.2f} TPS)")
            
            blackout_status = "O" if getattr(self, 'current_blackout_state', False) else "X"

            # 벤치마크 루프가 끝나는 시점에 실행되는 최종 데이터 박제
            results.append({
                "Timestamp": current_time_str,
                "Task": task.get('task', 'Custom'), 
                "Judge_Result": eval_result,         # ✅ 원본의 채점 결과 복구!
                "TTFT(s)": round(ttft, 3), 
                "Total_Time(s)": round(duration, 2), # ✅ 원본 변수 사용
                "TPS": round(tps, 2), 
                "Tokens_Sent": prompt_n,             # 🆕 추가: 입력 토큰 수
                "Tokens_Gen": predict_n,             # 🆕 추가: 생성 토큰 수
                "Blackout_During_Test": blackout_status, # ✅ 원본 키 이름 유지
                "Full_Response": text_acc            # 🆕 추가: 40자 제한 없는 답변 전문
            })
            time.sleep(1)

        self.log_signal.emit("\n Eval 파이프라인 검증 완료.")
        self.report_signal.emit(results)