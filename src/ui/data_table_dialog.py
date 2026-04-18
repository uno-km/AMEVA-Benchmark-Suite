"""
data_table_dialog.py  –  공통 데이터 테이블 뷰어 (리포트 / 하네스 공용)
[V5.6] Premium readable dark-mode QDialog with alternating row colors,
       column auto-fit, search filter, and export shortcut.
"""

import csv
from typing import List, Dict, Optional

from ui.qt_bridge import *


# ─────────────────────────────────────────────────────────────────────────────
# Palette
# ─────────────────────────────────────────────────────────────────────────────
_BG        = "#0f172a"
_SURFACE   = "#1e293b"
_SURFACE2  = "#162032"   # slightly different alt-row
_BORDER    = "#334155"
_PRIMARY   = "#3b82f6"
_TEXT      = "#e2e8f0"
_TEXT_DIM  = "#94a3b8"
_ACCENT    = "#10b981"
_HEADER_BG = "#1a2744"


_DIALOG_QSS = f"""
QDialog {{
    background-color: {_BG};
    color: {_TEXT};
    font-family: 'Inter','Segoe UI',sans-serif;
}}
QLabel {{
    color: {_TEXT};
    border: none;
}}
QLineEdit {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    color: {_TEXT};
    font-size: 12px;
    selection-background-color: {_PRIMARY};
}}
QLineEdit:focus {{
    border-color: {_PRIMARY};
}}
QPushButton {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    color: {_TEXT};
    padding: 6px 16px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: #2d3e50;
    border-color: {_PRIMARY};
}}
QPushButton#CloseBtn {{
    background-color: #450a0a;
    border: 1px solid #ef4444;
    color: #fca5a5;
}}
QPushButton#CloseBtn:hover {{
    background-color: #7f1d1d;
}}
QTableWidget {{
    background-color: {_SURFACE};
    alternate-background-color: {_SURFACE2};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 8px;
    gridline-color: {_BORDER};
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
    font-size: 12px;
    outline: 0;
}}
QTableWidget::item {{
    padding: 6px 10px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: #1d4ed8;
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: {_HEADER_BG};
    color: {_PRIMARY};
    border: none;
    border-right: 1px solid {_BORDER};
    border-bottom: 2px solid {_PRIMARY};
    padding: 8px 10px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
}}
QHeaderView::section:first {{
    border-top-left-radius: 8px;
}}
QHeaderView::section:last {{
    border-top-right-radius: 8px;
    border-right: none;
}}
QScrollBar:vertical {{
    background: {_SURFACE};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {_BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar:horizontal {{
    background: {_SURFACE};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {_BORDER};
    border-radius: 4px;
    min-width: 30px;
}}
"""


