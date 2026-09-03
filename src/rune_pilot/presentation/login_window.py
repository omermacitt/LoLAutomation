"""Account management window — shown on startup; user can auto-login or skip."""

import threading
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QLineEdit, QFormLayout, 
    QMessageBox, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from rune_pilot.application.account_service import AccountService
from rune_pilot.domain.account_model import Account
from rune_pilot.shared.resource import resource_path

class AddAccountDialog(QDialog):
    """Form dialog for adding or editing an account."""
    def __init__(self, parent=None, account: Account = None):
        super().__init__(parent)
        self.setWindowTitle("Add Account" if not account else "Edit Account")
        self.setMinimumWidth(300)
        self.account = account
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.user_input = QLineEdit()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.game_name_input = QLineEdit()
        self.tag_line_input = QLineEdit()
        
        form_layout.addRow("Username:", self.user_input)
        form_layout.addRow("Password:", self.pass_input)
        form_layout.addRow("In-Game Name (Optional):", self.game_name_input)
        form_layout.addRow("Tag (Optional):", self.tag_line_input)

        layout.addLayout(form_layout)

        if account:
            self.user_input.setText(account.username)
            self.pass_input.setPlaceholderText("(Enter to change)")
            self.game_name_input.setText(account.game_name or "")
            self.tag_line_input.setText(account.tag_line or "")
            
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def validate_and_accept(self):
        user = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()
        if not user:
            QMessageBox.warning(self, "Error", "Username is required.")
            return
        if not self.account and not pwd:
            QMessageBox.warning(self, "Error", "Password is required.")
            return
            
        self.accept()

    def get_data(self):
        return (
            self.user_input.text().strip(),
            self.pass_input.text().strip(),
            self.game_name_input.text().strip() or None,
            self.tag_line_input.text().strip() or None
        )

class LoginWindow(QMainWindow):
    """RunePilot launcher and account management window."""

    login_successful = pyqtSignal()
    skip_login = pyqtSignal()
    _login_finished = pyqtSignal(dict)  # Carries the background thread result to the UI thread

    def __init__(self, account_service: AccountService):
        super().__init__()
        self.account_service = account_service
        self.setWindowTitle("RunePilot - Account Selection")
        self.setWindowIcon(QIcon(resource_path("assets/app_icon.png")))
        self.resize(500, 350)
        self._login_finished.connect(self._on_done)
        self._init_ui()
        self._load_list()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        info_lbl = QLabel("Welcome!\nSelect or add an account to auto-login via Riot Client.\nPasswords are stored encrypted on this machine only.")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        manage_btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Account")
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._on_del_clicked)

        manage_btn_layout.addWidget(self.add_btn)
        manage_btn_layout.addWidget(self.edit_btn)
        manage_btn_layout.addWidget(self.del_btn)
        manage_btn_layout.addStretch()
        layout.addLayout(manage_btn_layout)

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #444;")
        layout.addWidget(line)

        action_btn_layout = QHBoxLayout()

        self.skip_btn = QPushButton("Continue Without Login")
        self.skip_btn.setToolTip("Click if Riot Client is already open or you want to log in manually.")
        self.skip_btn.clicked.connect(self.skip_login.emit)

        self.login_btn = QPushButton("Login & Launch League of Legends")
        self.login_btn.setObjectName("startButton")  # QSS ID for green styling
        self.login_btn.clicked.connect(self._on_login_clicked)
        self.login_btn.setMinimumHeight(35)
        
        action_btn_layout.addWidget(self.skip_btn)
        action_btn_layout.addWidget(self.login_btn)
        layout.addLayout(action_btn_layout)

    def _load_list(self):
        self.list_widget.clear()
        for acc in self.account_service.get_accounts():
            item = QListWidgetItem(acc.display_name)
            item.setData(Qt.ItemDataRole.UserRole, acc.id)
            self.list_widget.addItem(item)
            
        if self.account_service.get_accounts():
            self.list_widget.setCurrentRow(0)

    def _get_selected_account_id(self) -> str | None:
        sel = self.list_widget.selectedItems()
        if not sel:
            return None
        return sel[0].data(Qt.ItemDataRole.UserRole)

    def _on_add_clicked(self):
        dlg = AddAccountDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            u, p, g, t = dlg.get_data()
            self.account_service.add_account(u, p, g, t)
            self._load_list()

    def _on_edit_clicked(self):
        acc_id = self._get_selected_account_id()
        if not acc_id:
            QMessageBox.warning(self, "Error", "Please select an account to edit.")
            return
            
        acc = next((a for a in self.account_service.get_accounts() if a.id == acc_id), None)
        if not acc: return
        
        dlg = AddAccountDialog(self, account=acc)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            u, p, g, t = dlg.get_data()
            self.account_service.update_account(acc_id, u, p or None, g, t)
            self._load_list()

    def _on_del_clicked(self):
        acc_id = self._get_selected_account_id()
        if not acc_id:
            QMessageBox.warning(self, "Error", "Please select an account to delete.")
            return

        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to delete this account?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.account_service.delete_account(acc_id)
            self._load_list()

    def _on_login_clicked(self):
        acc_id = self._get_selected_account_id()
        if not acc_id:
            QMessageBox.warning(self, "Error", "Please select an account to log in.")
            return

        self.login_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.login_btn.setText("Logging in… this may take up to 40 s")

        def _bg_worker():
            try:
                result = self.account_service.auto_login(acc_id)
            except Exception as e:
                result = {"type": "error", "message": f"Unexpected error: {str(e)}"}
            self._login_finished.emit(result)

        thread = threading.Thread(target=_bg_worker, daemon=True)
        thread.start()

    def _on_done(self, result: dict):
        self.login_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.login_btn.setText("Login & Launch League of Legends")

        res_type = result.get("type")
        res_error = result.get("error")

        if res_type == "error":
            QMessageBox.critical(self, "Error", f"Login Failed:\n{result.get('message', 'Unknown Error')}")
        elif res_error == "auth_failure" or res_type == "auth_failure":
            QMessageBox.warning(self, "Error", "Incorrect username or password.\nPlease edit the account and try again.")
        elif res_type == "multifactor" or res_error == "multifactor":
            QMessageBox.warning(self, "Two-Factor Authentication", "Two-factor authentication (2FA) is required. Please enter the verification code in Riot Client manually.\nAfter completing verification, click 'Continue Without Login'.")
        elif res_type == "captcha":
            QMessageBox.warning(self, "Captcha Required", result.get("message", "Riot Client requires captcha verification.\nPlease complete the login in the Riot Client window manually.\nAfter logging in, click 'Continue Without Login'."))
        elif res_type == "captcha_ui":
            QMessageBox.information(self, "Action Required", result.get("message",
                "Your credentials have been entered in Riot Client.\n"
                "If a captcha appeared, please solve it, then click 'Continue Without Login'."))
        elif res_type == "response":
            self.login_successful.emit()
        else:
            QMessageBox.warning(self, "Unknown Status", f"Login request completed but the response could not be classified.\n{result}")

