"""
model_gallery.py  –  모델 갤러리 모달 (V5.6)
9종 GGUF 모델 설치·관리 QDialog
카테고리: Lite (즉시 실행) / Medium (밸런스) / Heavy (최고 성능)
비동기 다운로드 + 스피너 + 시스템 트레이 알림
"""
import os
import requests
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QProgressBar, QGroupBox,
    QApplication, QSystemTrayIcon
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSize
from PySide6.QtGui import QFont, QColor, QIcon, QMovie

# ─────────────────────────────────────────────────────────────────────────────
# Model Catalogue
# ─────────────────────────────────────────────────────────────────────────────

MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models_gguf"
)

MODEL_CATALOGUE = [
    # ── Lite ──────────────────────────────────────────────────── 최소 RAM 2GB
    {
        "id":          "qwen2.5-1.5b",
        "display":     "Qwen2.5-1.5B-Instruct",
        "category":    "Lite",
        "tag":         "⚡ 밸런스 · 한국어 명령",
        "desc":        "범용 소형 모델. 한국어 지시문 이해 우수. 노트북CPU에서도 빠름.",
        "min_ram_gb":  2,
        "size_gb":     1.0,
        "filename":    "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "hf_url":      "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "ollama_tag":  "qwen2.5:1.5b",
    },
    {
        "id":          "llama-3.2-1b",
        "display":     "Llama-3.2-1B-Instruct",
        "category":    "Lite",
        "tag":         "🪶 초경량 · JSON 포맷팅",
        "desc":        "가장 작은 모델. JSON 출력·구조화 태스크에 최적. RAM 2GB 이하 OK.",
        "min_ram_gb":  2,
        "size_gb":     0.7,
        "filename":    "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "ollama_tag":  "llama3.2:1b",
    },
    {
        "id":          "deepseek-r1-1.5b",
        "display":     "DeepSeek-R1-Distill-Qwen-1.5B",
        "category":    "Lite",
        "tag":         "🧠 논리 추론 · 경로 판단",
        "desc":        "추론 특화 증류 모델. 수학·논리·단계적 사고 강점. 1.5B 대비 성능 이상.",
        "min_ram_gb":  2,
        "size_gb":     1.0,
        "filename":    "DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
        "ollama_tag":  "deepseek-r1:1.5b",
    },
    {
        "id":          "gemma-2-2b",
        "display":     "Gemma-2-2B-It",
        "category":    "Lite",
        "tag":         "🏷️ 분류 · 객관식 판단",
        "desc":        "Google DeepMind 2B 모델. 분류·선택형 판단 우수. 효율 대비 품질 높음.",
        "min_ram_gb":  3,
        "size_gb":     1.6,
        "filename":    "gemma-2-2b-it-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "ollama_tag":  "gemma2:2b",
    },
    # ── Medium ────────────────────────────────────────────────── RAM 4~6GB
    {
        "id":          "qwen2.5-3b",
        "display":     "Qwen2.5-3B-Instruct",
        "category":    "Medium",
        "tag":         "💻 코딩 · 로직 분석",
        "desc":        "코딩·로직 분석 3B 최강. 파이썬/JS 함수 작성, 알고리즘 추론 탁월.",
        "min_ram_gb":  4,
        "size_gb":     2.0,
        "filename":    "qwen2.5-3b-instruct-q4_k_m.gguf",
        "hf_url":      "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        "ollama_tag":  "qwen2.5:3b",
    },
    {
        "id":          "llama-3.2-3b",
        "display":     "Llama-3.2-3B-Instruct",
        "category":    "Medium",
        "tag":         "🔗 논리 추론 · 맥락 유지",
        "desc":        "Meta 3B. 긴 문맥 유지·대화 흐름 일관성 우수. 범용 중형 추천.",
        "min_ram_gb":  4,
        "size_gb":     2.0,
        "filename":    "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "ollama_tag":  "llama3.2:3b",
    },
    # ── Heavy ─────────────────────────────────────────────────── RAM 8GB+
    {
        "id":          "exaone-7.8b",
        "display":     "EXAONE-3.0-7.8B-Instruct",
        "category":    "Heavy",
        "tag":         "🇰🇷 한국어 뉘앙스 · 최고 성능",
        "desc":        "LG AI Research 7.8B 한국어 1위 모델. 문맥·뉘앙스·존댓말 완벽 이해.",
        "min_ram_gb":  8,
        "size_gb":     4.8,
        "filename":    "EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/EXAONE-3.0-7.8B-Instruct-GGUF/resolve/main/EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf",
        "ollama_tag":  "exaone3:7.8b",
    },
    {
        "id":          "kullm3-8b",
        "display":     "KULLM3-8B",
        "category":    "Heavy",
        "tag":         "🌐 Llama3 기반 한국어 패치",
        "desc":        "Korea Univ. Llama3 파인튜닝. 한국어 교육·상식·추론 특화. 8B급 안정성.",
        "min_ram_gb":  8,
        "size_gb":     4.9,
        "filename":    "KULLM3-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/KULLM3-GGUF/resolve/main/KULLM3-Q4_K_M.gguf",
        "ollama_tag":  "kullm3",
    },
    {
        "id":          "eeve-10.8b",
        "display":     "EEVE-Korean-10.8B",
        "category":    "Heavy",
        "tag":         "📚 어휘력 특화 · 대형 모델",
        "desc":        "Yanolja 10.8B 한국어 어휘력 특화. 문학·법률·의학 어휘 이해 최상위.",
        "min_ram_gb":  12,
        "size_gb":     6.6,
        "filename":    "EEVE-Korean-Instruct-10.8B-v1.0-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/EEVE-Korean-Instruct-10.8B-v1.0-GGUF/resolve/main/EEVE-Korean-Instruct-10.8B-v1.0-Q4_K_M.gguf",
        "ollama_tag":  "eeve-korean:10.8b",
    },
]