class DataTableDialog(QDialog):
    """
    공통 테이블 뷰어 다이얼로그.

    Parameters
    ----------
    title       : 창 제목
    columns     : 컬럼명 리스트
    rows        : List[Dict] — 각 dict 키는 columns 값과 매핑
    parent      : 부모 위젯
    mode        : "report" | "harness"  (아이콘·색상 힌트)
    description : 상단 설명 문자열 (선택)
    """

    def __init__(
        self,
        title: str,
        columns: List[str],
        rows: List[Dict],
        parent=None,
        mode: str = "report",
        description: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(_DIALOG_QSS)
        self.setModal(True)

        self._columns = columns
        self._all_rows = rows
        self._mode = mode

        self._build_ui(title, description)
        self._load_rows(rows)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, title: str, desc: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout()

        icon = "📊" if self._mode == "report" else "📋"
        title_lbl = QLabel(f"{icon}  {title}")
        title_lbl.setFont(QFont("Inter", 16, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 18px; font-weight: 800;")
        hdr.addWidget(title_lbl)
        hdr.addStretch()

        self._row_count_lbl = QLabel("0 rows")
        self._row_count_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        hdr.addWidget(self._row_count_lbl)

        root.addLayout(hdr)

        # ── Description ────────────────────────────────────────────────────
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
            desc_lbl.setWordWrap(True)
            root.addWidget(desc_lbl)

        # ── Separator ──────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {_BORDER};")
        root.addWidget(sep)

        # ── Search bar ─────────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_icon = QLabel("🔍")
        self._search = QLineEdit()
        self._search.setPlaceholderText("검색 필터 (모든 컬럼 대상)…")
        self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(search_icon)
        search_row.addWidget(self._search, 1)

        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet(f"color: {_ACCENT}; font-size: 11px; font-weight: 600;")
        search_row.addWidget(self._stats_lbl)

        root.addLayout(search_row)

        # ── Table ──────────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(len(self._columns))
        self._table.setHorizontalHeaderLabels(self._columns)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setShowGrid(True)
        self._table.verticalHeader().setDefaultSectionSize(36)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)

        hh = self._table.horizontalHeader()
        for i, col in enumerate(self._columns):
            # 넓은 텍스트 컬럼은 Stretch, 나머지는 ResizeToContents
            if any(kw in col.lower() for kw in ["prompt", "response", "text", "reason"]):
                hh.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        root.addWidget(self._table, 1)

        # ── Footer ─────────────────────────────────────────────────────────
        footer = QHBoxLayout()

        self._footer_lbl = QLabel("")
        self._footer_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        footer.addWidget(self._footer_lbl)
        footer.addStretch()

        close_btn = QPushButton("✖  닫기")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)

        root.addLayout(footer)

    # ── Data helpers ─────────────────────────────────────────────────────────

    def _load_rows(self, rows: List[Dict]):
        """rows 데이터를 테이블에 채웁니다."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        for r_idx, row in enumerate(rows):
            self._table.insertRow(r_idx)
            for c_idx, col in enumerate(self._columns):
                value = str(row.get(col, ""))
                item = QTableWidgetItem(value)
                item.setToolTip(value)

                # 특수 컬럼 색상 강조
                low = col.lower()
                if "pass" in value.upper() and "judge" in low:
                    item.setForeground(QColor(_ACCENT))
                elif "fail" in value.upper() and "judge" in low:
                    item.setForeground(QColor("#ef4444"))
                elif "chat_mod" in value.upper():
                    item.setForeground(QColor("#a78bfa"))
                elif "stress" in value.upper():
                    item.setForeground(QColor("#f59e0b"))

                self._table.setItem(r_idx, c_idx, item)

        self._table.setSortingEnabled(True)
        self._update_stats(len(rows))

    def _update_stats(self, visible: int):
        total = len(self._all_rows)
        self._row_count_lbl.setText(f"{visible:,} / {total:,} rows")
        if self._mode == "report" and total > 0:
            # PASS 통계 계산
            pass_col = next(
                (c for c in self._columns if "judge" in c.lower()), None
            )
            if pass_col:
                passes = sum(
                    1 for r in self._all_rows
                    if "PASS" in str(r.get(pass_col, "")).upper()
                )
                pct = passes / total * 100
                self._stats_lbl.setText(
                    f"✅ PASS: {passes}/{total}  ({pct:.1f}%)"
                )
            else:
                self._stats_lbl.setText(f"총 {total}건")
        self._footer_lbl.setText(
            f"마지막 업데이트: 방금 로드됨  |  표시 중: {visible}행"
        )

    def _apply_filter(self, text: str):
        """검색어로 행 필터링."""
        text = text.strip().lower()
        filtered = []
        for row in self._all_rows:
            if not text or any(text in str(v).lower() for v in row.values()):
                filtered.append(row)
        self._load_rows(filtered)
        self._update_stats(len(filtered))


# ─────────────────────────────────────────────────────────────────────────────
# Factory helpers
# ─────────────────────────────────────────────────────────────────────────────

def open_report_viewer(db_path: str, parent=None):
    """Edge_v5_Singularity_Report.csv 를 읽어 뷰어를 팝업합니다."""
    rows = []
    columns = []
    try:
        with open(db_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            rows = list(reader)
    except FileNotFoundError:
        rows = []
        columns = ["(파일 없음)"]
    except Exception as e:
        rows = []
        columns = [f"오류: {e}"]

    dlg = DataTableDialog(
        title="벤치마크 결과 리포트",
        columns=list(columns),
        rows=rows,
        parent=parent,
        mode="report",
        description=f"📁  {db_path}  |  {len(rows)}건의 벤치마크 결과",
    )
    dlg.exec()


def open_harness_viewer(harness_path: str, parent=None):
    """harness_v4.csv 를 읽어 읽기전용 뷰어를 팝업합니다."""
    rows = []
    columns = []
    try:
        with open(harness_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            rows = list(reader)
    except FileNotFoundError:
        rows = []
        columns = ["(파일 없음)"]

    dlg = DataTableDialog(
        title="Harness 테스트셋 뷰어",
        columns=list(columns),
        rows=rows,
        parent=parent,
        mode="harness",
        description=f"📁  {harness_path}  |  편집은 HARNESS MANAGER에서 수행",
    )
    dlg.exec()
