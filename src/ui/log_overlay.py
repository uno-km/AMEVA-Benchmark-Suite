from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor


class LogOverlay(QWidget):
    """[V5.5] 전체화면 로그 확장 뷰어 오버레이.
    
    부모 위젯 위를 완전히 덮고, 소스 QTextEdit의 내용을 실시간 동기화합니다.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._source: QTextEdit | None = None
        self._setup()
        self.hide()

    def _setup(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("LogOverlay")
        self.setStyleSheet("background-color: #0f172a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 상단 헤더 바 ──────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(42)
        hdr.setStyleSheet(
            "background-color: #1e293b; border-bottom: 1px solid #334155;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)

        self.title_lbl = QLabel("LOG VIEWER")
        self.title_lbl.setStyleSheet(
            "color: #f8fafc; font-weight: 800; font-size: 13px; border: none;"
        )
        hl.addWidget(self.title_lbl)
        hl.addStretch()

        close_btn = QPushButton("⤡  축소")
        close_btn.setFixedWidth(90)
        close_btn.setStyleSheet(
            "background-color: #334155; color: #f8fafc; border: none;"
            "border-radius: 5px; padding: 4px 10px; font-weight: 600;"
        )
        close_btn.clicked.connect(self.close_overlay)
        hl.addWidget(close_btn)
        layout.addWidget(hdr)

        # ── 텍스트 뷰 ──────────────────────────────────
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setStyleSheet(
            "background-color: #020617; color: #f8fafc; border: none; border-radius: 0;"
            "font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 11px; padding: 12px;"
        )
        layout.addWidget(self.text_view)

    # ── 공개 API ──────────────────────────────────────

    def show_for(self, source: QTextEdit, title: str = "LOG VIEWER"):
        """지정 QTextEdit를 오버레이로 확장 표시합니다."""
        # 이전 소스 연결 해제
        if self._source is not None:
            try:
                self._source.textChanged.disconnect(self._sync)
            except RuntimeError:
                pass

        self._source = source
        self._source.textChanged.connect(self._sync)
        self.title_lbl.setText(title)

        # 현재 내용 복사 후 커서를 맨 아래로
        self.text_view.setPlainText(source.toPlainText())
        self.text_view.moveCursor(QTextCursor.End)

        # 부모 위젯을 전부 덮음
        p = self.parent()
        if p:
            self.setGeometry(0, 0, p.width(), p.height())
        self.raise_()
        self.show()

    def close_overlay(self):
        """오버레이를 닫고 소스 연결을 해제합니다."""
        if self._source is not None:
            try:
                self._source.textChanged.disconnect(self._sync)
            except RuntimeError:
                pass
            self._source = None
        self.hide()

    # ── 내부 슬롯 ─────────────────────────────────────

    def _sync(self):
        """소스 변경 시 오버레이를 실시간 동기화합니다."""
        if self._source is not None:
            self.text_view.setPlainText(self._source.toPlainText())
            self.text_view.moveCursor(QTextCursor.End)

    def resizeEvent(self, event):
        p = self.parent()
        if p and self.isVisible():
            self.setGeometry(0, 0, p.width(), p.height())
        super().resizeEvent(event)
