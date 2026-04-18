import json
import time
import requests
from openai import OpenAI
from core.ollama_client import OllamaClient

class JudgeService:
    """[Engineering] 전역 판정관 서비스. 로컬/원격 모델을 사용하여 추론 결과를 평가합니다."""

    @staticmethod
    def call_llm_judge(prompt: str, response: str, stress_config, chunk_callback=None) -> dict:
        """
        AI 모델을 호출하여 프롬프트와 응답의 품질을 채점합니다.
        
        Args:
            prompt: 사용자 질문
            response: 모델의 답변
            stress_config: judge_model 및 system_prompt 정보를 담은 객체
            chunk_callback: 판정관의 Thought 과정을 스트리밍으로 전달할 콜백 함수 (Optional)
        """
        judge_model = stress_config.judge_model
        
        system_prompt = (
            "You are an expert AI Benchmark Judge. Evaluate the Quality of the USER_RESPONSE based on the PROMPT.\n"
            "Score from 0 to 10. Output MUST be valid JSON: {\"score\": 8, \"reason\": \"...\"}\n"
            "Language: Answer 'reason' in KOREAN."
        )
        user_content = f"PROMPT: {prompt}\nUSER_RESPONSE: {response}"

        # 1. 로컬 판정 (Ollama)
        if ":" in judge_model or "exaone" in judge_model.lower() or "qwen" in judge_model.lower():
            try:
                if chunk_callback:
                    chunk_callback(f"\n\n--- 🧠 Local Judge Thought ({judge_model}) ---\n")
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
                
                full_reason = ""
                resp = OllamaClient.chat_stream(judge_model, messages, options={"temperature": 0.0})
                
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        full_reason += content
                        if chunk_callback:
                            chunk_callback(content)
                
                # 강인한 JSON 추출 및 복구 로직 사용
                result_data = JudgeService._extract_json(full_reason)
                if result_data:
                    return result_data
                
                return {"score": 0, "reason": "JSON 복구 실패"}

            except Exception as e:
                if chunk_callback:
                    chunk_callback(f"\n[⚠ 판정 실패]: {e}")
                return {"score": 0, "reason": f"Local Judge Error: {e}"}

        # 2. 원격 판정 (OpenAI)
        else:
            try:
                # system_prompt 필드에 API Key가 들어있다고 가정 (현재 UI 구조상)
                api_key = stress_config.system_prompt 
                client = OpenAI(api_key=api_key)
                res = client.chat.completions.create(
                    model=judge_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    response_format={ "type": "json_object" }
                )
                return json.loads(res.choices[0].message.content)
            except Exception as e:
                return {"score": 0, "reason": f"Remote Judge Error: {e}"}

    @staticmethod
    def _extract_json(text: str) -> dict:
        """
        텍스트에서 JSON을 추출하고, 문법 오류(특히 따옴표 탈출 실패)를 최대한 복구합니다.
        """
        import re
        
        # 1. 시도: 중괄호 블록 추출
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return None
            
        json_str = match.group(0).strip()
        
        # 2. 시도: 표준 json.loads
        try:
            return json.loads(json_str)
        except:
            pass
            
        # 3. 시도: 'Dirty Repair' - 정규식 강제 추출
        try:
            score_match = re.search(r'"score":\s*(\d+)', json_str)
            score = int(score_match.group(1)) if score_match else 0
            
            # "reason": " 부터 마지막 " 까지 도려내기
            reason_match = re.search(r'"reason":\s*"(.*)"', json_str, re.DOTALL)
            reason = reason_match.group(1).strip() if reason_match else "Reason recovery failed"
            
            return {"score": score, "reason": reason}
        except:
            return None
