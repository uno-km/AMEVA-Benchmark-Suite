from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLabel, QHeaderView, 
                             QDialog, QFormLayout, QLineEdit, QTextEdit, QComboBox, QMessageBox)
from PySide6.QtCore import Qt
import csv
import os

class HarnessEditDialog(QDialog):
    """추가/수정을 위한 팝업 다이얼로그"""
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("하네스 태스크 편집")
        self.setMinimumWidth(500)
        layout = QFormLayout(self)
        
        self.task_input = QLineEdit(data['task'] if data else "")
        self.prompt_input = QTextEdit(data['prompt'] if data else "")
        self.regex_input = QLineEdit(data['expected_regex'] if data else "")
        self.eval_combo = QComboBox()
        self.eval_combo.addItems(["regex", "llm_judge"])
        if data: self.eval_combo.setCurrentText(data['eval_type'])
        
        layout.addRow("태스크명:", self.task_input)
        layout.addRow("프롬프트:", self.prompt_input)
        layout.addRow("정규표현식(Regex):", self.regex_input)
        layout.addRow("평가방식:", self.eval_combo)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("확인")
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
    def __init__(self, controller):
        super().__init__()
        self.ctrl = controller
        self.fname = "harness_v4.csv"
        self._setup_ui()
        self.load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("⚙️ 하네스(테스트 데이터셋) 매니저")
        title.setStyleSheet("font-size: 20pt; font-weight: bold; color: #00ffcc; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # 테이블 설정
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Task", "Prompt", "Expected Regex", "Eval Type"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("background-color: #1e293b; color: white; gridline-color: #334155;")
        layout.addWidget(self.table)
        
        # 버튼 영역
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ 태스크 추가")
        add_btn.clicked.connect(self.add_row)
        edit_btn = QPushButton("📝 선택 수정")
        edit_btn.clicked.connect(self.edit_row)
        del_btn = QPushButton("🗑️ 삭제")
        del_btn.clicked.connect(self.delete_row)
        save_btn = QPushButton("💾 CSV 저장")
        save_btn.setStyleSheet("background-color: #059669; font-weight: bold;")
        save_btn.clicked.connect(self.save_to_csv)
        back_btn = QPushButton("◀ 뒤로가기")
        back_btn.clicked.connect(lambda: self.ctrl.stack.setCurrentIndex(0))
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(back_btn)
        layout.addLayout(btn_layout)

    def load_data(self):
        if not os.path.exists(self.fname): return
        self.table.setRowCount(0)
        with open(self.fname, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                r_idx = self.table.rowCount()
                self.table.insertRow(r_idx)
                self.table.setItem(r_idx, 0, QTableWidgetItem(row['task']))
                self.table.setItem(r_idx, 1, QTableWidgetItem(row['prompt']))
                self.table.setItem(r_idx, 2, QTableWidgetItem(row['expected_regex']))
                self.table.setItem(r_idx, 3, QTableWidgetItem(row['eval_type']))

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
            QMessageBox.information(self, "성공", "하네스 데이터가 CSV에 영구 저장되었습니다!")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")