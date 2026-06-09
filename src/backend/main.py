from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.routers.telemetry import router as telemetry_router
from backend.routers.logs import router as logs_router
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
# src/static 폴더의 위치를 절대경로로 확보
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

@app.on_event("startup")
async def startup_event():
    # 백그라운드 스레드 및 큐 준비
    from backend.routers.logs import start_broadcaster_task
    start_broadcaster_task()
