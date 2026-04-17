from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class BootstrapConfig:
    """도커 부팅을 위한 구성 모델"""
    engine: str = "OLM"  # OLM 또는 ENG
    cpu_cores: float = 2.0
    ram_mb: int = 4096
    gpu_layers: int = 0
    model_name: str = ""

@dataclass
class StressOptions:
    """스트레스 테스트 및 미세 튜닝을 위한 세부 프로토콜 옵션"""
    threads: int = 4
    n_ctx: int = 2048
    iterations: int = 1
    
    # [Engineering] 미세 튜닝 파라미터 (Phase 2 추가)
    temperature: float = 0.1
    top_k: int = 40
    top_p: float = 0.95
    repeat_penalty: float = 1.1
    system_prompt: str = "You are a professional benchmark assistant. Answer precisely and concisely."

@dataclass
class BenchmarkSession:
    """현재 활성화된 벤치마크 세션의 전체 상태를 담는 컨테이너"""
    boot_config: BootstrapConfig
    stress_config: StressOptions
    run_mode: str = "Inference Mode (Default)"
    judge_key: str = ""
