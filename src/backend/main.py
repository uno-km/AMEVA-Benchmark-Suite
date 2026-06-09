import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.routers.telemetry import router as telemetry_router
from backend.routers.logs import router as logs_router, broadcaster
from backend.routers.models import router as models_router
from backend.routers.benchmark import router as benchmark_router

app = FastAPI(title="AMEVA Benchmark Suite API", version="5.6")

# CORS 활성화
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(telemetry_router)
app.include_router(logs_router)
app.include_router(models_router)
app.include_router(benchmark_router)

# 정적 파일 서빙 등록
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

@app.on_event("startup")
async def startup_event():
    """앱 시작 시 메인 이벤트 루프를 브로드캐스터에 등록하고 브로드캐스트 루프 태스크를 시작합니다."""
    loop = asyncio.get_running_loop()
    broadcaster.set_loop(loop)
    from backend.routers.logs import start_broadcaster_task
    start_broadcaster_task()
    broadcaster.log("✅ AMEVA 벤치마크 시스템 초기화 완료. 커널 가동 명령 대기 중.", "sys")

@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI 정상 종료 시 Docker 격리 공간을 해제하고 자원을 반납합니다."""
    broadcaster.log("⚠️ AMEVA 백엔드 시스템 종료 중... Docker 자원 반납 진행.", "sys")
    try:
        from backend.state import state
        if state.engine:
            state.engine.shutdown()
        broadcaster.log("✅ Docker 격리 자원 반납 완료.", "sys")
    except Exception as e:
        print(f"[Shutdown Error] {e}")
