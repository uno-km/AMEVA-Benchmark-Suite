"""
chat_benchmark_engine.py  –  채팅 전용 1회성 추론 엔진 (V5.6)
사용자 채팅 메시지 하나를 받아 LLM 추론 → 지표 계산 → CSV 삽입
Task 컬럼: [CHAT_MOD]
"""
import time
import json
import requests
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from models.settings import BenchmarkSession
from models.report_db import ReportManager


def _ts() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"


class ChatBenchmarkEngine(QThread):
    """단일 채팅 프롬프트를 벤치마크하고 결과를 CSV에 저장합니다."""

    token_signal   = Signal(int)        # 누적 토큰 증분
    sys_log_signal = Signal(str)        # Kernel Telemetry 탭 로그
    chunk_signal   = Signal(str)        # 스트리밍 청크 → ChatPanel
    done_signal    = Signal(dict, str)  # (result_dict, response_text)
    error_signal   = Signal(str)        # 오류 메시지

    def __init__(self, prompt: str, session: BenchmarkSession, engine_core, db: ReportManager):
        super().__init__()
        self._prompt      = prompt
        self._session     = session
        self._engine_core = engine_core
        self._db          = db

    def _slog(self, msg: str):
        self.sys_log_signal.emit(f"{_ts()} {msg}")

    # ── Thread entry ──────────────────────────────────────────────────────

    def run(self):
        session      = self._session
        engine_type  = session.boot_config.engine
        model_name   = session.boot_config.model_name

        if engine_type == "OLM":
            url = "http://127.0.0.1:11434/api/generate"
        else:
            url = "http://127.0.0.1:8080/completion"

        self._slog(f"[CHAT_MOD] 채팅 벤치마크 시작 – 모델: {model_name}")
        self._slog(f"[CHAT_MOD] 프롬프트: {self._prompt[:80]}…")

        payload = {
            "model":   model_name,
            "prompt":  self._prompt,
            "stream":  True,
            "options": {"num_thread": session.stress_config.threads},
        }
        if engine_type == "ENG":
            payload = {
                "prompt":    self._prompt,
                "stream":    True,
                "n_predict": 512,
            }

        text_acc         = ""
        ttft             = 0
        prompt_ms_per_t  = 0
        sample_ms        = 0
        tok_count        = 0
        start_time       = time.time()

        try:
            resp = requests.post(url, json=payload, stream=True, timeout=30)
            resp.raise_for_status()

            for raw_line in resp.iter_lines(decode_unicode=True):
                if self.isInterruptionRequested():
                    break
                if not raw_line:
                    continue

                # ── ENG (llama.cpp SSE) ────────────────────────────────
                if engine_type == "ENG":
                    decoded = raw_line.strip()
                    if not decoded.startswith("data: "):
                        continue
                    decoded = decoded[6:]
                    if decoded == "[DONE]":
                        break
                    data = json.loads(decoded)
                    if ttft == 0:
                        ttft = (time.time() - start_time) * 1000
                    token = data.get("content", "")
                    text_acc += token
                    tok_count += len(data.get("tokens", [])) or 1
                    self._slog(f"[CPP] {repr(token)}")
                    self.chunk_signal.emit(token)
                    self.token_signal.emit(1)
                    if data.get("stop"):
                        t = data.get("timings", {})
                        pn = t.get("prompt_n", 0)
                        pm = t.get("prompt_ms", 0)
                        prompt_ms_per_t = round(pm / pn, 2) if pn > 0 else 0
                        sample_ms = t.get("predicted_ms", 0)
                        break

                # ── OLM (Ollama) ───────────────────────────────────────
                else:
                    data = json.loads(raw_line.strip())
                    if ttft == 0:
                        ttft = (time.time() - start_time) * 1000
                    token = data.get("response", "")
                    text_acc += token
                    tok_count += 1
                    self._slog(f"[OLM] {repr(token)}")
                    self.chunk_signal.emit(token)
                    self.token_signal.emit(1)
                    if data.get("done"):
                        break

        except Exception as e:
            self._slog(f"[CHAT_MOD] 오류: {e}")
            self.error_signal.emit(str(e))
            return

        duration = time.time() - start_time
        if ttft == 0:
            ttft = duration * 1000
        tps_val = round(tok_count / duration, 2) if duration > 0 else 0

        self._slog(
            f"[CHAT_MOD] 완료 | TPS: {tps_val} | TTFT: {ttft:.1f}ms | "
            f"{tok_count}tok | {duration:.2f}s"
        )

        result = {
            "Model_Hash":          model_name,
            "Quant_Method":        "N/A",
            "Context_Size":        session.stress_config.n_ctx,
            "Thread_Config":       session.stress_config.threads,
            "Prompt_Text":         self._prompt,
            "Prompt_Response":     text_acc,
            "TTFT (ms)":           round(ttft, 1),
            "Prompt_Eval (ms/t)":  prompt_ms_per_t,
            "Avg_GPU_W":           0,
            "Tokens_per_Joule":    0,
            "E2E_Latency":         round(duration, 2),
            "Generation (t/s)":    tps_val,
            "Peak_VRAM_MB":        0,
            "System_Load":         "[CHAT_MOD]",
            "Warm/Cold_Tag":       "CHAT",
            "Sampling_Time (ms)":  round(sample_ms, 2),
            "Judge_Score":         "N/A",
            "Metric_Source":       "chat",
        }

        # CSV 즉시 삽입
        try:
            self._db.insert_entry(result)
            self._slog("[CHAT_MOD] CSV 삽입 완료.")
        except Exception as e:
            self._slog(f"[CHAT_MOD] CSV 삽입 실패: {e}")

        self.done_signal.emit(result, text_acc)
