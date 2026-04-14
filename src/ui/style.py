class PremiumStyle:
    """[V5.5] Premium UI Theme - Dark Cyberpunk / Enterprise Look"""
    
    NEON_GREEN = "#00ffcc"
    NEON_BLUE = "#3b82f6"
    NEON_RED = "#ef4444"
    DARK_BG = "#0d1117"
    DARKER_BG = "#010409"
    GRAY_TEXT = "#8b949e"
    BORDER_COLOR = "#30363d"

    MAIN_QSS = f"""
        QMainWindow, QWidget {{
            background-color: {DARK_BG};
            color: #c9d1d9;
            font-family: 'Segoe UI', 'Roboto', sans-serif;
        }}

        QGroupBox {{
            border: 1px solid {BORDER_COLOR};
            border-radius: 8px;
            margin-top: 1.5em;
            font-weight: bold;
            color: {NEON_GREEN};
            padding: 15px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}

        QPushButton {{
            background-color: #21262d;
            border: 1px solid {BORDER_COLOR};
            border-radius: 6px;
            color: #c9d1d9;
            padding: 8px 16px;
            font-weight: 500;
        }}

        QPushButton:hover {{
            background-color: #30363d;
            border-color: {GRAY_TEXT};
        }}

        QPushButton#BootButton {{
            background-color: {NEON_GREEN};
            color: {DARKER_BG};
            font-weight: 900;
            border: none;
            font-size: 14px;
        }}

        QPushButton#BootButton:hover {{
            background-color: #00e6b8;
        }}

        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {DARKER_BG};
            border: 1px solid {BORDER_COLOR};
            border-radius: 4px;
            padding: 5px;
            color: #c9d1d9;
        }}

        QTextEdit {{
            background-color: {DARKER_BG};
            border: 1px solid {BORDER_COLOR};
            border-radius: 6px;
            font-family: 'Consolas', monospace;
            color: {NEON_GREEN};
        }}

        QProgressBar {{
            border: 1px solid {BORDER_COLOR};
            background-color: {DARKER_BG};
            border-radius: 10px;
            text-align: center;
        }}

        QProgressBar::chunk {{
            background-color: {NEON_GREEN};
            border-radius: 9px;
        }}

        QTabWidget::pane {{
            border: 1px solid {BORDER_COLOR};
            border-radius: 4px;
        }}

        QTabBar::tab {{
            background: {DARKER_BG};
            border: 1px solid {BORDER_COLOR};
            padding: 10px 20px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}

        QTabBar::tab:selected {{
            background: {DARK_BG};
            border-bottom-color: {NEON_GREEN};
            color: {NEON_GREEN};
        }}
    """
