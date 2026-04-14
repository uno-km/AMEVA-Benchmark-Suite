class PremiumStyle:
    """[V5.5] Premium UI Theme System - Dynamic Light/Dark Support"""
    
    @staticmethod
    def get_qss(is_dark=True):
        if is_dark:
            p = {
                "PRIMARY": "#3b82f6",
                "ACCENT": "#10b981",
                "DANGER": "#ef4444",
                "WARNING": "#f59e0b",
                "BG_DARK": "#0f172a",
                "SURFACE": "#1e293b",
                "BORDER": "#334155",
                "TEXT_MAIN": "#f8fafc",
                "TEXT_DIM": "#94a3b8",
                "INPUT_BG": "#020617",
                "TAB_PANE": "#0f172a"
            }
        else:
            p = {
                "PRIMARY": "#2563eb",
                "ACCENT": "#059669",
                "DANGER": "#dc2626",
                "WARNING": "#d97706",
                "BG_DARK": "#f1f5f9",
                "SURFACE": "#ffffff",
                "BORDER": "#cbd5e1",
                "TEXT_MAIN": "#0f172a",
                "TEXT_DIM": "#475569",
                "INPUT_BG": "#f8fafc",
                "TAB_PANE": "#ffffff"
            }

        return f"""
            QMainWindow, QWidget {{
                background-color: {p['BG_DARK']};
                color: {p['TEXT_MAIN']};
                font-family: 'Inter', 'Segoe UI', 'Roboto', sans-serif;
                font-size: 12px;
            }}

            QGroupBox {{
                border: 1px solid {p['BORDER']};
                border-radius: 8px;
                margin-top: 14px;
                font-weight: 700;
                font-size: 11px;
                color: {p['TEXT_DIM']};
                padding: 12px 14px 10px 14px;
                background-color: {p['SURFACE']};
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }}

            QPushButton {{
                background-color: {p['SURFACE']};
                border: 1px solid {p['BORDER']};
                border-radius: 6px;
                color: {p['TEXT_MAIN']};
                padding: 7px 16px;
                font-weight: 600;
                font-size: 12px;
            }}

            QPushButton:hover {{
                background-color: {"#2d3e50" if is_dark else "#f1f5f9"};
                border-color: {p['PRIMARY']};
            }}

            QPushButton:checked {{
                background-color: {p['PRIMARY']};
                color: white;
                border-color: {p['PRIMARY']};
            }}

            QPushButton:checked:hover {{
                background-color: {"#2563eb" if is_dark else "#1d4ed8"};
            }}

            QPushButton#BootButton, QPushButton#RunButton {{
                background-color: {p['PRIMARY']};
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 700;
            }}

            QPushButton#BootButton:hover, QPushButton#RunButton:hover {{
                background-color: {"#2563eb" if is_dark else "#1d4ed8"};
            }}

            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                background-color: {p['INPUT_BG']};
                border: 1px solid {p['BORDER']};
                border-radius: 5px;
                padding: 5px 8px;
                color: {p['TEXT_MAIN']};
                min-height: 26px;
            }}

            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {p['PRIMARY']};
            }}

            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {p['SURFACE']};
                border: 1px solid {p['BORDER']};
                selection-background-color: {p['PRIMARY']};
                color: {p['TEXT_MAIN']};
            }}

            QTextEdit {{
                background-color: {p['INPUT_BG']};
                border: 1px solid {p['BORDER']};
                border-radius: 6px;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 11px;
                color: {p['TEXT_MAIN']};
                padding: 8px;
            }}

            QProgressBar {{
                border: 1px solid {p['BORDER']};
                background-color: {p['INPUT_BG']};
                border-radius: 6px;
                text-align: center;
                font-weight: bold;
                font-size: 11px;
                max-height: 16px;
            }}

            QProgressBar::chunk {{
                background-color: {p['PRIMARY']};
                border-radius: 5px;
            }}

            QTabWidget::pane {{
                border: 1px solid {p['BORDER']};
                border-radius: 8px;
                background-color: {p['TAB_PANE']};
            }}

            QTabBar::tab {{
                background: {p['SURFACE']};
                color: {p['TEXT_DIM']};
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 11px;
            }}

            QTabBar::tab:selected {{
                background: {p['BG_DARK']};
                color: {p['PRIMARY']};
                border-bottom: 2px solid {p['PRIMARY']};
            }}

            QLabel#HeaderLabel {{
                font-size: 22px;
                font-weight: 800;
                color: {p['TEXT_MAIN']};
            }}

            QLabel#SubHeaderLabel {{
                font-size: 11px;
                color: {p['TEXT_DIM']};
            }}

            QScrollBar:vertical {{
                background: {p['SURFACE']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {p['BORDER']};
                border-radius: 4px;
                min-height: 30px;
            }}
        """
