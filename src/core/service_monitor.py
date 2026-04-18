import time
import docker
import subprocess
from ui.qt_bridge import *
from core.ollama_client import OllamaClient

class ServiceMonitorThread(QThread):
    """
    [Engineering] 백그라운드 서비스 모니터링 스레드.
    Docker 데몬 및 Ollama API의 상태를 주기적으로 체크합니다.
    """
    status_updated = Signal(str, bool, str)  # (service_name, is_online, error_msg)

    def __init__(self, interval: int = 5):
        super().__init__()
        self._interval = interval
        self._running = True

    def run(self):
        while self._running:
            # 1. Docker 체크
            self._check_docker()
            # 2. Ollama 체크
            self._check_ollama()
            
            time.sleep(self._interval)

    def stop(self):
        self._running = False
        self.wait()

    def _check_docker(self):
        try:
            client = docker.from_env()
            client.ping()
            self.status_updated.emit("docker", True, "Docker Desktop is running.")
        except Exception as e:
            self.status_updated.emit("docker", False, f"Docker Error: {str(e)}")

    def _check_ollama(self):
        try:
            # OllamaClient 활용하여 태그 리스트 체크
            models = OllamaClient.list_local_models()
            self.status_updated.emit("ollama", True, f"Ollama API is serving ({len(models)} models found).")
        except Exception as e:
            self.status_updated.emit("ollama", False, "Ollama is not responding.")

    def attempt_start(self, service_name: str):
        """서비스 시작 시도 (Windows 전용 기본 경로)"""
        if service_name == "docker":
            path = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
            try:
                subprocess.Popen([path], start_new_session=True)
                return True, "Starting Docker Desktop..."
            except Exception as e:
                return False, f"Failed to start Docker: {e}"
        
        elif service_name == "ollama":
            try:
                # ollama serve는 백그라운드 실행이 필요함
                subprocess.Popen(["ollama", "serve"], start_new_session=True, 
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                return True, "Starting Ollama serve..."
            except Exception as e:
                return False, f"Failed to start Ollama: {e}"
        
        return False, "Unknown service"
