import os
import json
import requests
from ui.qt_bridge import *
from core.constants import get_vault_abs_path, OLLAMA_BASE_URL
from core.ollama_client import OllamaClient

# ─────────────────────────────────────────────────────────────────────────────
# Model Catalogue
# ─────────────────────────────────────────────────────────────────────────────

MODELS_DIR = get_vault_abs_path()

from core.models_data import MODEL_CATALOGUE, CATEGORY_META

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


class OllamaPullWorker(QThread):
    """Ollama API를 통해 모델을 풀링하는 워커."""
    progress_signal = Signal(str, int)     # model_id, pct
    done_signal     = Signal(bool, str)    # success, model_id
    log_signal      = Signal(str)

    def __init__(self, model_info: dict):
        super().__init__()
        self._info = model_info

    def run(self):
        tag = self._info["ollama_tag"]
        model_id = self._info["id"]
        
        try:
            self.log_signal.emit(f"[OLM] 풀링 시작: {tag}")
            resp = OllamaClient.pull_model_stream(tag)
            resp.raise_for_status()

            for line in resp.iter_lines():
                if self.isInterruptionRequested():
                    self.done_signal.emit(False, model_id)
                    return
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    status = data.get("status", "")
                    total = data.get("total", 0)
                    completed = data.get("completed", 0)
                    
                    if total > 0:
                        pct = int(completed / total * 100)
                        self.progress_signal.emit(model_id, int(pct))
                    elif "manifest" in status.lower():
                        # 매니페스트 단계에서는 1%로 표시하여 먹통 아님을 알림
                        self.progress_signal.emit(model_id, 1)
                    
                    if status == "success":
                        self.log_signal.emit(f"[OLM] 완료: {tag}")
                        self.done_signal.emit(True, model_id)
                        return
                except:
                    continue # JSON 파싱 실패 시 무시하고 다음 줄

        except Exception as e:
            self.log_signal.emit(f"[OLM] 에러: {e}")
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

    install_clicked = Signal(dict)       # model_info 전달
    select_clicked  = Signal(str, str) # model_name, engine_type 전달

    def __init__(self, info: dict, installed: bool, is_current: bool, ollama_on: bool = False, parent=None):
        super().__init__(parent)
        self._info = info
        self._build(installed, is_current, ollama_on)

    def _build(self, installed: bool, is_current: bool, ollama_on: bool):
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
        self._spinner_lbl = QLabel("") # 애니메이션용
        self._spinner_lbl.setStyleSheet("color: #3b82f6; font-size: 12px; font-weight: 800;")
        self._spinner_lbl.hide()

        tag_lbl = QLabel(self._info["tag"])
        tag_lbl.setStyleSheet(
            "color: #94a3b8; font-size: 10px; font-weight: 600;"
            " background: #1e293b; border: 1px solid #334155;"
            " border-radius: 4px; padding: 1px 6px;"
        )
        name_row.addWidget(name_lbl)
        name_row.addWidget(self._spinner_lbl)
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

        # Right: Buttons for GGUF & Ollama
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        # GGUF Block
        gguf_row = QHBoxLayout()
        self.gguf_status = QLabel("📦 GGUF")
        self.gguf_status.setStyleSheet("font-size: 10px; color: #64748b;")
        self.btn_gguf = QPushButton("⬇ 다운로드")
        self.btn_gguf.setObjectName("InstallBtn")
        self.btn_gguf.setFixedWidth(85)
        gguf_row.addWidget(self.gguf_status)
        gguf_row.addStretch()
        gguf_row.addWidget(self.btn_gguf)
        btn_layout.addLayout(gguf_row)

        # Ollama Block
        ollama_row = QHBoxLayout()
        self.ollama_status = QLabel("🦙 Ollama")
        self.ollama_status.setStyleSheet("font-size: 10px; color: #64748b;")
        self.btn_ollama = QPushButton("⬇ 풀링")
        self.btn_ollama.setObjectName("InstallBtn")
        self.btn_ollama.setFixedWidth(85)
        ollama_row.addWidget(self.ollama_status)
        ollama_row.addStretch()
        ollama_row.addWidget(self.btn_ollama)
        btn_layout.addLayout(ollama_row)

        # Global Progress
        self._progress = QProgressBar()
        self._progress.setFixedHeight(4)
        self._progress.hide()
        btn_layout.addWidget(self._progress)

        row.addLayout(btn_layout)
        self._update_btn_state(installed, is_current, ollama_on)

    def _update_btn_state(self, installed: bool, is_current: bool, ollama_on: bool):
        # 1. GGUF 전용 버튼 상태
        if installed:
            self.btn_gguf.setText("▶ 사용 (GGUF)")
            self.btn_gguf.setObjectName("SelectBtn")
            self.btn_gguf.setEnabled(True)
            try:
                self.btn_gguf.clicked.disconnect()
            except:
                pass
            self.btn_gguf.clicked.connect(lambda: self.select_clicked.emit(self._info["id"], "ENG"))
        else:
            self.btn_gguf.setText("⬇ 다운로드")
            self.btn_gguf.setObjectName("InstallBtn")
            self.btn_gguf.setEnabled(True)
            try:
                self.btn_gguf.clicked.disconnect()
            except:
                pass
            self.btn_gguf.clicked.connect(lambda: self.install_clicked.emit(self._info))

        # 2. Ollama 전용 버튼 상태 
        if ollama_on:
            self.btn_ollama.setText("▶ 사용 (Ollama)")
            self.btn_ollama.setObjectName("SelectBtn")
            self.btn_ollama.setEnabled(True)
            try:
                self.btn_ollama.clicked.disconnect()
            except:
                pass
            self.btn_ollama.clicked.connect(lambda: self.select_clicked.emit(self._info["ollama_tag"], "OLM"))
        else:
            self.btn_ollama.setText("⬇ 풀링")
            self.btn_ollama.setObjectName("InstallBtn")
            self.btn_ollama.setEnabled(True)

    def set_installing(self, is_ollama=False):
        self._progress.show()
        self._spinner_lbl.show()
        if is_ollama:
            self.btn_ollama.setEnabled(False)
            self.btn_ollama.setText("풀링 중…")
        else:
            self.btn_gguf.setEnabled(False)
            self.btn_gguf.setText("다운로드 중…")

    def set_installed(self):
        self._progress.hide()
        self._spinner_lbl.hide()
        # 상태 업데이트는 Dialog에서 _update_card_statuses()를 호출하여 처리됩니다.

