from ui.qt_bridge import *
from typing import Optional


# ── Palette ────────────────────────────────────────────────────────────────
_BG        = "#0d1522"
_SURFACE   = "#1e293b"
_BORDER    = "#2d3f55"
_PRIMARY   = "#3b82f6"
_ACCENT    = "#10b981"
_TEXT      = "#e2e8f0"
_TEXT_DIM  = "#94a3b8"
_USER_BG   = "#1d4ed8"
_AI_BG     = "#1e293b"
_INPUT_BG  = "#162032"

PANEL_WIDTH = 430


_PANEL_QSS = f"""
QWidget#ChatPanelRoot {{
    background-color: {_BG};
    border-left: 1px solid {_BORDER};
}}
QLabel#ChatHeader {{
    color: {_TEXT};
    font-weight: 800;
    font-size: 13px;
    font-family: 'Inter','Segoe UI',sans-serif;
}}
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QWidget#MessageArea {{
    background-color: transparent;
}}
QLineEdit#ChatInput {{
    background-color: {_INPUT_BG};
    border: 1px solid {_BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    color: {_TEXT};
    font-size: 12px;
    font-family: 'Inter','Segoe UI',sans-serif;
    selection-background-color: {_PRIMARY};
}}
QLineEdit#ChatInput:focus {{
    border-color: {_PRIMARY};
    background-color: #1a2940;
}}
QPushButton#SendBtn {{
    background-color: {_PRIMARY};
    border: none;
    border-radius: 8px;
    color: white;
    font-weight: 700;
    font-size: 14px;
    padding: 0;
}}
QPushButton#SendBtn:hover {{
    background-color: #2563eb;
}}
QPushButton#SendBtn:disabled {{
    background-color: #334155;
    color: {_TEXT_DIM};
}}
QPushButton#ClearBtn {{
    background-color: transparent;
    border: 1px solid {_BORDER};
    border-radius: 6px;
    color: {_TEXT_DIM};
    font-size: 11px;
    padding: 3px 8px;
}}
QPushButton#ClearBtn:hover {{
    border-color: #ef4444;
    color: #ef4444;
}}
"""


class _BubbleWidget(QFrame):
    """단일 말풍선 위젯"""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self._label = None
        self._build(text, is_user)

    def _build(self, text: str, is_user: bool):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(0)

        bubble = QFrame()
        bubble.setObjectName("UserBubble" if is_user else "AIBubble")

        bg     = _USER_BG if is_user else _AI_BG
        radius = "16px 16px 4px 16px" if is_user else "16px 16px 16px 4px"
        border = "none" if is_user else f"1px solid {_BORDER}"

        bubble.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border-radius: {radius};"
            f" border: {border}; padding: 8px 12px; }}"
        )
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        bubble.setMaximumWidth(320)

        vl = QVBoxLayout(bubble)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(2)

        # 역할 레이블
        role_lbl = QLabel("You" if is_user else "🤖 AI")
        role_lbl.setStyleSheet(
            f"color: {'#93c5fd' if is_user else _ACCENT};"
            " font-size: 10px; font-weight: 700; background: transparent; border: none;"
        )
        vl.addWidget(role_lbl)

        # 텍스트
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._label.setStyleSheet(
            f"color: {_TEXT}; font-size: 12px;"
            " background: transparent; border: none;"
            " font-family: 'Inter','Segoe UI',sans-serif;"
        )
        vl.addWidget(self._label)

        if is_user:
            outer.addStretch()
        outer.addWidget(bubble)
        if not is_user:
            outer.addStretch()

    def append_text(self, chunk: str):
        """스트리밍 청크를 레이블에 append."""
        if self._label:
            self._label.setText(self._label.text() + chunk)


