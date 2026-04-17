"""
prompt_utils.py - LLM 프롬프트 서순 및 템플릿 관리 (V5.6)
비정형 텍스트를 ChatML 등의 정형화된 템플릿으로 변환합니다.
"""

def format_chatml(prompt: str, system_prompt: str = "") -> str:
    """
    텍스트를 ChatML (<|im_start|>) 형식으로 변환합니다.
    Qwen, Llama3, Phi-3 등 최신 모델 사양에 최적화되어 있습니다.
    """
    if not system_prompt:
        system_prompt = "You are a helpful assistant."
        
    chatml = (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{prompt}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    return chatml

def get_stop_tokens(engine_type: str) -> list:
    """엔진별 중단 토큰 정의"""
    if engine_type == "OLM":
        return ["<|im_end|>", "<|endoftext|>", "</s>"]
    return ["<|im_end|>", "<|endoftext|>", "assistant:"]
