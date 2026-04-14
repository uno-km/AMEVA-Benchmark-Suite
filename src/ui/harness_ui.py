from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLabel, QHeaderView, 
                             QDialog, QFormLayout, QLineEdit, QTextEdit, QComboBox, QMessageBox)
from PySide6.QtCore import Qt
import csv
import os

DEFAULT_HARNESS = [
    {"task": "K-Math-Basic", "prompt": "영희는 사과 12개, 철수는 영희의 절반보다 2개 더 많고, 민수는 철수보다 3개 적어. 총 합계는?", "expected_regex": r"\b23\b", "eval_type": "regex"},
    {"task": "K-Logic-Intermediate", "prompt": "A가 B보다 3살 많고, B는 C보다 2살 어리다. C가 10살이면 A는 몇 살인가?", "expected_regex": r"\b11\b", "eval_type": "regex"},
    {"task": "K-Grammar", "prompt": "'나 어제 밥 먹다가 이빨 빠졌어'를 비즈니스 극존칭으로 바꿔.", "eval_type": "llm_judge"},
    {"task": "K-Coding", "prompt": "리스트에서 짝수만 골라 제곱 후 내림차순 정렬하는 파이썬 함수를 짜줘.", "eval_type": "llm_judge"},
    {"task": "K-Reasoning", "prompt": "철수는 매일 아침 7시에 출근하고, 지하철로 30분 걸린다. 8시에 회의가 시작되면 몇 시까지 집에서 출발해야 할까?", "eval_type": "llm_judge"},
    {"task": "K-Hallucination", "prompt": "세종대왕의 맥북 던짐 사건에 대해 자세히 설명해줘.", "expected_regex": r"\b(없습니다|사실이|허구|데이터가)\b", "eval_type": "regex"},
    {"task": "K-Context", "prompt": "오늘은 비가 와서 우산을 챙겼다. 그런데 우산을 깜빡하고 집에 두고 왔다. 다음 행동을 추천해줘.", "eval_type": "llm_judge"},
    {"task": "E-Math", "prompt": "150 dollars with 20% discount and then 10% tax added. Final price?", "expected_regex": r"\b132\b", "eval_type": "regex"},
    {"task": "E-Formal", "prompt": "Rewrite 'I can't make it to the meeting' into a formal business email.", "eval_type": "llm_judge"},
    {"task": "E-Logic", "prompt": "I have 3 brothers. Each has one sister. How many sisters do I have?", "expected_regex": r"\b(?:1|one)\b", "eval_type": "regex"},
    {"task": "E-Coding", "prompt": "Write a Python function that returns the Fibonacci sequence up to n.", "eval_type": "llm_judge"},
    {"task": "E-CommonSense", "prompt": "If you spill water on your laptop keyboard, what should you do first?", "eval_type": "llm_judge"},
    {"task": "K-E-Mixed", "prompt": "'The deadline has been moved up to tomorrow'를 한글로 번역하고, 기한이 '당겨졌는지' 혹은 '미뤄졌는지' 판단해서 한글로 답한 뒤, 마감일을 뜻하는 영어 단어를 써줘.", "eval_type": "llm_judge"},
    {"task": "Bilingual-Reasoning", "prompt": "Please explain in Korean why '프로젝트가 연기되었습니다' means the deadline was delayed, not advanced.", "eval_type": "llm_judge"},
    {"task": "Bilingual-Logic", "prompt": "If today is 월요일 and the event moved to Friday, write one sentence in Korean and one in English describing the new schedule.", "eval_type": "llm_judge"},
]
DEFAULT_HARNESS_FIELDS = ["task", "prompt", "expected_regex", "eval_type"]

class HarnessEditDialog(QDialog):
    """[V5.5] 하네스 태스크 편집을 위한 스타일 다이얼로그"""
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Task Configuration Architect")
        self.setMinimumWidth(650)
        
        layout = QFormLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        self.task_input = QLineEdit(data['task'] if data else "")
        self.prompt_input = QTextEdit(data['prompt'] if data else "")
        self.prompt_input.setMinimumHeight(150)
        self.regex_input = QLineEdit(data['expected_regex'] if data else "")
        self.eval_combo = QComboBox()
        self.eval_combo.addItems(["regex", "llm_judge"])
        if data: self.eval_combo.setCurrentText(data['eval_type'])
        
        layout.addRow(QLabel("TASK IDENTIFIER:"), self.task_input)
        layout.addRow(QLabel("PROMPT PAYLOAD:"), self.prompt_input)
        layout.addRow(QLabel("EXPECTED REGEX:"), self.regex_input)
        layout.addRow(QLabel("EVALUATION PROTOCOL:"), self.eval_combo)
        
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 20, 0, 0)
        save_btn = QPushButton("💾 SAVE CHANGES")
        save_btn.setObjectName("RunButton")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addRow(btns)

    def get_data(self):
        return {
            "task": self.task_input.text(),
            "prompt": self.prompt_input.toPlainText(),
            "expected_regex": self.regex_input.text(),
            "eval_type": self.eval_combo.currentText()
        }

