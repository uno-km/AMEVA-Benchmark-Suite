"""
harness_ui.py  –  AMEVA Harness Manager (V5.6)
테이블 가독성 대폭 개선 + 공통 DataTableDialog 활용
"""
from ui.qt_bridge import *
import csv
import os

# ─────────────────────────────────────────────────────────────────────────────
# Default harness data
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_HARNESS = [
    {"task": "K-Math-Basic",        "prompt": "영희는 사과 12개, 철수는 영희의 절반보다 2개 더 많고, 민수는 철수보다 3개 적어. 총 합계는?",   "expected_regex": r"\b23\b",                              "eval_type": "regex"},
    {"task": "K-Logic-Intermediate","prompt": "A가 B보다 3살 많고, B는 C보다 2살 어리다. C가 10살이면 A는 몇 살인가?",                          "expected_regex": r"\b11\b",                              "eval_type": "regex"},
    {"task": "K-Grammar",           "prompt": "'나 어제 밥 먹다가 이빨 빠졌어'를 비즈니스 극존칭으로 바꿔.",                                    "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "K-Coding",            "prompt": "리스트에서 짝수만 골라 제곱 후 내림차순 정렬하는 파이썬 함수를 짜줘.",                            "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "K-Reasoning",         "prompt": "철수는 매일 아침 7시에 출근하고, 지하철로 30분 걸린다. 8시에 회의가 시작되면 몇 시까지 집에서 출발해야 할까?", "expected_regex": "",                              "eval_type": "llm_judge"},
    {"task": "K-Hallucination",     "prompt": "세종대왕의 맥북 던짐 사건에 대해 자세히 설명해줘.",                                              "expected_regex": r"\b(없습니다|사실이|허구|데이터가)\b", "eval_type": "regex"},
    {"task": "K-Context",           "prompt": "오늘은 비가 와서 우산을 챙겼다. 그런데 우산을 깜빡하고 집에 두고 왔다. 다음 행동을 추천해줘.",    "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "E-Math",              "prompt": "150 dollars with 20% discount and then 10% tax added. Final price?",                            "expected_regex": r"\b132\b",                             "eval_type": "regex"},
    {"task": "E-Formal",            "prompt": "Rewrite 'I can't make it to the meeting' into a formal business email.",                        "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "E-Logic",             "prompt": "I have 3 brothers. Each has one sister. How many sisters do I have?",                           "expected_regex": r"\b(?:1|one)\b",                       "eval_type": "regex"},
    {"task": "E-Coding",            "prompt": "Write a Python function that returns the Fibonacci sequence up to n.",                          "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "E-CommonSense",       "prompt": "If you spill water on your laptop keyboard, what should you do first?",                        "expected_regex": "",                                     "eval_type": "llm_judge"},
    {"task": "K-E-Mixed",           "prompt": "'The deadline has been moved up to tomorrow'를 한글로 번역하고, 기한이 '당겨졌는지' 혹은 '미뤄졌는지' 판단해서 한글로 답한 뒤, 마감일을 뜻하는 영어 단어를 써줘.", "expected_regex": "", "eval_type": "llm_judge"},
    {"task": "Bilingual-Reasoning", "prompt": "Please explain in Korean why '프로젝트가 연기되었습니다' means the deadline was delayed, not advanced.", "expected_regex": "",                              "eval_type": "llm_judge"},
    {"task": "Bilingual-Logic",     "prompt": "If today is 월요일 and the event moved to Friday, write one sentence in Korean and one in English describing the new schedule.", "expected_regex": "", "eval_type": "llm_judge"},
]
DEFAULT_HARNESS_FIELDS = ["task", "prompt", "expected_regex", "eval_type"]

# ─────────────────────────────────────────────────────────────────────────────
# Shared style palette
# ─────────────────────────────────────────────────────────────────────────────
_BG      = "#0f172a"
_SURFACE = "#1e293b"
_SURF2   = "#162032"
_BORDER  = "#334155"
_PRIMARY = "#3b82f6"
_TEXT    = "#e2e8f0"
_DIM     = "#94a3b8"
_ACCENT  = "#10b981"
_HDR_BG  = "#1a2744"

_TABLE_QSS = f"""
QTableWidget {{
    background-color: {_SURFACE};
    alternate-background-color: {_SURF2};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 8px;
    gridline-color: #253347;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
    font-size: 12px;
    outline: 0;
}}
QTableWidget::item {{
    padding: 8px 10px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: #1d4ed8;
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: {_HDR_BG};
    color: {_PRIMARY};
    border: none;
    border-right: 1px solid {_BORDER};
    border-bottom: 2px solid {_PRIMARY};
    padding: 8px 10px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
}}
QScrollBar:vertical {{
    background: {_SURFACE}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {_BORDER}; border-radius: 4px; min-height: 30px;
}}
QScrollBar:horizontal {{
    background: {_SURFACE}; height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {_BORDER}; border-radius: 4px; min-width: 30px;
}}
"""

_DIALOG_QSS = f"""
QDialog {{
    background-color: {_BG};
    color: {_TEXT};
    font-family: 'Inter','Segoe UI',sans-serif;
}}
QLabel {{ color: {_TEXT}; border: none; }}
QLineEdit, QTextEdit, QComboBox {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {_TEXT};
    font-size: 12px;
    selection-background-color: {_PRIMARY};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {_PRIMARY};
}}
QComboBox QAbstractItemView {{
    background-color: {_SURFACE};
    color: {_TEXT};
    selection-background-color: {_PRIMARY};
}}
QPushButton {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    color: {_TEXT};
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: #2d3e50;
    border-color: {_PRIMARY};
}}
QPushButton#SaveBtn {{
    background-color: {_PRIMARY};
    border: none;
    color: white;
}}
QPushButton#SaveBtn:hover {{ background-color: #2563eb; }}
QPushButton#DeleteBtn {{
    color: #fca5a5;
    border-color: #450a0a;
}}
QPushButton#DeleteBtn:hover {{
    background-color: #450a0a;
    border-color: #ef4444;
}}
QPushButton#CommitBtn {{
    background-color: {_ACCENT};
    border: none;
    color: white;
    font-weight: 700;
}}
QPushButton#CommitBtn:hover {{ background-color: #059669; }}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Edit Dialog
# ─────────────────────────────────────────────────────────────────────────────

class HarnessEditDialog(QDialog):
    """[V5.6] 하네스 태스크 편집 다이얼로그 – 다크 모드 개편."""

    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Task Configuration")
        self.setMinimumWidth(680)
        self.setStyleSheet(_DIALOG_QSS)

        layout = QFormLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def _hdr(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {_DIM}; font-size: 10px; font-weight: 700;")
            return lbl

        self.task_input   = QLineEdit(data["task"]   if data else "")
        self.prompt_input = QTextEdit(data["prompt"] if data else "")
        self.prompt_input.setMinimumHeight(140)
        self.regex_input  = QLineEdit(data.get("expected_regex", "") if data else "")
        self.eval_combo   = QComboBox()
        self.eval_combo.addItems(["regex", "llm_judge"])
        if data:
            self.eval_combo.setCurrentText(data.get("eval_type", "llm_judge"))

        layout.addRow(_hdr("TASK ID"), self.task_input)
        layout.addRow(_hdr("PROMPT"), self.prompt_input)
        layout.addRow(_hdr("REGEX"), self.regex_input)
        layout.addRow(_hdr("EVAL TYPE"), self.eval_combo)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        save_btn = QPushButton("💾 저장")
        save_btn.setObjectName("SaveBtn")
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self.accept)
        btns.addWidget(save_btn)

        layout.addRow(btns)

    def get_data(self):
        return {
            "task":             self.task_input.text(),
            "prompt":           self.prompt_input.toPlainText(),
            "expected_regex":   self.regex_input.text(),
            "eval_type":        self.eval_combo.currentText(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main Harness Manager Dialog
# ─────────────────────────────────────────────────────────────────────────────

class HarnessManagerUI(QDialog):
    """[V5.6] 하네스 매니저 – 프리미엄 다크 테이블 + 가독성 개선."""

    def __init__(self, controller):
        super().__init__(controller)
        self.setModal(True)
        self.setWindowTitle("HARNESS DATASET MANAGER")
        self.setMinimumSize(1020, 660)
        self.setStyleSheet(_DIALOG_QSS)
        self.ctrl  = controller
        self.fname = "harness_v4.csv"
        self._setup_ui()
        self._ensure_default_harness()
        self.load_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # ── Header ──────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("📋  HARNESS DATASET MANAGER")
        title.setFont(QFont("Inter", 16, QFont.Bold))
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #f1f5f9;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._count_lbl = QLabel("0 tasks")
        self._count_lbl.setStyleSheet(f"color: {_DIM}; font-size: 11px;")
        hdr.addWidget(self._count_lbl)

        close_btn = QPushButton("✖  닫기")
        close_btn.setStyleSheet(
            "background-color: #450a0a; border: 1px solid #ef4444;"
            " color: #fca5a5; border-radius: 6px; padding: 6px 14px;"
        )
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)
        root.addLayout(hdr)

        # ── Separator ───────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {_BORDER};")
        root.addWidget(sep)

        # ── Table ───────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["TASK ID", "PROMPT", "REGEX 패턴", "평가 방식"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(_TABLE_QSS)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        root.addWidget(self.table, 1)

        # ── Toolbar ──────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.status_label = QLabel("harness_v4.csv 로드됨")
        self.status_label.setStyleSheet(f"color: {_DIM}; font-size: 11px;")
        toolbar.addWidget(self.status_label)
        toolbar.addStretch()

        view_btn = QPushButton("👁 미리보기")
        view_btn.setToolTip("전체 데이터 TeamTable 뷰어 열기")
        view_btn.clicked.connect(self._open_viewer)

        add_btn = QPushButton("➕ NEW TASK")
        add_btn.clicked.connect(self.add_row)

        edit_btn = QPushButton("📝 편집")
        edit_btn.clicked.connect(self.edit_row)

        del_btn = QPushButton("🗑️ 삭제")
        del_btn.setObjectName("DeleteBtn")
        del_btn.clicked.connect(self.delete_row)

        commit_btn = QPushButton("💾 COMMIT TO CSV")
        commit_btn.setObjectName("CommitBtn")
        commit_btn.setFixedWidth(160)
        commit_btn.clicked.connect(self.save_to_csv)

        for btn in [view_btn, add_btn, edit_btn, del_btn, commit_btn]:
            toolbar.addWidget(btn)

        root.addLayout(toolbar)

    # ── Data ──────────────────────────────────────────────────────────────

    def _ensure_default_harness(self):
        if os.path.exists(self.fname):
            return
        try:
            with open(self.fname, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=DEFAULT_HARNESS_FIELDS)
                writer.writeheader()
                for row in DEFAULT_HARNESS:
                    writer.writerow(row)
        except Exception as e:
            print(f"기본 하네스 생성 실패: {e}")

    def load_data(self):
        self._ensure_default_harness()
        self.table.setRowCount(0)
        try:
            with open(self.fname, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    r_idx = self.table.rowCount()
                    self.table.insertRow(r_idx)
                    self._set_row(r_idx, row)
        except Exception as e:
            print(f"하네스 로드 에러: {e}")
        self.status_label.setText(f"✅ {self.fname} 로드 완료")
        self._count_lbl.setText(f"{self.table.rowCount()} tasks")

    def _set_row(self, r_idx: int, row: dict):
        """행 데이터를 컬럼에 채우고 색상 강조를 적용합니다."""
        vals = [
            row.get("task", ""),
            row.get("prompt", ""),
            row.get("expected_regex", ""),
            row.get("eval_type", ""),
        ]
        for c_idx, val in enumerate(vals):
            item = QTableWidgetItem(val)
            item.setToolTip(val)

            # eval_type 색상 강조
            if c_idx == 3:
                if val == "llm_judge":
                    item.setForeground(QColor("#60a5fa"))  # 파랑
                else:
                    item.setForeground(QColor("#34d399"))  # 초록

            # task 굵게
            if c_idx == 0:
                fnt = item.font()
                fnt.setWeight(QFont.Bold)
                item.setFont(fnt)
                item.setForeground(QColor("#f1f5f9"))

            self.table.setItem(r_idx, c_idx, item)

    # ── CRUD ──────────────────────────────────────────────────────────────

    def add_row(self):
        dialog = HarnessEditDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            r_idx = self.table.rowCount()
            self.table.insertRow(r_idx)
            self._set_row(r_idx, data)
            self.status_label.setText("⚠ 미저장 변경: 새 태스크 추가됨")
            self._count_lbl.setText(f"{self.table.rowCount()} tasks")

    def edit_row(self):
        curr = self.table.currentRow()
        if curr < 0:
            return
        data = {
            "task":           self.table.item(curr, 0).text(),
            "prompt":         self.table.item(curr, 1).text(),
            "expected_regex": self.table.item(curr, 2).text(),
            "eval_type":      self.table.item(curr, 3).text(),
        }
        dialog = HarnessEditDialog(data, parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            self._set_row(curr, new_data)
            self.status_label.setText("⚠ 미저장 변경: 태스크 편집됨")

    def delete_row(self):
        curr = self.table.currentRow()
        if curr >= 0:
            self.table.removeRow(curr)
            self.status_label.setText("⚠ 미저장 변경: 태스크 삭제됨")
            self._count_lbl.setText(f"{self.table.rowCount()} tasks")

    def save_to_csv(self):
        try:
            with open(self.fname, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=DEFAULT_HARNESS_FIELDS)
                writer.writeheader()
                for r in range(self.table.rowCount()):
                    writer.writerow({
                        "task":           self.table.item(r, 0).text(),
                        "prompt":         self.table.item(r, 1).text(),
                        "expected_regex": self.table.item(r, 2).text(),
                        "eval_type":      self.table.item(r, 3).text(),
                    })
            QMessageBox.information(self, "저장 완료", f"✅ {self.fname} 에 동기화되었습니다.")
            self.status_label.setText(f"✅ {self.fname} 저장 완료")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"I/O 오류: {e}")

    def _open_viewer(self):
        from ui.data_table_dialog import open_harness_viewer
        open_harness_viewer(self.fname, parent=self)