# ─────────────────────────────────────────────────────────────────────────────
# Main Dialog
# ─────────────────────────────────────────────────────────────────────────────

class ModelGalleryDialog(QDialog):
    """모델 갤러리 모달."""

    model_selected = Signal(str, str) # name, engine_type
    install_requested = Signal(dict, bool) # info, is_ollama

    def __init__(self, current_model: str = "", parent=None, dl_workers: dict = None):
        super().__init__(parent)
        self.setWindowTitle("🛠️  모델 갤러리 · 설치 & 관리")
        self.setMinimumSize(780, 640)
        self.setStyleSheet(_GALLERY_QSS)
        self.setModal(True)

        self._current_model = current_model
        self._cards: dict[str, ModelCard] = {}
        self._workers = dl_workers or {} # 외부에서 관리되는 워커들

        self._build_ui()
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(300)
        self._spinner_timer.timeout.connect(self._tick_spinners)
        self._spinner_timer.start()
        self._spinner_idx = 0
        
        QTimer.singleShot(100, self._update_card_statuses)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

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
            "아래 모델을 선택하거나 설치하세요. 설치된 모델만 벤치마크에 사용 가능합니다."
        )
        subtitle.setStyleSheet("color: #64748b; font-size: 11px;")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(0, 0, 0, 0)

        for cat_name, cat_meta in CATEGORY_META.items():
            grp = QGroupBox(f"{cat_meta['icon']}  {cat_name}  —  {cat_meta['desc']}")
            grp.setStyleSheet(
                f"QGroupBox {{ border-color: {cat_meta['color']}; color: {cat_meta['color']}; }}"
                f"QGroupBox::title {{ color: {cat_meta['color']}; }}"
            )
            grp_layout = QVBoxLayout(grp)
            grp_layout.setSpacing(6)

            for info in MODEL_CATALOGUE:
                if info["category"] != cat_name:
                    continue
                installed  = self._is_installed(info)
                is_current = (info["ollama_tag"] == self._current_model) or (info["id"] == self._current_model)
                card = ModelCard(info, installed, is_current, ollama_on=self._is_ollama_installed(info["ollama_tag"]))
                card.install_clicked.connect(self._on_install)
                card.select_clicked.connect(self._on_select)
                
                try: card.btn_ollama.clicked.disconnect() 
                except: pass
                card.btn_ollama.clicked.connect(lambda _, m=info: self._on_ollama_pull(m))
                
                self._cards[info["id"]] = card
                grp_layout.addWidget(card)

            content_layout.addWidget(grp)

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        self._footer_note = QLabel(f"📁 모델 저장 경로: {MODELS_DIR}")
        self._footer_note.setStyleSheet("color: #475569; font-size: 10px;")
        footer.addWidget(self._footer_note)
        footer.addStretch()

        close_btn = QPushButton("✖  닫기")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedWidth(90)
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    def _is_installed(self, info: dict) -> bool:
        path = os.path.join(MODELS_DIR, info["filename"])
        return os.path.isfile(path)

    def _is_ollama_installed(self, ollama_tag: str) -> bool:
        models = OllamaClient.list_local_models()
        tags = [m["name"] for m in models]
        return ollama_tag in tags or f"{ollama_tag}:latest" in tags

    def _update_card_statuses(self):
        for mid, card in self._cards.items():
            info = card._info
            gguf_on = self._is_installed(info)
            ollama_on = self._is_ollama_installed(info["ollama_tag"])
            is_current = (info["ollama_tag"] == self._current_model) or (info["id"] == self._current_model)

            card._update_btn_state(gguf_on, is_current, ollama_on)

            if is_current:
                card.setStyleSheet("QFrame#ModelCard { background-color: #162032; border: 1.5px solid #3b82f6; border-radius: 10px; }")
            else:
                card.setStyleSheet("QFrame#ModelCard { background-color: #162032; border: 1px solid #2d3f55; border-radius: 10px; }")

    def _on_install(self, info: dict):
        model_id = info["id"]
        if model_id in self._workers: return
        self.install_requested.emit(info, False)
        # UI 업데이트는 _workers가 외부에서 갱신되거나, 타임에 의해 동기화됨
        # (여기서는 일단 즉시 spinner만 켜줌)
        card = self._cards[model_id]
        card.set_installing(is_ollama=False)
        self._workers[model_id] = True # 임시 마킹

    def _on_ollama_pull(self, info: dict):
        model_id = info["id"]
        if model_id in self._workers: return
        self.install_requested.emit(info, True)
        card = self._cards[model_id]
        card.set_installing(is_ollama=True)
        self._workers[model_id] = True # 임시 마킹

    def _on_progress(self, model_id: str, pct: int):
        card = self._cards.get(model_id)
        if card:
            card._progress.setValue(pct)

    def _on_done(self, success: bool, model_id: str):
        # 이제 완료 처리는 중앙에서 관리하지만, 열려있는 창의 UI 갱신을 위해 남겨둠
        self._update_card_statuses()
        card = self._cards.get(model_id)
        if card: card.set_installed()
        if success:
            self._status_lbl.setText(f"✅ {model_id} 설치 완료!")
        else:
            self._status_lbl.setText(f"❌ {model_id} 설치 실패")

    def _on_select(self, model_name: str, engine_type: str):
        self._current_model = model_name
        self.model_selected.emit(model_name, engine_type)
        self.close()

    def _tick_spinners(self):
        frames = ["⏳", "⌛", "⏰", "⏱️"]
        self._spinner_idx = (self._spinner_idx + 1) % len(frames)
        
        # main.py의 실제 일꾼 목록과 동기화하여 UI 업데이트
        for mid, card in self._cards.items():
            if mid in self._workers:
                card._spinner_lbl.show()
                card._spinner_lbl.setText(frames[self._spinner_idx])
                
                # 만약 실제 Worker 객체라면 진행률도 업데이트
                worker = self._workers[mid]
                if hasattr(worker, 'progress_signal'):
                    # (이미 연결되어 있지 않다면 연결) - QThread 특성상 중복 연결 방지 필요
                    pass 
            else:
                card._spinner_lbl.hide()
