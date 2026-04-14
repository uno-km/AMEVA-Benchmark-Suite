from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLabel, QHeaderView, 
                             QDialog, QFormLayout, QLineEdit, QTextEdit, QComboBox, QMessageBox)
from PySide6.QtCore import Qt
import csv
import os

class HarnessEditDialog(QDialog):
    """[V5.5] 하네스 태스크 편집을 위한 스타일 다이얼로그"""
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("태스크 설정")
        self.setMinimumWidth(600)
        
        # 다이얼로그 배경색 설정
        self.setStyleSheet("background-color: #0d1117; color: #c9d1d9;")
        
        layout = QFormLayout(self)
        layout.setSpacing(15)
        
        self.task_input = QLineEdit(data['task'] if data else "")
        self.prompt_input = QTextEdit(data['prompt'] if data else "")
        self.regex_input = QLineEdit(data['expected_regex'] if data else "")
        self.eval_combo = QComboBox()
        self.eval_combo.addItems(["regex", "llm_judge"])
        if data: self.eval_combo.setCurrentText(data['eval_type'])
        
        layout.addRow(QLabel("태스크 식별자:"), self.task_input)
        layout.addRow(QLabel("프롬프트 페이로드:"), self.prompt_input)
        layout.addRow(QLabel("기대 정규표현식:"), self.regex_input)
        layout.addRow(QLabel("평가 유형:"), self.eval_combo)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("💾 변경사항 저장")
        save_btn.setStyleSheet("background-color: #00ffcc; color: #0d1117; font-weight: bold;")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addRow(btns)

    def get_data(self):
        return {
            "task": self.task_input.text(),
            "prompt": self.prompt_input.toPlainText(),
            "expected_regex": self.regex_input.text(),
            "eval_type": self.eval_combo.currentText()
        }

class HarnessManagerUI(QWidget):
    """[V5.5] 리팩토링된 하네스 매니저 - 프리미엄 스타일 및 SRP 흐름 적용."""
    def __init__(self, controller):
        super().__init__()
        self.ctrl = controller
        self.fname = "harness_v4.csv"
        self._setup_ui()
        self.load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        
        header_layout = QHBoxLayout()
        title = QLabel("⚙️ 하네스 데이터셋 아키텍트")
        title.setStyleSheet("font-size: 26px; font-weight: 900; color: #00ffcc; letter-spacing: 1px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.back_btn = QPushButton("◀ 대시보드로 돌아가기")
        self.back_btn.setStyleSheet("background-color: #3b82f6; color: white; border-radius: 6px;")
        self.back_btn.clicked.connect(lambda: self.ctrl.stack.setCurrentIndex(1))
        header_layout.addWidget(self.back_btn)
        
        layout.addLayout(header_layout)
        
        # 프리미엄 다크 스타일 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["태스크", "프롬프트", "정규표현식", "평가 유형"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #010409;
                gridline-color: #30363d;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                padding: 10px;
                border: 1px solid #30363d;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.table)
        
        # 툴바 영역
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ 새 태스크")
        add_btn.clicked.connect(self.add_row)
        
        edit_btn = QPushButton("📝 선택 수정")
        edit_btn.clicked.connect(self.edit_row)
        
        del_btn = QPushButton("🗑️ 삭제")
        del_btn.setStyleSheet("color: #ef4444;")
        del_btn.clicked.connect(self.delete_row)
        
        save_btn = QPushButton("💾 CSV 커밋")
        save_btn.setObjectName("BootButton") 
        save_btn.setStyleSheet("background-color: #00ffcc; color: #0d1117; font-weight: 900;")
        save_btn.clicked.connect(self.save_to_csv)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def load_data(self):
        """기존 하네스 데이터를 로드합니다."""
        if not os.path.exists(self.fname): return
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

    def add_row(self):
        dialog = HarnessEditDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            r_idx = self.table.rowCount()
            self.table.insertRow(r_idx)
            for i, key in enumerate(['task', 'prompt', 'expected_regex', 'eval_type']):
                self.table.setItem(r_idx, i, QTableWidgetItem(data[key]))

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

    def delete_row(self):
        curr = self.table.currentRow()
        if curr >= 0: self.table.removeRow(curr)

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
        except Exception as e:
            QMessageBox.critical(self, "오류", f"I/O 에러: {e}")