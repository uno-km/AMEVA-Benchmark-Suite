import docker
import time
import datetime
import os
from typing import Dict, Tuple

class MatrixEngine:
    def __init__(self):
        self.client = docker.from_env()
        self.container_name = "edgematrix_v4_arena"
        self.container = None
        self.current_cpus = 2.0
        self.is_throttled = False
        self.ui_logger = None
        
    def set_logger(self, logger_func):
        """UI(DashUI)의 log_sys 함수를 이 엔진에 연결합니다."""
        self.ui_logger = logger_func

    def _sys_log(self, msg):
        """print 대신 UI의 두 번째 탭으로 메시지를 전송합니다."""
        if self.ui_logger:
            self.ui_logger(msg)
        else:
            print(msg) # UI가 안 붙어있으면 걍 터미널 출력
            
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
            # 1. 엔진 종류에 따라 이미지, 명령어, 포트를 다르게 세팅!
            if engine_type == "ollama":
                image = "ollama/ollama"
                cmd = None
                port_binding = {'11434/tcp': 11434}  # Ollama용 포트
            else:
                image = "ghcr.io/ggml-org/llama.cpp:server"
                cmd = ["-m", "/models/qwen2.5-0.5b.gguf", "-c", "2048", "--host", "0.0.0.0", "--port", "8080"]
                port_binding = {'8080/tcp': 8080}  # ✅ llama.cpp용 포트!!
            
            self._sys_log(f"[SYSTEM] '{image}' 이미지 마운트 및 부팅 시퀀스 가동...")
            
            # 2. 컨테이너 실행 시 동적으로 port_binding 변수를 넣습니다.
            self.container = self.client.containers.run(
                image, command=cmd, name=self.container_name, detach=True,
                nano_cpus=int(self.current_cpus * 1e9), mem_limit=ram_str, memswap_limit=ram_str,
                ports=port_binding, # 🚨 하드코딩 삭제하고 이걸로 교체!
                volumes=volumes_config, device_requests=device_reqs
            )
            self.print_matrix_telemetry(self.container) 
            self._sys_log("\n[SYSTEM] 매트릭스 부팅 완료. 모델 GGUF RAM 적재 대기 중...")
            # 이 부분에서 함수를 호출합니다!

            spinner = ['|', '/', '-', '\\']
            for i in range(10):
                self._sys_log(f"   -> 적재 진행 중... {spinner[i % 4]} ({(i+1)*10}%)")
                time.sleep(1) # 1초씩 끊어서 10번 대기
                
            self._sys_log("[SYSTEM] 🟢 RAM 적재 완료. API 통신 포트(8080) 개방.\n")
            
            self.is_throttled = False
            return True, f"[{engine_type.upper()}] CPU {self.current_cpus}C, RAM {ram_str}, GPU Layers {gpu_layers} 격리 가동."
        except Exception as e:
            return False, str(e)

    def inject_chaos_monkey(self):
        """[기능 3] 카오스 몽키: 백그라운드에 인위적인 100% CPU 더미 연산 주입 (3초간)"""
        if self.container:
            try:
                # 쉘 스크립트로 3초간 무한 루프를 도는 악성(Chaos) 프로세스 실행
                cmd = "sh -c 'end=date +%s; end=; while [ date +%s -lt ]; do :; done'"
                self.container.exec_run(cmd, detach=True)
                return True
            except: return False
        return False

    def print_matrix_telemetry(self, container):
        """도커 컨테이너의 심장부(상태, 메모리, 마운트, 내부 로그)를 파헤쳐 출력합니다."""
        
        # 1. 최신 상태 동기화
        container.reload()
        
        # 2. 기본 정보
        c_name = container.name
        c_id = container.short_id
        c_status = container.status
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. 마운트(Volume) 정보 추적
        mounts = container.attrs.get('Mounts', [])
        mount_info = ""
        if not mounts:
            mount_info = "마운트된 볼륨 없음"
        else:
            for m in mounts:
                mount_info += f"\n    -> [Host] {m['Source']} \n    -> [Matrix] {m['Destination']} (Mode: {m.get('Mode', 'N/A')})"

        # 4. 실시간 리소스 (메모리)
        try:
            stats = container.stats(stream=False)
            mem_usage = stats['memory_stats'].get('usage', 0) / (1024 * 1024)
            mem_limit = stats['memory_stats'].get('limit', 0) / (1024 * 1024)
            mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
        except Exception:
            mem_usage, mem_limit, mem_percent = 0, 0, 0

        # 5. 컨테이너 내부 최신 로그 (마지막 5줄)
        try:
            recent_logs = container.logs(tail=5).decode('utf-8').strip()
        except Exception:
            recent_logs = "로그 추출 실패"


        self._sys_log("\n" + "="*50)
        self._sys_log(" 📡 [MATRIX TELEMETRY UPLINK ESTABLISHED] 📡")
        self._sys_log("="*50)
        self._sys_log(f"접속 시간  : {current_time}")
        self._sys_log(f"컨테이너   : {c_name} (상태: {c_status.upper()})")
        self._sys_log(f"현재 상태  : {c_status.upper()}")
        self._sys_log("-" * 50)
        self._sys_log(f"메모리 적재: {mem_usage:.2f} MB / {mem_limit:.2f} MB ({mem_percent:.2f}%)")
        self._sys_log("-" * 50)
        self._sys_log(f"마운트 경로:{mount_info}")
        self._sys_log("-" * 50)
        self._sys_log(" 🔎 [Matrix 내부 최신 로그 (마지막 5줄)]")
        self._sys_log(recent_logs if recent_logs else "(로그 없음 - 엔진 기동 중)")
        self._sys_log("="*50 + "\n")
        

        
        self._sys_log("-" * 50)
        self._sys_log("="*50 + "\n")
        
        # ================= UI 출력부 =================
        print("\n" + "="*60)
        print(" 📡 [MATRIX TELEMETRY UPLINK ESTABLISHED] 📡")
        print("="*60)
        print(f"접속 시간  : {current_time}")
        print(f"컨테이너   : {c_name} (ID: {c_id})")
        print(f"현재 상태  : {c_status.upper()}")
        print("-" * 60)
        print(f"메모리 적재: {mem_usage:.2f} MB / {mem_limit:.2f} MB ({mem_percent:.2f}%)")
        print("-" * 60)
        print(f"마운트 경로:{mount_info}")
        print("-" * 60)
        print(" 🔎 [Matrix 내부 최신 로그 (마지막 5줄)]")
        print(recent_logs if recent_logs else "(로그 없음 - 엔진 기동 중)")
        print("="*60 + "\n")
    
    def shutdown(self):
        """매트릭스의 모든 자원을 안전하게 회수하고 마운트를 해제합니다."""
        print("\n" + "="*60)
        print(" ⚠️ [SYSTEM SHUTDOWN SEQUENCE INITIATED] ⚠️")
        print("="*60)
        
        self._sys_log("\n" + "="*50)
        self._sys_log(" ⚠️ [SYSTEM SHUTDOWN SEQUENCE INITIATED] ⚠️")
        self._sys_log("="*50)
        
        print("1. 매트릭스(Docker) 컨테이너 정지 및 연결 해제 중...")
        try:
            if self.container:
                # 5초간 부드럽게 종료를 시도하고, 안 되면 강제 종료(SIGKILL)
                self.container.stop(timeout=5) 
                print("   -> 컨테이너 동작 정지 완료.")
        except Exception as e:
            print(f"   -> [경고] 정지 중 문제 발생 (무시하고 파괴 진행): {e}")

        print("2. 할당된 물리 자원(RAM, CPU) 반납 및 볼륨 마운트 파괴 중...")
        self._sys_log("2. 물리 자원 반납 및 볼륨 마운트 파괴 중...")
        self.nuke_existing_arena()
        self.container = None
        
        print("3. 호스트 시스템 메모리 반환 완료.")
        print("="*60)
        print(" 🟢 [ALL RESOURCES SECURELY RELEASED] 🟢")
        print("="*60 + "\n")
        self._sys_log("3. 호스트 시스템 메모리 반환 완료.")
        self._sys_log("="*50)
        self._sys_log(" 🟢 [ALL RESOURCES SECURELY RELEASED] 🟢")
        self._sys_log("="*50 + "\n")
