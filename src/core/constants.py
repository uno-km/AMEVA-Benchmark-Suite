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

def get_filename_by_id(model_id: str) -> str:
    """ID 혹은 ollama_tag를 기반으로 DB를 조회하여 GGUF 파일명을 찾습니다."""
    import sqlite3
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ameva_benchmark.db"))
    if not os.path.exists(db_path):
        if model_id.endswith(".gguf"):
            return model_id
        return f"{model_id}.gguf"
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM model_registry WHERE model_id = ? OR ollama_tag = ?;", (model_id, model_id))
        row = cursor.fetchone()
        conn.close()
        if row and row["filename"]:
            return row["filename"]
    except Exception:
        pass
    if model_id.endswith(".gguf"):
        return model_id
    return f"{model_id}.gguf"

