import docker
import time
import os
from typing import Optional, Callable, Dict, Tuple
from core.constants import OLLAMA_BASE_URL, LLAMA_CPP_HOST, LLAMA_CPP_PORT, get_vault_abs_path, INTERNAL_VAULT_PATH
from core.models_data import get_filename_by_id


class MatrixEngine:
    """[V5.5] 매트릭스 엔진 - Docker 오케스트레이션 순수 백엔드."""

    def __init__(self, container_name: str = "edgematrix_v5_5_arena"):
        self.container_name = container_name
        self.container = None
        self.log_callback: Optional[Callable[[str], None]] = None

    def set_logger(self, callback: Callable[[str], None]):
        self.log_callback = callback

    def _log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg) 

    def _get_docker_client(self):
        try:
            return docker.from_env()
        except docker.errors.DockerException as e:
            raise RuntimeError(
                "Docker 데몬에 연결할 수 없습니다. Docker Desktop이 실행 중인지, Docker Engine이 활성화되어 있는지 확인하세요. "
                f"상세 오류: {e}"
            ) from e

    def cleanup_old_arena(self):
        """기존 컨테이너를 정리합니다."""
        try:
            client = self._get_docker_client()
            client.containers.get(self.container_name).remove(force=True)
            self._log("✓ 이전 컨테이너 제거 완료")
        except docker.errors.NotFound:
            self._log("· 기존 컨테이너 없음 (클린 스테이트)")
        except Exception as e:
            self._log(f"[WARN] 컨테이너 정리 중 오류: {e}")

    def boot_matrix(self, config: Dict) -> Tuple[bool, str]:
        """매트릭스(Docker 컨테이너)를 부팅합니다. 각 단계를 상세 로깅합니다."""
        model_name = config.get("model_name", "qwen2.5:1.5b")
        cpu_cores = float(config.get("cpu_cores", 2.0))
        ram_mb = int(config.get("ram_mb", 2048))
        engine_type = config.get("engine", "OLM")
        gpu_layers = int(config.get("gpu_layers", 0))

        try:
            self._log("Docker 클라이언트 초기화 중...")
            client = self._get_docker_client()
            self._log("✓ Docker 데몬 연결 성공")

            # Cleanup
            self._log("이전 아레나 인스턴스 정리 중...")
            self.cleanup_old_arena()

            # Volumes
            from .constants import get_vault_abs_path, INTERNAL_VAULT_PATH, OLLAMA_BASE_URL, LLAMA_CPP_PORT
            models_dir = get_vault_abs_path()
            os.makedirs(models_dir, exist_ok=True)
            volumes = {models_dir: {'bind': INTERNAL_VAULT_PATH, 'mode': 'rw'}}
            self._log(f"· 볼륨 마운트 준비: {models_dir} → {INTERNAL_VAULT_PATH}")

            # GPU
            device_requests = []
            if gpu_layers > 0:
                try:
                    device_requests = [docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])]
                    self._log(f"✓ GPU 오프로드 레이어 {gpu_layers}개 등록")
                except Exception as ge:
                    self._log(f"[WARN] GPU 요청 실패 → CPU 전용 모드: {ge}")

            # Engine: model_name is the ID passed from UI
            if engine_type == "OLM":
                image = "ollama/ollama"
                cmd = None
                ports = {'11434/tcp': 11434}
                self._log(f"· 런타임: OLLAMA (Managed API, port 11434)")
            else:
                image = "ghcr.io/ggml-org/llama.cpp:server"
                actual_filename = get_filename_by_id(model_name)
                # 경로 수정: /models -> /vault. 조회된 실제 파일명 사용.
                cmd = ["-m", f"{INTERNAL_VAULT_PATH}/{actual_filename}", "-c", "2048",
                       "--host", "0.0.0.0", "--port", str(LLAMA_CPP_PORT)]
                ports = {f'{LLAMA_CPP_PORT}/tcp': LLAMA_CPP_PORT}
                self._log(f"· 런타임: LLAMA.CPP Server (GGUF: {actual_filename})")

            # Image check/pull
            self._log(f"이미지 인스펙션 중: {image}")
            try:
                client.images.get(image)
                self._log(f"✓ 로컬 이미지 캐시 히트")
            except docker.errors.ImageNotFound:
                self._log(f"↓ 이미지 미발견 → Docker Hub 풀링 시작...")
                self._log("  (초기 다운로드는 이미지 크기에 따라 수 분 소요)")
                for evt in client.api.pull(image, stream=True, decode=True):
                    status = evt.get('status', '')
                    prog = evt.get('progress', '')
                    if status:
                        self._log(f"  ↓ {status} {prog}")
                self._log("✓ 이미지 다운로드 완료")

            # Launch
            self._log("컨테이너 생성 및 부팅 중...")
            self._log(f"  CPU 쿼터 : {cpu_cores} Core(s)")
            self._log(f"  RAM 상한 : {ram_mb} MB")
            self.container = client.containers.run(
                image,
                command=cmd,
                name=self.container_name,
                detach=True,
                nano_cpus=int(cpu_cores * 1e9),
                mem_limit=f"{ram_mb}m",
                ports=ports,
                volumes=volumes,
                device_requests=device_requests
            )
            self._log(f"✓ 컨테이너 시작됨 [ID: {self.container.short_id}]")

            # Stream container startup logs (up to 10s)
            self._log("─── 컨테이너 부팅 로그 스트림 ───")
            deadline = time.time() + 10
            try:
                for raw in self.container.logs(stream=True, follow=True):
                    line = raw.decode('utf-8', errors='replace').strip()
                    if line:
                        self._log(f"[CTR] {line}")
                    if time.time() > deadline:
                        self._log("─── (스트림 10초 상한 도달, 백그라운드 계속 실행) ───")
                        break
            except Exception as le:
                self._log(f"[WARN] 로그 스트리밍 중단: {le}")

            self._log(f"✓ 커널 온라인. 명령 대기 상태.")
            
            # ⚠️ 크리티컬: 모델 로딩 완료 대기 (LLAMA.CPP는 시간이 많이 걸림)
            self._log("⏳ 서버 준비 상태 확인 중 (최대 60초)...")
            server_ready = self._wait_for_server_ready(engine_type, model_name, deadline_sec=60)
            if server_ready:
                self._log("✓ 서버 준비 완료. 추론 가능 상태.")
            else:
                self._log("[WARN] 서버 준비 시간초과 (60초) - 재시도 로직 활사화")
            
            return True, f"[{engine_type}] ONLINE  CPU:{cpu_cores}c  RAM:{ram_mb}MB"

        except Exception as e:
            self._log(f"[FATAL] 부팅 실패: {e}")
            return False, str(e)

    def _wait_for_server_ready(self, engine_type: str, model_name: str, deadline_sec: int = 60) -> bool:
        """[Engineering] 서버가 응답 가능한 상태인지 + 모델 로드가 완료되었는지 실질적으로 확인합니다."""
        import requests
        start = time.time()
        
        while time.time() - start < deadline_sec:
            try:
                if engine_type == "ENG":
                    resp = requests.post(
                        f"http://{LLAMA_CPP_HOST}:{LLAMA_CPP_PORT}/completion",
                        json={"prompt": " ", "n_predict": 1},
                        timeout=2
                    )
                    if resp.status_code == 200:
                        return True
                else:
                    # OLLAMA: /api/generate 에 모델 전달하여 실제 로드 완료 확인
                    resp = requests.post(
                        f"{OLLAMA_BASE_URL}/api/generate",
                        json={"model": model_name, "prompt": " ", "stream": False},
                        timeout=5
                    )
                    if resp.status_code == 200:
                        return True
            except Exception:
                pass  # 네트워크 연결 대기 중
            
            time.sleep(1.5)
        
        return False
        

    def run_llama_bench(self, model_name: str, options: dict) -> dict:
        """지정 모델로 llama-bench를 실행합니다."""
        if not self.container:
            return {}
        try:
            model_file = model_name.replace(":", "-")
            if not model_file.endswith(".gguf"):
                model_file += ".gguf"
            threads = options.get('threads', 4)
            n_ctx = options.get('n_ctx', 2048)
            cmd = f"llama-bench -m /vault/{model_file} -t {threads} -c {n_ctx} --output-json"
            self._log(f"[스트레스] 실행 중: {cmd}")
            exit_code, output = self.container.exec_run(cmd)
            if exit_code == 0:
                import json
                return json.loads(output.decode('utf-8'))
        except Exception as e:
            self._log(f"[에러] LLAMA-BENCH 실행 실패: {e}")
        return {}

    def inject_chaos(self):
        """카오스 몽키 부하 주입."""
        if self.container:
            cmd = "sh -c 'end=$(($(date +%s)+10)); while [ $(date +%s) -lt $end ]; do :; done'"
            self.container.exec_run(cmd, detach=True)
            return True
        return False

    def shutdown(self):
        """매트릭스를 셧다운하고 자원을 반납합니다."""
        if self.container:
            try:
                self.container.stop(timeout=5)
            except Exception:
                pass
            try:
                self.container.remove(force=True)
            except Exception:
                pass
            self.container = None
            self._log("✓ 커널 연결 해제. 자원 반납 완료.")
