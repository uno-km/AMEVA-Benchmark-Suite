import os

# [Vault Configuration]
VAULT_DIR_NAME = "ai_vault"
BIT_VAULT_DIR_NAME = "ai_bit_vault"
INTERNAL_VAULT_PATH = "/vault"

# [Network Configuration]
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
LLAMA_CPP_HOST = "127.0.0.1"
LLAMA_CPP_PORT = 8080

# [System Defaults]
DEFAULT_JUDGE_MODEL = "exaone3:7.8b"
DEFAULT_INFERENCE_MODEL = "qwen2.5:1.5b"

def get_vault_abs_path():
    """c:\\ameva\\models\\llm 경로를 반환합니다."""
    path = "c:\\ameva\\models\\llm"
    os.makedirs(path, exist_ok=True)
    return path

def get_bit_vault_abs_path():
    """c:\\ameva\\models\\bitnet 경로를 반환합니다."""
    path = "c:\\ameva\\models\\bitnet"
    os.makedirs(path, exist_ok=True)
    return path

