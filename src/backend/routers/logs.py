import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

class LogBroadcaster:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.queue = asyncio.Queue()

    async def register(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def unregister(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    def log(self, message: str, log_type: str = "sys"):
        """임의의 스레드에서 안전하게 로그를 추가할 수 있도록 이벤트 루프를 통해 큐에 삽입"""
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(
                self.queue.put_nowait, 
                {"type": log_type, "text": message}
            )
        except RuntimeError:
            pass

    async def start_broadcast_loop(self):
        while True:
            item = await self.queue.get()
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(item)
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                self.unregister(conn)
            self.queue.task_done()

broadcaster = LogBroadcaster()

broadcast_task = None

def start_broadcaster_task():
    global broadcast_task
    if broadcast_task is None:
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

