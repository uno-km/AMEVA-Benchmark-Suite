import asyncio
import psutil
import subprocess
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

def get_gpu_telemetry():
    """NVIDIA GPU 상태 수집 (nvidia-smi 파싱 또는 GPUtil 활용)"""
    stats = {
        "gpu_percent": 0.0,
        "vram_used_mb": 0.0,
        "vram_total_mb": 0.0,
        "temp_c": 0,
        "power_w": 0.0
    }
    
    # 1. nvidia-smi를 사용해 정밀 정보 추출 시도
    try:
        # query-gpu: utilization.gpu, memory.used, memory.total, temperature.gpu, power.draw
        cmd = [
            "nvidia-smi", 
            "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw", 
            "--format=csv,noheader,nounits"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        parts = res.stdout.strip().split(',')
        if len(parts) >= 5:
            stats["gpu_percent"] = float(parts[0].strip())
            stats["vram_used_mb"] = float(parts[1].strip())
            stats["vram_total_mb"] = float(parts[2].strip())
            stats["temp_c"] = int(parts[3].strip())
            stats["power_w"] = float(parts[4].strip())
            return stats
    except Exception:
        pass

    # 2. GPUtil 폴백 시도
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            stats["gpu_percent"] = round(gpu.load * 100, 1)
            stats["vram_used_mb"] = round(gpu.memoryUsed, 1)
            stats["vram_total_mb"] = round(gpu.memoryTotal, 1)
            stats["temp_c"] = int(gpu.temperature)
            return stats
    except Exception:
        pass

    return stats

import platform
import os

def get_cpu_temp():
    temp_c = 0.0
    # 1. psutil 시도
    try:
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps and 'coretemp' in temps:
                temp_c = temps['coretemp'][0].current
            elif temps:
                temp_c = list(temps.values())[0][0].current
    except Exception:
        pass
        
    # 2. Linux 파일 시스템 직접 접근 (제안해주신 방식)
    if temp_c == 0.0 and platform.system() == "Linux":
        thermal_path = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(thermal_path):
            try:
                with open(thermal_path, "r") as f:
                    temp_raw = f.read().strip()
                    temp_c = float(temp_raw) / 1000.0
            except Exception:
                pass
                
    return temp_c

async def get_system_stats():
    # CPU & RAM 수집
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    ram_used_gb = round((mem.total - mem.available) / (1024**3), 2)
    ram_total_gb = round(mem.total / (1024**3), 2)
    
    # 온도 및 GPU 수집
    cpu_temp_c = get_cpu_temp()
    gpu_stats = get_gpu_telemetry()
    
    # 최종 리턴
    return {
        "cpu": cpu_percent,
        "cpu_temp_c": cpu_temp_c,
        "ram": ram_used_gb,
        "ram_total": ram_total_gb,
        **gpu_stats
    }

@router.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            stats = await get_system_stats()
            await websocket.send_json(stats)
            await asyncio.sleep(1.0)  # 1초 주기로 스트리밍
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
