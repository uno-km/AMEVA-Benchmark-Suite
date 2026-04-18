import requests
import json
from core.constants import OLLAMA_BASE_URL

class OllamaClient:
    """Ollama API 통신을 전담하는 싱글톤 엔진입니다."""
    
    @staticmethod
    def list_local_models():
        """로컬에 이미 받아져 있는 Ollama 모델 목록을 반환합니다."""
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                return resp.json().get('models', [])
        except:
            pass
        return []

    @staticmethod
    def pull_model_stream(model_name: str):
        """Ollama 모델을 스트리밍 방식으로 다운로드합니다."""
        url = f"{OLLAMA_BASE_URL}/api/pull"
        return requests.post(url, json={"name": model_name}, stream=True)

    @staticmethod
    def chat_stream(model_name: str, messages: list, options: dict = None):
        """[Engineering] 추론 엔진용 채팅 스트리밍 인터페이스."""
        url = f"{OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "options": options or {}
        }
        return requests.post(url, json=payload, stream=True)

    @staticmethod
    def generate_streaming(model_name: str, prompt: str, options: dict = None):
        """단일 프롬프트 방식의 텍스트 생성 스트리밍."""
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": True,
            "options": options or {}
        }
        return requests.post(url, json=payload, stream=True)
