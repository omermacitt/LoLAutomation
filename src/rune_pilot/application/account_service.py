"""
Hesap yönetimi uygulama servisi.
"""

import json
import os
import uuid
from typing import List, Optional

from src.rune_pilot.domain.account_model import Account
from src.rune_pilot.infrastructure.crypto import encrypt_password, decrypt_password
from src.rune_pilot.infrastructure.riot_client import RiotClientAPI, launch_riot_client

class AccountService:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.accounts: List[Account] = []
        self._load_accounts()

    def _load_accounts(self) -> None:
        """Config dosyasından hesapları okur."""
        if not os.path.exists(self.config_file):
            return
            
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                accounts_data = data.get("accounts", [])
                self.accounts = [Account(**acc) for acc in accounts_data]
        except Exception as e:
            print(f"Hesaplar yuklenirken hata: {e}")

    def _save_accounts(self) -> None:
        """Hesapları config dosyasına geri yazar."""
        data = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
                
        data["accounts"] = [acc.model_dump() for acc in self.accounts]
        
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Hesaplar kaydedilirken hata: {e}")

    def get_accounts(self) -> List[Account]:
        return self.accounts

    def add_account(self, username: str, password: str, game_name: str = None, tag_line: str = None) -> Account:
        """Yeni bir hesap ekler."""
        encrypted_pw = encrypt_password(password)
        acc = Account(
            id=str(uuid.uuid4()),
            username=username,
            encrypted_password=encrypted_pw,
            game_name=game_name,
            tag_line=tag_line
        )
        self.accounts.append(acc)
        self._save_accounts()
        return acc
        
    def update_account(self, acc_id: str, username: str, password: str = None, game_name: str = None, tag_line: str = None) -> bool:
        """Mevcut bir hesabı günceller."""
        for acc in self.accounts:
            if acc.id == acc_id:
                acc.username = username
                if password:  # Sadece yeni parola verildiyse güncelleyelim.
                    acc.encrypted_password = encrypt_password(password)
                acc.game_name = game_name
                acc.tag_line = tag_line
                self._save_accounts()
                return True
        return False

    def delete_account(self, acc_id: str) -> bool:
        """Hesabı siler."""
        initial_len = len(self.accounts)
        self.accounts = [acc for acc in self.accounts if acc.id != acc_id]
        if len(self.accounts) < initial_len:
            self._save_accounts()
            return True
        return False

    def auto_login(self, acc_id: str) -> dict:
        """
        Giriş işlemlerini (Auto-Login) başlatır.
        Önce istemci açık mı bakar, değilse başlatır. Sonra HTTP PUT isteği gönderir.
        """
        acc = next((a for a in self.accounts if a.id == acc_id), None)
        if not acc:
            return {"type": "error", "message": "Hesap bulunamadı."}
            
        password = decrypt_password(acc.encrypted_password)
        if not password:
            return {"type": "error", "message": "Parola çözülemedi. Lütfen hesabı güncelleyin."}

        client = RiotClientAPI()
        
        # Eğer açık değilse başlat:
        if not client.is_running():
            print("Riot Client kapalı, başlatılıyor...")
            if not launch_riot_client():
                return {"type": "error", "message": "Riot Client başlatılamadı."}
                
        # UX sürecinin başlamasını bekle
        if not client.wait_for_client(timeout=15):
            return {"type": "error", "message": "Riot Client API'ye bağlanılamadı (Timeout)."}
            
        print("Riot Client'a giriş yapılıyor...")
        # Artık API üzerinden credentials gönderilebilir
        response = client.auto_login(acc.username, password, persist_login=True)
        return response
