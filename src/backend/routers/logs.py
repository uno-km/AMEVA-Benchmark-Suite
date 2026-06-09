import asyncio
import json
import threading
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

class LogBroadcaster:
    """
    WebSocket 브로드캐스터.
    - 모든 스레드(백그라운드 워커 포함)에서 안전하게 .log() 호출 가능.
    - 이벤트 루프가 아직 시작 안 됐을 경우를 위한 pending_queue 백업.
    """
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._lock = threading.Lock()
        # 이벤트 루프 초기화 전에 쌓인 로그 임시 보관
        self._pending: list[dict] = []

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """FastAPI 앱 startup 시 메인 이벤트 루프를 등록합니다."""
        with self._lock:
            self._loop = loop
            self._queue = asyncio.Queue()
            # 루프가 등록되기 전에 쌓인 pending 로그를 큐에 삽입
            for item in self._pending:
                loop.call_soon_threadsafe(self._queue.put_nowait, item)
            self._pending.clear()

    async def register(self, websocket: WebSocket):
        await websocket.accept()
        with self._lock:
            self.active_connections.append(websocket)

    def unregister(self, websocket: WebSocket):
        with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    def log(self, message: str, log_type: str = "sys"):
        """임의의 스레드에서 안전하게 호출 가능한 로그 메서드."""
        item = {"type": log_type, "text": message}
        with self._lock:
            if self._loop is not None and self._queue is not None:
                try:
                    self._loop.call_soon_threadsafe(self._queue.put_nowait, item)
                except RuntimeError:
                    # 루프가 종료된 경우 - pending에 넣어도 의미없으므로 무시
                    pass
            else:
                # 루프가 아직 없으면 pending에 쌓아둠
                self._pending.append(item)

    async def start_broadcast_loop(self):
        while True:
            item = await self._queue.get()
            disconnected = []
            with self._lock:
                connections = list(self.active_connections)
            for connection in connections:
                try:
                    await connection.send_json(item)
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                self.unregister(conn)
            self._queue.task_done()


broadcaster = LogBroadcaster()
broadcast_task = None


def start_broadcaster_task():
    global broadcast_task
    if broadcast_task is None or broadcast_task.done():
        broadcast_task = asyncio.create_task(broadcaster.start_broadcast_loop())


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await broadcaster.register(websocket)
    start_broadcaster_task()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.unregister(websocket)
    except Exception:
        broadcaster.unregister(websocket)
