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
                
                # 정규식으로 JSON만 추출 (모델이 마크다운 블록을 뱉을 수 있음)
                json_match = JudgeService._extract_json(full_reason)
                if json_match:
                    return json.loads(json_match)
                return {"score": 0, "reason": "JSON 파싱 실패"}

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
    def _extract_json(text: str) -> str:
        """텍스트에서 첫 번째 {...} 블록을 안전하게 추출합니다."""
        import re
        # 마크다운 블록 등을 고려하여 가장 바깥쪽 중괄호 쌍을 찾음
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
             return match.group(1).strip()
        return None
