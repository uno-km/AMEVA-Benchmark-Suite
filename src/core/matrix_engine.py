class MatrixEngine:
    """[V5.5] 매트릭스 엔진 - 도커 오케스트레이션을 위한 순수 백엔드 모듈입니다."""
    
    def __init__(self, container_name: str = "edgematrix_v5_5_arena"):
        self.client = docker.from_env()
        self.container_name = container_name
        self.container = None
        self.log_callback: Optional[Callable[[str], None]] = None

    def set_logger(self, callback: Callable[[str], None]):
        self.log_callback = callback

    def _log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)

    def cleanup_old_arena(self):
        """기존에 남아있는 아레나(컨테이너)를 정리합니다."""
        try:
            self.client.containers.get(self.container_name).remove(force=True)
        except:
            pass

    def boot_matrix(self, config: Dict) -> Tuple[bool, str]:
        """매트릭스(도커 컨테이너)를 부팅합니다."""
        self.cleanup_old_arena()
        
        cpu_cores = float(config.get("cpu_cores", 2.0))
        ram_mb = int(config.get("ram_mb", 2048))
        engine_type = config.get("engine", "OLM")
        gpu_layers = int(config.get("gpu_layers", 0))

        models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
        os.makedirs(models_dir, exist_ok=True)
        volumes = {models_dir: {'bind': '/models', 'mode': 'rw'}}

        device_requests = []
        if gpu_layers > 0:
            try:
                device_requests = [docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])]
            except:
                self._log("[경고] GPU 요청에 실패했습니다. CPU 모드로 전환합니다.")

        try:
            if engine_type == "OLM":
                image = "ollama/ollama"
                cmd = None
                ports = {'11434/tcp': 11434}
            else:
                image = "ghcr.io/ggml-org/llama.cpp:server"
                # 모델 파일이 명시되지 않은 경우 발견 로직 또는 기본값 사용
                cmd = ["-m", "/models/qwen2.5-0.5b.gguf", "-c", "2048", "--host", "0.0.0.0", "--port", "8080"]
                ports = {'8080/tcp': 8080}

            self._log(f"[시스템] 커널 마운트 중: {image}")
            self.container = self.client.containers.run(
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
            
            self._log("[시스템] 아레나 생성 완료. 메모리 초기화 중...")
            time.sleep(5) # 부팅을 위한 대기 시간
            
            return True, f"[{engine_type}] 매트릭스 온라인 (CPU:{cpu_cores}, RAM:{ram_mb}MB)"
        except Exception as e:
            return False, str(e)

    def run_llama_bench(self, model_name: str, options: dict) -> dict:
        """지정된 하드웨어 제약 조건 하에서 llama-bench를 실행합니다."""
        if not self.container: return {}
        try:
            # 모델 명칭 매핑
            model_file = model_name.replace(":", "-")
            if not model_file.endswith(".gguf"): model_file += ".gguf"
            
            threads = options.get('threads', 4)
            n_ctx = options.get('n_ctx', 2048)
            
            cmd = f"llama-bench -m /models/{model_file} -t {threads} -c {n_ctx} --output-json"
            self._log(f"[스트레스] 실행 중: {cmd}")
            
            exit_code, output = self.container.exec_run(cmd)
            if exit_code == 0:
                import json
                return json.loads(output.decode('utf-8'))
        except Exception as e:
            self._log(f"[에러] LLAMA-BENCH 실행 실패: {e}")
        return {}

    def inject_chaos(self):
        """카오스 몽키(부하 테스트)를 주입합니다."""
        if self.container:
            cmd = "sh -c 'end=date +%s; while [ date +%s -lt ]; do :; done'"
            self.container.exec_run(cmd, detach=True)
            return True
        return False

    def shutdown(self):
        """매트릭스를 셧다운하고 자원을 반납합니다."""
        if self.container:
            try:
                self.container.stop(timeout=5)
            except:
                pass
            self.cleanup_old_arena()
            self.container = None
            self._log("[시스템] 커널 연결 해제. 자원 반납 완료.")
