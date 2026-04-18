from datetime import datetime
from typing import Dict
from ui.qt_bridge import *


def _ts() -> str:
    """현재 시각을 [HH:MM:SS.mmm] 포맷으로 반환합니다."""
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"


class BootThread(QThread):
    """[V5.5] 비동기 Docker 부팅 스레드.
    MatrixEngine.boot_matrix()를 백그라운드에서 실행하고
    타임스탬프 포함 로그를 실시간으로 emit합니다.
    """
    log_signal = Signal(str)
    done_signal = Signal(bool, str)   # (success, message)

    def __init__(self, config: Dict, engine):
        super().__init__()
        self.config = config
        self.engine = engine

    def _ts_log(self, msg: str):
        """타임스탬프를 앞에 붙여 log_signal로 emit합니다."""
        self.log_signal.emit(f"{_ts()} {msg}")

    def run(self):
        # MatrixEngine의 로거를 타임스탬프 래퍼로 교체
        self.engine.set_logger(self._ts_log)
        success, msg = self.engine.boot_matrix(self.config)
        self.done_signal.emit(success, msg)