CATEGORY_META = {
    "Lite":   {"icon": "⚡", "color": "#10b981", "desc": "RAM 2~3GB  |  즉시 실행 가능  |  CPU 전용 환경 OK"},
    "Medium": {"icon": "⚙️", "color": "#3b82f6", "desc": "RAM 4~6GB  |  일상 노트북 권장  |  4코어 이상"},
    "Heavy":  {"icon": "🔥", "color": "#f59e0b", "desc": "RAM 8GB+   |  고성능 워크스테이션  |  GPU 권장"},
}

# ─────────────────────────────────────────────────────────────────────────────
# Download Worker
# ─────────────────────────────────────────────────────────────────────────────

class ModelDownloadWorker(QThread):
    progress_signal = Signal(int)          # 0~100
    done_signal     = Signal(bool, str)    # (success, model_id)
    log_signal      = Signal(str)

    def __init__(self, model_info: dict, dest_dir: str):
        super().__init__()
        self._info    = model_info
        self._dest    = dest_dir

    def run(self):
        url      = self._info["hf_url"]
        fname    = self._info["filename"]
        model_id = self._info["id"]
        path     = os.path.join(self._dest, fname)

        os.makedirs(self._dest, exist_ok=True)

        try:
            self.log_signal.emit(f"[DL] 다운로드 시작: {fname}")
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 1024 * 512  # 512 KB

            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if self.isInterruptionRequested():
                        self.log_signal.emit("[DL] 취소 요청 수신.")
                        f.close()
                        if os.path.exists(path):
                            os.remove(path)
                        self.done_signal.emit(False, model_id)
                        return
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(downloaded / total * 100)
                        self.progress_signal.emit(pct)

            self.log_signal.emit(f"[DL] 완료: {fname}")
            self.done_signal.emit(True, model_id)

        except Exception as e:
            self.log_signal.emit(f"[DL] 오류: {e}")
            if os.path.exists(path):
                os.remove(path)
            self.done_signal.emit(False, model_id)


