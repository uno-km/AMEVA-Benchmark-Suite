import os
import json
import threading
import requests
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from core.models_data import MODEL_CATALOGUE, CATEGORY_META
from core.constants import get_vault_abs_path, get_bit_vault_abs_path
from core.ollama_client import OllamaClient
from backend.routers.logs import broadcaster

router = APIRouter()

# 전역 다운로드 태스크 관리용
# 구조: { model_id: { "progress": int, "status": str, "cancel_event": threading.Event } }
active_downloads = {}
downloads_lock = threading.Lock()

class DownloadRequest(BaseModel):
    model_id: str
    is_ollama: bool = False
    engine_type: str = "ENG"

def download_gguf_worker(model_info: dict, dest_dir: str, cancel_event: threading.Event):
    model_id = model_info["id"]
    url = model_info["hf_url"]
    fname = model_info["filename"]
    path = os.path.join(dest_dir, fname)

    os.makedirs(dest_dir, exist_ok=True)
    broadcaster.log(f"[DL] 다운로드 시작: {fname}")

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 1024 * 512

        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if cancel_event.is_set():
                    broadcaster.log(f"[DL] 다운로드 취소됨: {fname}")
                    f.close()
                    if os.path.exists(path):
                        os.remove(path)
                    with downloads_lock:
                        active_downloads[model_id]["status"] = "cancelled"
                    return
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded / total * 100)
                    with downloads_lock:
                        active_downloads[model_id]["progress"] = pct

        broadcaster.log(f"[DL] 다운로드 완료: {fname}")
        with downloads_lock:
            active_downloads[model_id]["status"] = "success"
            active_downloads[model_id]["progress"] = 100
    except Exception as e:
        broadcaster.log(f"[DL] 다운로드 에러: {e}")
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
        with downloads_lock:
            active_downloads[model_id]["status"] = "failed"

def download_ollama_worker(model_info: dict, cancel_event: threading.Event):
    model_id = model_info["id"]
    tag = model_info["ollama_tag"]
    broadcaster.log(f"[OLM] 풀링 시작: {tag}")

    try:
        resp = OllamaClient.pull_model_stream(tag)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if cancel_event.is_set():
                broadcaster.log(f"[OLM] 풀링 취소됨: {tag}")
                with downloads_lock:
                    active_downloads[model_id]["status"] = "cancelled"
                return
            if not line:
                continue
            
            try:
                data = json.loads(line)
                status = data.get("status", "")
                total = data.get("total", 0)
                completed = data.get("completed", 0)
                
                if total > 0:
                    pct = int(completed / total * 100)
                    with downloads_lock:
                        active_downloads[model_id]["progress"] = pct
                elif "manifest" in status.lower():
                    with downloads_lock:
                        active_downloads[model_id]["progress"] = 1
                
                if status == "success":
                    broadcaster.log(f"[OLM] 완료: {tag}")
                    with downloads_lock:
                        active_downloads[model_id]["status"] = "success"
                        active_downloads[model_id]["progress"] = 100
                    return
            except:
                continue
    except Exception as e:
        broadcaster.log(f"[OLM] 에러: {e}")
        with downloads_lock:
            active_downloads[model_id]["status"] = "failed"

@router.get("/api/models")
def get_models():
    """모델 목록 및 각각의 다운로드 상태 반환"""
    vault_dir = get_vault_abs_path()
    bit_vault_dir = get_bit_vault_abs_path()
    
    ollama_models = [m["name"] for m in OllamaClient.list_local_models()]
    
    results = []
    for m in MODEL_CATALOGUE:
        # GGUF 파일이 로컬에 있는지 확인
        dest_dir = bit_vault_dir if m.get("category") == "Heavy" and "bitnet" in m["id"] else vault_dir
        gguf_path = os.path.join(dest_dir, m["filename"])
        gguf_installed = os.path.isfile(gguf_path)
        
        # Ollama 모델이 설치되어 있는지 확인
        ollama_installed = (m["ollama_tag"] in ollama_models) or (f"{m['ollama_tag']}:latest" in ollama_models)
        
        # 현재 다운로드 진행 정보
        dl_info = {"status": "idle", "progress": 0}
        with downloads_lock:
            if m["id"] in active_downloads:
                dl_info["status"] = active_downloads[m["id"]]["status"]
                dl_info["progress"] = active_downloads[m["id"]]["progress"]
        
        results.append({
            "id": m["id"],
            "display": m["display"],
            "category": m["category"],
            "tag": m["tag"],
            "desc": m["desc"],
            "min_ram_gb": m["min_ram_gb"],
            "size_gb": m["size_gb"],
            "filename": m["filename"],
            "ollama_tag": m["ollama_tag"],
            "gguf_installed": gguf_installed,
            "ollama_installed": ollama_installed,
            "download": dl_info
        })
    return {"models": results, "categories": CATEGORY_META}

@router.post("/api/models/download")
def download_model(req: DownloadRequest, background_tasks: BackgroundTasks):
    """모델 다운로드 요청 접수"""
    # 카탈로그에서 모델 정보 조회
    model_info = next((m for m in MODEL_CATALOGUE if m["id"] == req.model_id), None)
    if not model_info:
        raise HTTPException(status_code=404, detail="Model not found in catalogue")

    with downloads_lock:
        if req.model_id in active_downloads and active_downloads[req.model_id]["status"] == "downloading":
            return {"status": "already_downloading", "model_id": req.model_id}
        
        cancel_event = threading.Event()
        active_downloads[req.model_id] = {
            "progress": 0,
            "status": "downloading",
            "cancel_event": cancel_event
        }

    if req.is_ollama:
        t = threading.Thread(target=download_ollama_worker, args=(model_info, cancel_event))
    else:
        dest_dir = get_bit_vault_abs_path() if req.engine_type == "BIT" else get_vault_abs_path()
        t = threading.Thread(target=download_gguf_worker, args=(model_info, dest_dir, cancel_event))
        
    t.start()
    return {"status": "started", "model_id": req.model_id}

@router.post("/api/models/cancel")
def cancel_download(model_id: str):
    """다운로드 중단"""
    with downloads_lock:
        if model_id in active_downloads and active_downloads[model_id]["status"] == "downloading":
            active_downloads[model_id]["cancel_event"].set()
            return {"status": "cancelling", "model_id": model_id}
    return {"status": "not_active", "model_id": model_id}
