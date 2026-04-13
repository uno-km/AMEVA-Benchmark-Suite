import docker
import time
import os
from typing import Dict, Tuple

class MatrixEngine:
    def __init__(self):
        self.client = docker.from_env()
        self.container_name = "edgematrix_v4_arena"
        self.container = None
        self.current_cpus = 2.0
        self.is_throttled = False

    def nuke_existing_arena(self):
        try:
            self.client.containers.get(self.container_name).remove(force=True)
        except: pass

    def boot_matrix(self, config: Dict) -> Tuple[bool, str]:
        self.nuke_existing_arena()
        
        self.current_cpus = float(config.get("cpu_cores", 2.0))
        ram_str = f"{int(config.get('ram_mb', 2048))}m"
        engine_type = config.get("engine", "ollama")
        gpu_layers = int(config.get("gpu_layers", 0))

        models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
        os.makedirs(models_dir, exist_ok=True)
        volumes_config = {models_dir: {'bind': '/models', 'mode': 'rw'}}

        # [기능 4] GPU/NPU Device Requests 처리
        device_reqs = []
        if gpu_layers > 0:
            try:
                device_reqs = [docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])]
            except: pass

        try:
            if engine_type == "ollama":
                image = "ollama/ollama"
                cmd = None
            else:
                image = "ghcr.io/ggerganov/llama.cpp:light"
                # [기능 4] llama.cpp에 -ngl 옵션 동적 주입
                cmd = ["--server", "--host", "0.0.0.0", "--port", "11434", "-m", "/models/model.gguf", "-ngl", str(gpu_layers)]
            
            self.container = self.client.containers.run(
                image, command=cmd, name=self.container_name, detach=True,
                nano_cpus=int(self.current_cpus * 1e9), mem_limit=ram_str, memswap_limit=ram_str,
                ports={'11434/tcp': 11434}, volumes=volumes_config, device_requests=device_reqs
            )
            self.is_throttled = False
            time.sleep(4)
            return True, f"[{engine_type.upper()}] CPU {self.current_cpus}C, RAM {ram_str}, GPU Layers {gpu_layers} 격리 가동."
        except Exception as e:
            return False, str(e)

    def inject_chaos_monkey(self):
        """[기능 3] 카오스 몽키: 백그라운드에 인위적인 100% CPU 더미 연산 주입 (3초간)"""
        if self.container:
            try:
                # 쉘 스크립트로 3초간 무한 루프를 도는 악성(Chaos) 프로세스 실행
                cmd = "sh -c 'end=date +%s; end=; while [ date +%s -lt \ ]; do :; done'"
                self.container.exec_run(cmd, detach=True)
                return True
            except: return False
        return False

    def shutdown(self):
        self.nuke_existing_arena()