# ─────────────────────────────────────────────────────────────────────────────
# Gallery Style
# ─────────────────────────────────────────────────────────────────────────────

_BG      = "#0f172a"
_SURFACE = "#1e293b"
_BORDER  = "#334155"
_TEXT    = "#e2e8f0"
_DIM     = "#94a3b8"

_GALLERY_QSS = f"""
QDialog {{
    background-color: {_BG};
    color: {_TEXT};
    font-family: 'Inter','Segoe UI',sans-serif;
}}
QLabel {{ color: {_TEXT}; border: none; }}
QScrollArea {{ background: transparent; border: none; }}
QGroupBox {{
    border: 1px solid {_BORDER};
    border-radius: 10px;
    margin-top: 16px;
    font-weight: 700;
    font-size: 11px;
    color: {_DIM};
    padding: 14px;
    background-color: {_SURFACE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
}}
QPushButton {{
    border-radius: 6px;
    font-weight: 600;
    font-size: 12px;
    padding: 6px 14px;
    border: 1px solid {_BORDER};
    color: {_TEXT};
    background-color: {_SURFACE};
}}
QPushButton:hover {{ background-color: #2d3e50; border-color: #3b82f6; }}
QPushButton#InstallBtn {{
    background-color: #1d4ed8;
    border: none;
    color: white;
    min-width: 70px;
}}
QPushButton#InstallBtn:hover {{ background-color: #2563eb; }}
QPushButton#ActiveBtn {{
    background-color: #14532d;
    border: 1px solid #16a34a;
    color: #86efac;
    min-width: 70px;
}}
QPushButton#SelectBtn {{
    background-color: #1e3a5f;
    border: 1px solid #3b82f6;
    color: #93c5fd;
    min-width: 70px;
}}
QPushButton#CloseBtn {{
    background-color: #450a0a;
    border: 1px solid #ef4444;
    color: #fca5a5;
}}
QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: #334155;
    max-height: 6px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background-color: #3b82f6;
    border-radius: 4px;
}}
QScrollBar:vertical {{
    background: {_SURFACE}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {_BORDER}; border-radius: 4px; min-height: 30px;
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Model Card Widget
# ─────────────────────────────────────────────────────────────────────────────

class ModelCard(QFrame):
    """단일 모델 카드 위젯."""

    install_clicked = Signal(dict)    # model_info 전달
    select_clicked  = Signal(str)     # ollama_tag 전달

    def __init__(self, info: dict, installed: bool, is_current: bool, parent=None):
        super().__init__(parent)
        self._info = info
        self._build(installed, is_current)

    def _build(self, installed: bool, is_current: bool):
        self.setObjectName("ModelCard")
        self.setStyleSheet(
            "QFrame#ModelCard { background-color: #162032;"
            " border: 1px solid #2d3f55; border-radius: 10px; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)

        # Left: info block
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        # Model name + tag
        name_row = QHBoxLayout()
        name_lbl = QLabel(self._info["display"])
        name_lbl.setStyleSheet(
            "color: #f1f5f9; font-weight: 700; font-size: 13px;"
        )
        tag_lbl = QLabel(self._info["tag"])
        tag_lbl.setStyleSheet(
            "color: #94a3b8; font-size: 10px; font-weight: 600;"
            " background: #1e293b; border: 1px solid #334155;"
            " border-radius: 4px; padding: 1px 6px;"
        )
        name_row.addWidget(name_lbl)
        name_row.addWidget(tag_lbl)
        name_row.addStretch()
        info_col.addLayout(name_row)

        # Description
        desc_lbl = QLabel(self._info["desc"])
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        desc_lbl.setWordWrap(True)
        info_col.addWidget(desc_lbl)

        # Specs
        spec_lbl = QLabel(
            f"최소 RAM: {self._info['min_ram_gb']}GB  |  "
            f"파일 크기: ~{self._info['size_gb']:.1f}GB  |  "
            f"Ollama: {self._info['ollama_tag']}"
        )
        spec_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        info_col.addWidget(spec_lbl)

        row.addLayout(info_col, 1)

        # Right: progress + button
        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        right_col.setAlignment(Qt.AlignCenter)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(90)
        self._progress.setValue(0)
        self._progress.hide()
        right_col.addWidget(self._progress)

        self._spinner_lbl = QLabel("⏳")
        self._spinner_lbl.setAlignment(Qt.AlignCenter)
        self._spinner_lbl.setStyleSheet("font-size: 18px;")
        self._spinner_lbl.hide()
        right_col.addWidget(self._spinner_lbl)

        self._action_btn = QPushButton()
        self._action_btn.setFixedWidth(90)
        self._update_btn_state(installed, is_current)
        right_col.addWidget(self._action_btn)

        row.addLayout(right_col)

    def _update_btn_state(self, installed: bool, is_current: bool):
        if is_current:
            self._action_btn.setText("✅ 사용 중")
            self._action_btn.setObjectName("ActiveBtn")
            self._action_btn.setEnabled(False)
        elif installed:
            self._action_btn.setText("▶ 선택")
            self._action_btn.setObjectName("SelectBtn")
            self._action_btn.clicked.connect(
                lambda: self.select_clicked.emit(self._info["ollama_tag"])
            )
        else:
            self._action_btn.setText("⬇ 설치")
            self._action_btn.setObjectName("InstallBtn")
            self._action_btn.clicked.connect(
                lambda: self.install_clicked.emit(self._info)
            )

    def set_installing(self, pct: int):
        self._progress.show()
        self._progress.setValue(pct)
        self._spinner_lbl.show()
        self._action_btn.setEnabled(False)
        self._action_btn.setText("설치 중…")

    def set_installed(self):
        self._progress.hide()
        self._spinner_lbl.hide()
        self._action_btn.setText("▶ 선택")
        self._action_btn.setObjectName("SelectBtn")
        self._action_btn.setEnabled(True)
        # reconnect
        try:
            self._action_btn.clicked.disconnect()
        except Exception:
            pass
        self._action_btn.clicked.connect(
            lambda: self.select_clicked.emit(self._info["ollama_tag"])
        )
        self.style().unpolish(self._action_btn)
        self.style().polish(self._action_btn)

    def set_failed(self):
        self._progress.hide()
        self._spinner_lbl.hide()
        self._action_btn.setText("재시도")
        self._action_btn.setObjectName("InstallBtn")
        self._action_btn.setEnabled(True)
        try:
            self._action_btn.clicked.disconnect()
        except Exception:
            pass
        self._action_btn.clicked.connect(
            lambda: self.install_clicked.emit(self._info)
        )
        self.style().unpolish(self._action_btn)
        self.style().polish(self._action_btn)


# ─────────────────────────────────────────────────────────────────────────────
# Main Dialog
# ─────────────────────────────────────────────────────────────────────────────

class ModelGalleryDialog(QDialog):
    """모델 갤러리 모달."""

    model_selected = Signal(str)   # ollama_tag

    def __init__(self, current_model: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛠️  모델 갤러리 · 설치 & 관리")
        self.setMinimumSize(780, 640)
        self.setStyleSheet(_GALLERY_QSS)
        self.setModal(True)

        self._current_model = current_model
        self._cards: dict[str, ModelCard] = {}
        self._workers: dict[str, ModelDownloadWorker] = {}

        self._build_ui()
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(300)
        self._spinner_timer.timeout.connect(self._tick_spinners)
        self._spinner_idx = 0

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("🛠️  모델 갤러리")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #f1f5f9;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
        hdr.addWidget(self._status_lbl)
        root.addLayout(hdr)

        subtitle = QLabel(
            "아래 모델을 선택하거나 설치하세요. "
            "설치된 모델만 벤치마크에 사용 가능합니다."
        )
        subtitle.setStyleSheet("color: #64748b; font-size: 11px;")
        root.addWidget(subtitle)

        # Scroll area with cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(0, 0, 0, 0)

        for cat_name, cat_meta in CATEGORY_META.items():
            # Category group box
            grp = QGroupBox(
                f"{cat_meta['icon']}  {cat_name}  —  {cat_meta['desc']}"
            )
            grp.setStyleSheet(
                f"QGroupBox {{ border-color: {cat_meta['color']};"
                f" color: {cat_meta['color']}; }}"
                f"QGroupBox::title {{ color: {cat_meta['color']}; }}"
            )
            grp_layout = QVBoxLayout(grp)
            grp_layout.setSpacing(6)

            for info in MODEL_CATALOGUE:
                if info["category"] != cat_name:
                    continue
                installed  = self._is_installed(info)
                is_current = info["ollama_tag"] == self._current_model
                card = ModelCard(info, installed, is_current)
                card.install_clicked.connect(self._on_install)
                card.select_clicked.connect(self._on_select)
                self._cards[info["id"]] = card
                grp_layout.addWidget(card)

            content_layout.addWidget(grp)

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # Footer
        footer = QHBoxLayout()
        self._footer_note = QLabel(
            f"📁 모델 저장 경로: {MODELS_DIR}"
        )
        self._footer_note.setStyleSheet("color: #475569; font-size: 10px;")
        footer.addWidget(self._footer_note)
        footer.addStretch()

        close_btn = QPushButton("✖  닫기")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedWidth(90)
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _is_installed(self, info: dict) -> bool:
        path = os.path.join(MODELS_DIR, info["filename"])
        return os.path.isfile(path)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_install(self, info: dict):
        model_id = info["id"]
        if model_id in self._workers:
            return  # 이미 진행 중

        card = self._cards.get(model_id)
        if card:
            card.set_installing(0)

        worker = ModelDownloadWorker(info, MODELS_DIR)
        worker.progress_signal.connect(
            lambda pct, mid=model_id: self._on_progress(mid, pct)
        )
        worker.done_signal.connect(self._on_done)
        worker.log_signal.connect(lambda msg: self._status_lbl.setText(msg[-60:]))
        self._workers[model_id] = worker
        worker.start()

        if not self._spinner_timer.isActive():
            self._spinner_timer.start()

        self._status_lbl.setText(f"⬇ {info['display']} 다운로드 중…")

    def _on_progress(self, model_id: str, pct: int):
        card = self._cards.get(model_id)
        if card:
            card.set_installing(pct)

    def _on_done(self, success: bool, model_id: str):
        self._workers.pop(model_id, None)
        card = self._cards.get(model_id)

        if success:
            if card:
                card.set_installed()
            self._status_lbl.setText("✅ 설치 완료!")
            self._show_tray_notification(
                f"모델 설치 완료",
                f"{model_id} 모델이 성공적으로 설치되었습니다."
            )
        else:
            if card:
                card.set_failed()
            self._status_lbl.setText("❌ 설치 실패 – 네트워크를 확인하세요.")

        if not self._workers:
            self._spinner_timer.stop()

    def _on_select(self, ollama_tag: str):
        self._current_model = ollama_tag
        self.model_selected.emit(ollama_tag)
        self._status_lbl.setText(f"✅ 선택됨: {ollama_tag}")
        self.close()

    def _tick_spinners(self):
        frames = ["⏳", "⌛"]
        self._spinner_idx = (self._spinner_idx + 1) % len(frames)
        for model_id, worker in self._workers.items():
            card = self._cards.get(model_id)
            if card and hasattr(card, "_spinner_lbl"):
                card._spinner_lbl.setText(frames[self._spinner_idx])

    def _show_tray_notification(self, title: str, msg: str):
        try:
            tray = QSystemTrayIcon(QApplication.instance())
            tray.show()
            tray.showMessage(title, msg, QSystemTrayIcon.Information, 4000)
        except Exception:
            pass
