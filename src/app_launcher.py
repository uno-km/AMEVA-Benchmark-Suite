import os
import sys
import socket
import threading
import uvicorn
import webview

# Ensure local source packages load before any top-level workspace folders like /models
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def find_free_port():
    """임의의 빈 포트를 찾아 반환합니다."""
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def run_backend(port):
    """FastAPI 백엔드를 Uvicorn으로 가동합니다."""
    # backend.main 패키지를 임포트하여 uvicorn 실행
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, log_level="warning")

def main():
    port = find_free_port()
    
    # 메인 포트(port)를 기준으로 도커 호스트 포트를 port + 1로 설정하여 충돌 방지 및 격리 강화
    import core.constants as constants
    constants.LLAMA_CPP_PORT = port + 1
    
    # 1. 백엔드 스레드 가동
    backend_thread = threading.Thread(target=run_backend, args=(port,), daemon=True)
    backend_thread.start()
    
    # Uvicorn 서버가 완전히 뜰 때까지 잠시 대기
    import time
    time.sleep(1.0)
    
    # 2. PyWebview로 로컬 브라우저 창 띄우기
    url = f"http://127.0.0.1:{port}"
    print(f"[AMEVA Launcher] 웹앱 가동 주소: {url}")
    
    window = webview.create_window(
        title="AMEVA EDGE MATRIX v5.6",
        url=url,
        width=1280,
        height=820,
        resizable=True,
        min_size=(960, 680)
    )
    
    # 3. 창이 닫힐 때 Docker 컨테이너 및 프로세스 자원 완벽 해제 처리
    def on_closed():
        print("[AMEVA Launcher] 창 닫힘 감지. Docker 격리 공간 해제 중...")
        try:
            from backend.state import state
            state.engine.shutdown()
            print("[AMEVA Launcher] Docker 격리 자원 반납 완료.")
        except Exception as e:
            print(f"[AMEVA Launcher] 자원 해제 중 에러: {e}")
        finally:
            # Uvicorn 스레드 등을 포함하여 전역 프로세스 강제 종료
            os._exit(0)
            
    window.events.closed += on_closed
    
    # 루프 시작
    webview.start()

if __name__ == "__main__":
    main()
