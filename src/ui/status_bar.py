from ui.qt_bridge import *

class ServiceIndicator(QWidget):
    """상태 표시등 아이콘과 텍스트가 결합된 위젯"""
    clicked = Signal(str)

    def __init__(self, name: str, label: str):
        super().__init__()
        self._name = name
        self._label_text = label
        self._is_online = False
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(6)

        self.led = QLabel("●")
        self.led.setStyleSheet("color: #ef4444; font-size: 14px;") # 기본 레드
        
        self.lbl = QLabel(self._label_text)
        self.lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600;")
        
        layout.addWidget(self.led)
        layout.addWidget(self.lbl)
        
        self.setCursor(Qt.PointingHandCursor)

    def set_status(self, is_online: bool, msg: str):
        self._is_online = is_online
        color = "#22c55e" if is_online else "#ef4444"
        self.led.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.setToolTip(msg)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._name)

class AMEVAStatusBar(QStatusBar):
    """[Engineering] VS Code 스타일의 하단 상태 표시줄"""
    
    service_request = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setSizeGripEnabled(False) # VS Code 스타일을 위해 사이즈 그립 제거
        self.setStyleSheet(
            "QStatusBar { background-color: #1e293b; border-top: 1px solid #334155; }"
            "QStatusBar::item { border: none; }"
        )
        self._build_ui()

    def _build_ui(self):
        # QStatusBar는 자체 레이아웃을 사용하므로 센터 위젯 등을 추가할 때 addWidget/addPermanentWidget 사용
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(15)

        # 1. Docker 지표
        self.docker_ind = ServiceIndicator("docker", "DOCKER")
        self.docker_ind.clicked.connect(self.service_request.emit)
        layout.addWidget(self.docker_ind)

        # 2. Ollama 지표
        self.ollama_ind = ServiceIndicator("ollama", "OLLAMA")
        self.ollama_ind.clicked.connect(self.service_request.emit)
        layout.addWidget(self.ollama_ind)

        layout.addStretch()

        # 3. 추가 정보 (버전 등)
        self.ver_lbl = QLabel("AMEVA v5.6 | CORE ONLINE")
        self.ver_lbl.setStyleSheet("color: #475569; font-size: 9px; font-weight: 700;")
        layout.addWidget(self.ver_lbl)

        self.addPermanentWidget(container, 1)

    def update_service_status(self, name: str, is_online: bool, msg: str):
        if name == "docker":
            self.docker_ind.set_status(is_online, msg)
        elif name == "ollama":
            self.ollama_ind.set_status(is_online, msg)