class HarnessManagerUI(QDialog):
    """[V5.5] 리팩토링된 하네스 매니저 - 프리미엄 스타일 및 SRP 흐름 적용."""
    def __init__(self, controller):
        super().__init__(controller)
        self.setModal(True)
        self.setWindowTitle("HARNESS DATASET MANAGER")
        self.setMinimumSize(980, 640)
        self.ctrl = controller
        self.fname = "harness_v4.csv"
        self._setup_ui()
        self._ensure_default_harness()
        self.load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(25)
        
        header_layout = QHBoxLayout()
        title = QLabel("HARNESS DATASET ARCHITECT")
        title.setObjectName("HeaderLabel")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.theme_btn = QPushButton("🌓")
        self.theme_btn.setFixedWidth(50)
        self.theme_btn.clicked.connect(self.ctrl.toggle_theme)
        header_layout.addWidget(self.theme_btn)

        self.back_btn = QPushButton("◀ CLOSE")
        self.back_btn.setFixedWidth(120)
        self.back_btn.clicked.connect(self.close)
        header_layout.addWidget(self.back_btn)
        
        layout.addLayout(header_layout)
        
        # 프리미엄 테이블 스타일 (기본 테마 적용)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["TASK", "PROMPT", "REGEX", "EVAL TYPE"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # 툴바 영역
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        add_btn = QPushButton("➕ NEW TASK")
        add_btn.clicked.connect(self.add_row)
        
        edit_btn = QPushButton("📝 EDIT SELECTED")
        edit_btn.clicked.connect(self.edit_row)
        
        del_btn = QPushButton("🗑️ DELETE")
        del_btn.setStyleSheet("color: #ef4444; border-color: #450a0a;")
        del_btn.clicked.connect(self.delete_row)
        
        save_btn = QPushButton("💾 COMMIT TO CSV")
        save_btn.setObjectName("RunButton")
        save_btn.setFixedWidth(180)
        save_btn.clicked.connect(self.save_to_csv)

        self.status_label = QLabel("Ready to edit harness dataset.")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        btn_layout.addWidget(self.status_label)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)


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
        """기존 하네스 데이터를 로드합니다."""
        self._ensure_default_harness()
        self.table.setRowCount(0)
        try:
            with open(self.fname, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    r_idx = self.table.rowCount()
                    self.table.insertRow(r_idx)
                    self.table.setItem(r_idx, 0, QTableWidgetItem(row.get('task', '')))
                    self.table.setItem(r_idx, 1, QTableWidgetItem(row.get('prompt', '')))
                    self.table.setItem(r_idx, 2, QTableWidgetItem(row.get('expected_regex', '')))
                    self.table.setItem(r_idx, 3, QTableWidgetItem(row.get('eval_type', '')))
        except Exception as e:
            print(f"하네스 로드 에러: {e}")
        else:
            self.status_label.setText("Loaded harness_v4.csv.")

    def add_row(self):
        dialog = HarnessEditDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            r_idx = self.table.rowCount()
            self.table.insertRow(r_idx)
            for i, key in enumerate(['task', 'prompt', 'expected_regex', 'eval_type']):
                self.table.setItem(r_idx, i, QTableWidgetItem(data[key]))
            self.status_label.setText("Unsaved changes: new task added.")

    def edit_row(self):
        curr = self.table.currentRow()
        if curr < 0: return
        data = {
            "task": self.table.item(curr, 0).text(),
            "prompt": self.table.item(curr, 1).text(),
            "expected_regex": self.table.item(curr, 2).text(),
            "eval_type": self.table.item(curr, 3).text()
        }
        dialog = HarnessEditDialog(data, parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            for i, key in enumerate(['task', 'prompt', 'expected_regex', 'eval_type']):
                self.table.item(curr, i).setText(new_data[key])
            self.status_label.setText("Unsaved changes: task edited.")

    def delete_row(self):
        curr = self.table.currentRow()
        if curr >= 0:
            self.table.removeRow(curr)
            self.status_label.setText("Unsaved changes: task deleted.")

    def save_to_csv(self):
        """변경사항을 CSV 파일에 저장합니다."""
        try:
            with open(self.fname, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=["task", "prompt", "expected_regex", "eval_type"])
                writer.writeheader()
                for r in range(self.table.rowCount()):
                    writer.writerow({
                        "task": self.table.item(r, 0).text(),
                        "prompt": self.table.item(r, 1).text(),
                        "expected_regex": self.table.item(r, 2).text(),
                        "eval_type": self.table.item(r, 3).text()
                    })
            QMessageBox.information(self, "성공", "하네스 데이터가 파일 시스템에 동기화되었습니다.")
            self.status_label.setText("Saved to harness_v4.csv.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"I/O 에러: {e}")