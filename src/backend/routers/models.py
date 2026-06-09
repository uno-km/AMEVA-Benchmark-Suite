import os
import json
import threading
import requests
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from core.constants import get_vault_abs_path, get_bit_vault_abs_path
from core.ollama_client import OllamaClient
from backend.routers.logs import broadcaster
from backend.database import get_db_connection

router = APIRouter()

CATEGORY_META = {
    "Lite":   {"icon": "⚡", "color": "#10b981", "desc": "RAM 2~3GB  |  즉시 실행 가능  |  CPU 전용 환경 OK"},
    "Medium": {"icon": "⚙️", "color": "#3b82f6", "desc": "RAM 4~6GB  |  일상 노트북 권장  |  4코어 이상"},
    "Heavy":  {"icon": "🔥", "color": "#f59e0b", "desc": "RAM 8GB+   |  고성능 워크스테이션  |  GPU 권장"},
}

# 전역 다운로드 태스크 관리용
active_downloads = {}
downloads_lock = threading.Lock()

class DownloadRequest(BaseModel):
    model_id: str
    is_ollama: bool = False
    engine_type: str = "ENG"

class ModelRegisterSchema(BaseModel):
    model_id: str
    display_name: str
    category: str
    tag: str = ""
    description: str = ""
    min_ram_gb: float = 2.0
    size_gb: float = 0.0
    filename: str = ""
    ollama_tag: str = ""
    hf_url: str = ""

# ─────────────────────────────────────────────────────────────────────────────
# Workers
# ─────────────────────────────────────────────────────────────────────────────

def download_gguf_worker(model_info: dict, dest_dir: str, cancel_event: threading.Event):
    model_id = model_info["model_id"]
    url = model_info["hf_url"]
    fname = model_info["filename"]
    path = os.path.join(dest_dir, fname)

    if not url:
        broadcaster.log(f"[DL Error] 다운로드 URL이 지정되지 않았습니다: {fname}")
        with downloads_lock:
            active_downloads[model_id]["status"] = "failed"
        return

    os.makedirs(dest_dir, exist_ok=True)
    broadcaster.log(f"[DL] GGUF 다운로드 시작: {fname}")

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

        broadcaster.log(f"[DL] GGUF 다운로드 완료: {fname}")
        
        # 파일 크기 업데이트
        try:
            sz_gb = round(os.path.getsize(path) / (1024**3), 1)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE model_registry SET size_gb = ? WHERE model_id = ?;", (sz_gb, model_id))
            conn.commit()
            conn.close()
        except:
            pass

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
    model_id = model_info["model_id"]
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

# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/models")
def get_models():
    """모델 목록 스캔 및 각각의 다운로드 상태 반환"""
    vault_dir = get_vault_abs_path()
    bit_vault_dir = get_bit_vault_abs_path()
    
    # 1. 로컬 디렉토리 파일 스캔
    local_ggufs = []
    if os.path.exists(vault_dir):
        local_ggufs += [f for f in os.listdir(vault_dir) if f.endswith(".gguf")]
    
    local_bitnets = []
    if os.path.exists(bit_vault_dir):
        local_bitnets += [f for f in os.listdir(bit_vault_dir) if f.endswith(".gguf")]
        
    # 2. 로컬 Ollama 모델 조회
    ollama_models = []
    try:
        ollama_models = [m["name"] for m in OllamaClient.list_local_models()]
    except:
        pass

    # 3. DB 등록 모델 리스트 조회
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM model_registry;")
    db_models = [dict(r) for r in cursor.fetchall()]
    conn.close()

    results = []
    registered_filenames = set()
    registered_ollama_tags = set()

    # DB에 있는 등록 완료 모델들 검증
    for m in db_models:
        model_id = m["model_id"]
        filename = m.get("filename") or ""
        ollama_tag = m.get("ollama_tag") or ""
        
        if filename:
            registered_filenames.add(filename)
        if ollama_tag:
            registered_ollama_tags.add(ollama_tag)
            registered_ollama_tags.add(f"{ollama_tag}:latest")
            if ":" in ollama_tag:
                registered_ollama_tags.add(ollama_tag.split(":")[0])

        # 파일 경로 확인
        gguf_installed = False
        if filename:
            is_bitnet = (m["category"] == "Heavy" and "bitnet" in model_id) or ("bitnet" in filename.lower())
            dest_dir = bit_vault_dir if is_bitnet else vault_dir
            gguf_installed = os.path.isfile(os.path.join(dest_dir, filename))

        # Ollama 확인
        ollama_installed = False
        if ollama_tag:
            ollama_installed = (ollama_tag in ollama_models) or (f"{ollama_tag}:latest" in ollama_models)

        # 다운로드 현황 병합
        dl_info = {"status": "idle", "progress": 0}
        with downloads_lock:
            if model_id in active_downloads:
                dl_info["status"] = active_downloads[model_id]["status"]
                dl_info["progress"] = active_downloads[model_id]["progress"]

        results.append({
            "id": model_id,
            "display": m["display_name"],
            "category": m["category"],
            "tag": m["tag"] or "",
            "desc": m["description"] or "",
            "min_ram_gb": m["min_ram_gb"] or 2.0,
            "size_gb": m["size_gb"] or 0.0,
            "filename": filename,
            "ollama_tag": ollama_tag,
            "gguf_installed": gguf_installed,
            "ollama_installed": ollama_installed,
            "download": dl_info,
            "unregistered": False
        })

    # 4. 미등록 GGUF 파일 발견 시 리스트에 추가 (External)
    all_local_files = [("ENG", f, vault_dir) for f in local_ggufs] + [("BIT", f, bit_vault_dir) for f in local_bitnets]
    for engine_type, fname, fdir in all_local_files:
        if fname not in registered_filenames:
            size_bytes = os.path.getsize(os.path.join(fdir, fname))
            size_gb = round(size_bytes / (1024**3), 1)
            
            clean_id = fname.lower().replace(".gguf", "").replace("_", "-").replace(" ", "-")
            temp_id = f"ext-gguf-{clean_id}"
            
            results.append({
                "id": temp_id,
                "display": fname,
                "category": "Lite", 
                "tag": "📦 발견된 외부 GGUF",
                "desc": f"로컬 폴더에서 검색되었으나 DB에 등록되지 않은 모델 파일입니다. 정상 활용하려면 [등록하기]를 눌러 스펙을 기입하세요.",
                "min_ram_gb": 4.0,
                "size_gb": size_gb,
                "filename": fname,
                "ollama_tag": "",
                "gguf_installed": True,
                "ollama_installed": False,
                "download": {"status": "idle", "progress": 0},
                "unregistered": True,
                "engine_type": engine_type
            })

    # 5. 미등록 로컬 Ollama 모델 발견 시 리스트에 추가
    for o_model in ollama_models:
        if o_model not in registered_ollama_tags:
            clean_id = o_model.lower().replace(":", "-").replace(".", "-")
            temp_id = f"ext-ollama-{clean_id}"
            
            results.append({
                "id": temp_id,
                "display": o_model,
                "category": "Lite",
                "tag": "🦙 외부 Ollama",
                "desc": f"Ollama 내에 존재하나 DB에 등록되지 않은 모델입니다. [등록하기]를 눌러 스펙을 기입하세요.",
                "min_ram_gb": 4.0,
                "size_gb": 0.0,
                "filename": "",
                "ollama_tag": o_model,
                "gguf_installed": False,
                "ollama_installed": True,
                "download": {"status": "idle", "progress": 0},
                "unregistered": True,
                "engine_type": "OLM"
            })

    return {"models": results, "categories": CATEGORY_META}

@router.post("/api/models/register")
def register_model(req: ModelRegisterSchema):
    """신규 모델 수동 등록 / 미등록 외부 모델 스펙 추가"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM model_registry WHERE model_id = ?;", (req.model_id,))
        if cursor.fetchone():
            cursor.execute("""
            UPDATE model_registry
            SET display_name = ?, category = ?, tag = ?, description = ?, min_ram_gb = ?, size_gb = ?, filename = ?, ollama_tag = ?, hf_url = ?
            WHERE model_id = ?;
            """, (
                req.display_name, req.category, req.tag, req.description,
                req.min_ram_gb, req.size_gb, req.filename, req.ollama_tag, req.hf_url, req.model_id
            ))
            conn.commit()
            return {"status": "updated", "model_id": req.model_id}
        else:
            cursor.execute("""
            INSERT INTO model_registry (
                model_id, display_name, category, tag, description, min_ram_gb, size_gb, filename, ollama_tag, hf_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                req.model_id, req.display_name, req.category, req.tag, req.description,
                req.min_ram_gb, req.size_gb, req.filename, req.ollama_tag, req.hf_url
            ))
            conn.commit()
            return {"status": "registered", "model_id": req.model_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during registration: {e}")
    finally:
        conn.close()

@router.post("/api/models/download")
def download_model(req: DownloadRequest, background_tasks: BackgroundTasks):
    """모델 다운로드 요청 접수 (DB 쿼리 적용)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM model_registry WHERE model_id = ?;", (req.model_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Model specifications not found in DB registry")
    
    model_info = dict(row)

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

@router.get("/api/models/installed-ollama")
def get_installed_ollama_models():
    """로컬 Ollama에 설치된 모델 목록 조회"""
    try:
        models = OllamaClient.list_local_models()
        return {"models": [m["name"] for m in models]}
    except Exception as e:
        return {"models": [], "error": str(e)}
