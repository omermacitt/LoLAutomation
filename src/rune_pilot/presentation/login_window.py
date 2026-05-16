"""
Hesaplar (Accounts) yönetim penceresi.
Uygulama başlatıldığında ilk olarak bu pencere açılır; kullanıcı giriş yapabilir 
veya giriş yapmadan devam edebilir.
"""

import threading
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QLineEdit, QFormLayout, 
    QMessageBox, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from src.rune_pilot.application.account_service import AccountService
from src.rune_pilot.domain.account_model import Account
from src.rune_pilot.shared.resource import resource_path

class AddAccountDialog(QDialog):
    """Yeni hesap eklemek veya düzenlemek için form penceresi."""
    def __init__(self, parent=None, account: Account = None):
        super().__init__(parent)
        self.setWindowTitle("Hesap Ekle" if not account else "Hesap Düzenle")
        self.setMinimumWidth(300)
        self.account = account
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.user_input = QLineEdit()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.game_name_input = QLineEdit()
        self.tag_line_input = QLineEdit()
        
        form_layout.addRow("Kullanıcı Adı:", self.user_input)
        form_layout.addRow("Şifre:", self.pass_input)
        form_layout.addRow("Oyun İçi Ad (Opsiyonel):", self.game_name_input)
        form_layout.addRow("Etiket (Opsiyonel):", self.tag_line_input)
        
        layout.addLayout(form_layout)
        
        if account:
            self.user_input.setText(account.username)
            self.pass_input.setPlaceholderText("(Değiştirmek için girin)")
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
            QMessageBox.warning(self, "Hata", "Kullanıcı adı zorunludur.")
            return
        if not self.account and not pwd:
            QMessageBox.warning(self, "Hata", "Şifre zorunludur.")
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
    """RunePilot Başlatıcı (Launcher) ve Hesap Yönetim Penceresi."""
    
    login_successful = pyqtSignal() 
    skip_login = pyqtSignal()
    _login_finished = pyqtSignal(dict) # Arka plan işleminden dönen sonucu UI'a taşımak için
    
    def __init__(self, account_service: AccountService):
        super().__init__()
        self.account_service = account_service
        self.setWindowTitle("RunePilot - Hesap Seçimi")
        self.setWindowIcon(QIcon(resource_path("assets/app_icon.png")))
        self.resize(500, 350)
        self._login_finished.connect(self._on_done)
        self._init_ui()
        self._load_list()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Bilgi
        info_lbl = QLabel("Hoş Geldiniz!\nRiot Client üzerinden otomatik giriş yapmak için bir hesap seçin veya ekleyin.\nŞifreleriniz diskinizde yalnızca bu bilgisayara özel şifrelenmektedir.")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)
        
        # Liste
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        # Hesap Yönetim Butonları
        manage_btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Hesap Ekle")
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.edit_btn = QPushButton("Düzenle")
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        self.del_btn = QPushButton("Sil")
        self.del_btn.clicked.connect(self._on_del_clicked)
        
        manage_btn_layout.addWidget(self.add_btn)
        manage_btn_layout.addWidget(self.edit_btn)
        manage_btn_layout.addWidget(self.del_btn)
        manage_btn_layout.addStretch()
        layout.addLayout(manage_btn_layout)
        
        # Ayrım Çizgisi
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #444;")
        layout.addWidget(line)

        # Başlatma Butonları
        action_btn_layout = QHBoxLayout()
        
        self.skip_btn = QPushButton("Giriş Yapmadan Devam Et")
        self.skip_btn.setToolTip("Riot Client zaten açıksa veya el ile giriş yapacaksanız tıklayın.")
        self.skip_btn.clicked.connect(self.skip_login.emit)
        
        self.login_btn = QPushButton("Seçili Hesapla Giriş Yap (Auto-Login)")
        self.login_btn.setObjectName("startButton") # Yeşile boyanması için QSS ID'si
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
            QMessageBox.warning(self, "Hata", "Lütfen düzenlemek için bir hesap seçin.")
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
            QMessageBox.warning(self, "Hata", "Lütfen silmek için bir hesap seçin.")
            return
            
        reply = QMessageBox.question(self, "Onay", "Bu hesabı silmek istediğinize emin misiniz?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.account_service.delete_account(acc_id)
            self._load_list()

    def _on_login_clicked(self):
        acc_id = self._get_selected_account_id()
        if not acc_id:
            QMessageBox.warning(self, "Hata", "Giriş yapmak için lütfen bir hesap seçin.")
            return
            
        self.login_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.login_btn.setText("Giriş yapılıyor, lütfen bekleyin...")
        
        def _bg_worker():
            try:
                result = self.account_service.auto_login(acc_id)
            except Exception as e:
                result = {"type": "error", "message": f"Beklenmedik hata: {str(e)}"}
            self._login_finished.emit(result)
            
        # Arka plan denemesi başlat
        thread = threading.Thread(target=_bg_worker, daemon=True)
        thread.start()

    def _on_done(self, result: dict):
        self.login_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.login_btn.setText("Seçili Hesapla Giriş Yap (Auto-Login)")
        
        # Riot API/UI Automation yanıt tiplerini çözümle
        res_type = result.get("type")
        res_error = result.get("error")
        
        if res_type == "error":
            QMessageBox.critical(self, "Hata", f"Giriş Başarısız:\n{result.get('message', 'Bilinmeyen Hata')}")
        elif res_error == "auth_failure" or res_type == "auth_failure":
            QMessageBox.warning(self, "Hata", "Kullanıcı adı veya şifre yanlış.\nLütfen hesap bilgilerinizi düzenleyip tekrar deneyin.")
        elif res_type == "multifactor" or res_error == "multifactor":
            QMessageBox.warning(self, "İki Adımlı Doğrulama", "İki adımlı doğrulama (2FA) talep ediliyor. Lütfen Riot Client üzerinden doğrulama kodunu kendiniz girin.\nDoğrulama tamamlandıktan sonra 'Giriş Yapmadan Devam Et' butonuna tıklayın.")
        elif res_type == "response":
            # UI Automation: form dolduruldu ve gönderildi.
            # Kullanıcı Riot Client'ı kontrol etmeli.
            reply = QMessageBox.question(
                self,
                "Giriş Formu Gönderildi",
                f"{result.get('message', 'Giriş formu gönderildi.')}\n\n"
                "Riot Client'ta giriş başarıyla tamamlandı mı?\n\n"
                "• Evet → Ana ekrana geç\n"
                "• Hayır → Geri dön ve tekrar dene",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.login_successful.emit()
        else:
            QMessageBox.warning(self, "Bilinmeyen Durum", f"Giriş isteği tamamlandı ancak yanıt sınıflandırılamadı.\n{result}")

