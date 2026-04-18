import os

# [Vault Configuration]
VAULT_DIR_NAME = "ai_vault"
INTERNAL_VAULT_PATH = "/vault"

# [Network Configuration]
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
LLAMA_CPP_HOST = "127.0.0.1"
LLAMA_CPP_PORT = 8080

# [System Defaults]
DEFAULT_JUDGE_MODEL = "exaone3:7.8b"
DEFAULT_INFERENCE_MODEL = "qwen2.5:1.5b"

def get_vault_abs_path():
    """프로젝트 루트 기준 ai_vault의 절대 경로를 반환합니다."""
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", VAULT_DIR_NAME)
    )
