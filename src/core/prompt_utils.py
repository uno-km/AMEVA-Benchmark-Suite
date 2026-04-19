import re

class PromptFactory:
    """[V5.6] 모델 패밀리에 따른 최적의 프롬프트 템플릿을 생성합니다."""
    
    @staticmethod
    def detect_family(model_name: str) -> str:
        """모델 파일명에서 자동으로 가족군을 판별합니다."""
        name = model_name.lower()
        if "llama-3" in name or "llama3" in name:
            return "LLAMA3"
        if "exaone" in name:
            return "EXAONE"
        if "qwen" in name or "phi-3" in name or "yi-" in name:
            return "CHATML"
        if "gemma" in name:
            return "GEMMA"
        
        return "CHATML" # 기본값

    @staticmethod
    def wrap(prompt: str, model_name: str, system_prompt: str = "") -> str:
        """모델 패밀리에 맞게 프롬프트를 래핑합니다."""
        family = PromptFactory.detect_family(model_name)
        
        if not system_prompt:
            system_prompt = "You are a helpful and professional AI assistant."

        # 1. LLAMA3 (Official)
        if family == "LLAMA3":
            return (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                f"{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
                f"{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
            )
            
        # 2. EXAONE 3.5 (LGE Standard)
        elif family == "EXAONE":
            return (
                f"[입력]\n{system_prompt}\n\n{prompt}\n[출력]\n"
            )
            
        # 3. GEMMA (Google Standard)
        elif family == "GEMMA":
            return (
                f"<start_of_turn>user\n{system_prompt}\n\n{prompt}<end_of_turn>\n"
                f"<start_of_turn>assistant\n"
            )
            
        # 4. CHATML (Qwen, Phi-3, Yi, etc.)
        else:
            return (
                f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
                f"<|im_start|>user\n{prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

def get_stop_tokens(model_name: str) -> list:
    """모델별 중단 토큰을 정의합니다."""
    family = PromptFactory.detect_family(model_name)
    
    base_stops = ["<|im_end|>", "<|endoftext|>", "</s>"]
    if family == "LLAMA3":
        return base_stops + ["<|eot_id|>", "<|end_header_id|>"]
    if family == "EXAONE":
        return base_stops + ["[입력]", "[출력]"]
    if family == "GEMMA":
        return base_stops + ["<end_of_turn>"]
        
    return base_stops