class ChatPanel(QWidget):
    """슬라이딩 채팅 사이드바 (QPropertyAnimation 기반)."""

    chat_submitted = Signal(str)    # 사용자가 전송한 프롬프트
    chat_interrupted = Signal()    # 사용자가 중단 버튼 클릭

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatPanelRoot")

        # 초기값: 숨김
        self.setMaximumWidth(0)
        self.setMinimumWidth(0)

        self._anim = QPropertyAnimation(self, b"maximumWidth")
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        self._is_open = False
        self._last_ai_bubble: Optional[_BubbleWidget] = None
        self._waiting = False

        self._build_ui()
        self.setStyleSheet(_PANEL_QSS)

    # ── Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setFixedHeight(46)
        header.setStyleSheet(
            f"QFrame {{ background-color: {_SURFACE};"
            f" border-bottom: 1px solid {_BORDER}; }}"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 10, 0)

        title = QLabel("🗨️  대화형 벤치마크")
        title.setObjectName("ChatHeader")
        hl.addWidget(title)
        hl.addStretch()

        self._clear_btn = QPushButton("🗑 초기화")
        self._clear_btn.setObjectName("ClearBtn")
        self._clear_btn.setFixedHeight(26)
        self._clear_btn.clicked.connect(self._clear_messages)
        hl.addWidget(self._clear_btn)

        root.addWidget(header)

        # Scroll area for bubbles
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._msg_area = QWidget()
        self._msg_area.setObjectName("MessageArea")
        self._msg_layout = QVBoxLayout(self._msg_area)
        self._msg_layout.setContentsMargins(6, 8, 6, 8)
        self._msg_layout.setSpacing(6)
        self._msg_layout.addStretch()   # push bubbles to bottom

        self._scroll.setWidget(self._msg_area)
        root.addWidget(self._scroll, 1)

        # Status bar (shows "⏳ 추론 중..." while waiting)
        self._status_bar = QLabel("")
        self._status_bar.setAlignment(Qt.AlignCenter)
        self._status_bar.setFixedHeight(22)
        self._status_bar.setStyleSheet(
            f"color: {_ACCENT}; font-size: 11px; font-weight: 600;"
            f" background: {_INPUT_BG};"
        )
        root.addWidget(self._status_bar)

        # Input row
        input_frame = QFrame()
        input_frame.setFixedHeight(56)
        input_frame.setStyleSheet(
            f"QFrame {{ background-color: {_INPUT_BG};"
            f" border-top: 1px solid {_BORDER}; }}"
        )
        il = QHBoxLayout(input_frame)
        il.setContentsMargins(10, 8, 10, 8)
        il.setSpacing(8)

        self._input = QLineEdit()
        self._input.setObjectName("ChatInput")
        self._input.setPlaceholderText("벤치마크할 프롬프트를 입력하세요…")
        self._input.returnPressed.connect(self._on_send)

        self._send_btn = QPushButton("➤")
        self._send_btn.setObjectName("SendBtn")
        self._send_btn.setFixedSize(38, 38)
        self._send_btn.clicked.connect(self._on_send)

        self._stop_btn = QPushButton("X")
        self._stop_btn.setObjectName("StopBtn")
        self._stop_btn.setFixedSize(38, 38)
        self._stop_btn.setStyleSheet(
            f"QPushButton#StopBtn {{ background-color: #ef4444; color: white; border-radius: 8px; font-weight: 800; }}"
        )
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)

        il.addWidget(self._input, 1)
        il.addWidget(self._send_btn)
        il.addWidget(self._stop_btn)

        root.addWidget(input_frame)

    # ── Slide animation ────────────────────────────────────────────────────

    def toggle(self):
        """패널 열기/닫기 토글."""
        if self._is_open:
            self._close()
        else:
            self._open()

    def _open(self):
        self._anim.stop()
        self._anim.setStartValue(self.maximumWidth())
        self._anim.setEndValue(PANEL_WIDTH)
        self._anim.start()
        self._is_open = True

    def _close(self):
        self._anim.stop()
        self._anim.setStartValue(self.maximumWidth())
        self._anim.setEndValue(0)
        self._anim.start()
        self._is_open = False

    def is_open(self) -> bool:
        return self._is_open

    # ── Message API ────────────────────────────────────────────────────────

    def append_user_message(self, text: str):
        bubble = _BubbleWidget(text, is_user=True)
        # insert before the bottom stretch
        count = self._msg_layout.count()
        self._msg_layout.insertWidget(count - 1, bubble)
        self._scroll_to_bottom()

    def append_ai_message(self, text: str = ""):
        """AI 빈 말풍선 생성 (스트리밍용 – 이후 append_ai_chunk 사용)."""
        bubble = _BubbleWidget(text, is_user=False)
        count = self._msg_layout.count()
        self._msg_layout.insertWidget(count - 1, bubble)
        self._last_ai_bubble = bubble
        self._scroll_to_bottom()
        return bubble

    def append_ai_chunk(self, chunk: str):
        """마지막 AI 말풍선에 스트리밍 청크 추가."""
        if self._last_ai_bubble:
            self._last_ai_bubble.append_text(chunk)
            self._scroll_to_bottom()

    def set_waiting(self, waiting: bool, msg: str = "⏳ 추론 중…"):
        self._waiting = waiting
        self._status_bar.setText(msg if waiting else "")
        self._send_btn.setEnabled(not waiting)
        self._stop_btn.setEnabled(waiting)
        self._input.setEnabled(not waiting)

    def _on_stop(self):
        self.chat_interrupted.emit()
        self.set_waiting(False, "🛑 중단됨")

    def _clear_messages(self):
        # stretch 제외하고 모두 삭제
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._last_ai_bubble = None

    def _on_send(self):
        if self._waiting:
            return
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.append_user_message(text)
        self.chat_submitted.emit(text)

    def _scroll_to_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())


# Optional type hint fix
from typing import Optional
