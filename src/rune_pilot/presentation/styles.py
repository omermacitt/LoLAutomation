"""
RunePilot Hextech Dark Theme QSS stylesheet.
"""

STYLESHEET = """
QWidget {
    background-color: #010a13;
    color: #cdbe91;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
}

QLabel#appTitle {
    color: #f0e6d2;
    font-size: 22px;
    font-weight: 800;
    padding: 6px 0;
}

QLabel#appSubtitle {
    color: #a09b8c;
    font-size: 12px;
    padding-bottom: 8px;
}

QLabel#cornerStatusLabel {
    padding: 4px 10px;
    border-radius: 12px;
    font-weight: 700;
    border: 1px solid #3c3c3c;
    background-color: #1e282d;
    color: #f0e6d2;
    font-size: 12px;
}

QLabel#cornerStatusLabel[state="running"] {
    background-color: #1aa865;
    border-color: #1aa865;
    color: #010a13;
}

QLabel#cornerStatusLabel[state="stopped"] {
    background-color: #111821;
    border-color: #2b2f36;
    color: #f0e6d2;
}

QLabel#cornerStatusLabel[state="offline"] {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QLabel#cornerStatusLabel[state="checking"],
QLabel#cornerStatusLabel[state="starting"] {
    background-color: #c8aa6e;
    border-color: #c8aa6e;
    color: #010a13;
}

QLabel#cornerStatusLabel[state="stopping"] {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QProgressBar#cornerProgress {
    background-color: #111821;
    border: 1px solid #2b2f36;
    border-radius: 5px;
}

QProgressBar#cornerProgress::chunk {
    background-color: #c8aa6e;
    border-radius: 4px;
}

QProgressBar#cornerProgress[state="running"]::chunk {
    background-color: #1aa865;
}

QProgressBar#cornerProgress[state="offline"]::chunk,
QProgressBar#cornerProgress[state="stopping"]::chunk {
    background-color: #d64545;
}

QLabel#automationStatus {
    padding: 6px 12px;
    border-radius: 16px;
    font-weight: 700;
    border: 1px solid #3c3c3c;
    background-color: #1e282d;
    color: #f0e6d2;
    min-width: 190px;
}

QLabel#automationStatus[state="running"] {
    background-color: #1aa865;
    border-color: #1aa865;
    color: #010a13;
}

QLabel#automationStatus[state="stopped"] {
    background-color: #111821;
    border-color: #2b2f36;
    color: #f0e6d2;
}

QLabel#automationStatus[state="offline"] {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QLabel#automationStatus[state="checking"],
QLabel#automationStatus[state="starting"] {
    background-color: #c8aa6e;
    border-color: #c8aa6e;
    color: #010a13;
}

QLabel#automationStatus[state="stopping"] {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QGroupBox {
    border: 1px solid #c8aa6e;
    border-radius: 4px;
    margin-top: 20px;
    font-weight: bold;
    color: #f0e6d2;
    background-color: rgba(30, 40, 45, 120);
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 10px;
    color: #c8aa6e;
}

QLabel {
    color: #a09b8c;
}

QComboBox {
    background-color: #1e282d;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px;
    color: #f0e6d2;
    min-height: 20px;
}

QComboBox:hover {
    border: 1px solid #c8aa6e;
}

QComboBox:focus {
    border: 1px solid #c8aa6e;
}

QComboBox QAbstractItemView {
    background-color: #0b151f;
    border: 1px solid #3c3c3c;
    selection-background-color: #c8aa6e;
    selection-color: #010a13;
    padding: 4px;
    outline: 0;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

QTabWidget::pane {
    border: 1px solid #3c3c3c;
    background-color: #010a13;
}

QTabBar::tab {
    background: #1e282d;
    border: 1px solid #3c3c3c;
    color: #a09b8c;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:hover {
    border: 1px solid #c8aa6e;
    color: #f0e6d2;
}

QTabBar::tab:selected {
    background: #010a13;
    border-color: #c8aa6e;
    border-bottom-color: #010a13;
    color: #f0e6d2;
    font-weight: bold;
}

QPushButton {
    background-color: #0f1923;
    border: 1px solid #3c3c3c;
    color: #f0e6d2;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 14px;
}

QPushButton:hover {
    background-color: #1e282d;
    border-color: #c8aa6e;
}

QPushButton:pressed {
    background-color: #0b121a;
}

QPushButton:disabled {
    background-color: #111821;
    border: 1px solid #2b2f36;
    color: #6b7280;
}

QPushButton#refreshButton {
    border-color: #c8aa6e;
    color: #c8aa6e;
}

QPushButton#refreshButton:hover {
    background-color: #1e282d;
    border-color: #f0e6d2;
    color: #f0e6d2;
}

QPushButton#runeButton[configured="true"],
QPushButton#skinButton[configured="true"] {
    background-color: #c8aa6e;
    border-color: #c8aa6e;
    color: #010a13;
}

QPushButton#runeButton[configured="true"]:hover,
QPushButton#skinButton[configured="true"]:hover {
    background-color: #f0e6d2;
    border-color: #f0e6d2;
    color: #010a13;
}

QPushButton#startButton {
    background-color: #1aa865;
    border-color: #1aa865;
    color: #010a13;
}

QPushButton#startButton:hover {
    background-color: #22c172;
    border-color: #1aa865;
    color: #010a13;
}

QPushButton#startButton:pressed {
    background-color: #12804c;
    border-color: #f0e6d2;
    color: #f0e6d2;
}

QPushButton#startButton:disabled,
QPushButton#startButton[automationState="running"]:disabled,
QPushButton#startButton[automationState="stopping"]:disabled {
    background-color: #1aa865;
    border-color: #1aa865;
    color: #010a13;
}

QPushButton#startButton[automationState="starting"]:disabled {
    background-color: #c8aa6e;
    border-color: #c8aa6e;
    color: #010a13;
}

QPushButton#stopButton {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QPushButton#stopButton:hover {
    background-color: #e25a5a;
    border-color: #d64545;
    color: #010a13;
}

QPushButton#stopButton:pressed {
    background-color: #9e3030;
    border-color: #f0e6d2;
    color: #f0e6d2;
}

QPushButton#stopButton[automationState="stopping"]:disabled {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}
"""
