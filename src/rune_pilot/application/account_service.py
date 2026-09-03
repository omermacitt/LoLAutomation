"""Account management application service."""

import json
import os
import uuid
from typing import List, Optional

from rune_pilot.domain.account_model import Account
from rune_pilot.infrastructure.crypto import encrypt_password, decrypt_password
from rune_pilot.infrastructure.riot_client import auto_login_api, auto_login_ui, launch_riot_client

class AccountService:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.accounts: List[Account] = []
        self._load_accounts()

    def _load_accounts(self) -> None:
        """Loads accounts from the config file."""
        if not os.path.exists(self.config_file):
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                accounts_data = data.get("accounts", [])
                self.accounts = [Account(**acc) for acc in accounts_data]
        except Exception as e:
            print(f"Error loading accounts: {e}")

    def _save_accounts(self) -> None:
        """Writes accounts back to the config file."""
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
            print(f"Error saving accounts: {e}")

    def get_accounts(self) -> List[Account]:
        return self.accounts

    def add_account(self, username: str, password: str, game_name: str = None, tag_line: str = None) -> Account:
        """Adds a new account."""
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
        """Updates an existing account."""
        for acc in self.accounts:
            if acc.id == acc_id:
                acc.username = username
                if password:  # Only update the password if a new one is provided.
                    acc.encrypted_password = encrypt_password(password)
                acc.game_name = game_name
                acc.tag_line = tag_line
                self._save_accounts()
                return True
        return False

    def delete_account(self, acc_id: str) -> bool:
        """Deletes an account."""
        initial_len = len(self.accounts)
        self.accounts = [acc for acc in self.accounts if acc.id != acc_id]
        if len(self.accounts) < initial_len:
            self._save_accounts()
            return True
        return False

    def auto_login(self, acc_id: str) -> dict:
        """Initiates the auto-login flow for the given account via the Riot Client HTTP API."""
        acc = next((a for a in self.accounts if a.id == acc_id), None)
        if not acc:
            return {"type": "error", "message": "Account not found."}

        password = decrypt_password(acc.encrypted_password)
        if not password:
            return {"type": "error", "message": "Could not decrypt password. Please update the account."}

        result = auto_login_api(acc.username, password)
        if result.get("type") == "response":
            launch_riot_client()
            return result

        if result.get("type") == "captcha":
            # API blocked by captcha — pre-fill the Riot Client login form via UI automation.
            # User still needs to solve the captcha manually in the Riot Client window.
            ui_result = auto_login_ui(acc.username, password)
            if ui_result.get("success"):
                return {
                    "type": "captcha_ui",
                    "message": (
                        "Your credentials have been entered in Riot Client.\n"
                        "If a captcha appeared, please solve it, then click 'Continue Without Login'.\n"
                        "If you are already logged in, just click 'Continue Without Login'."
                    ),
                }

        return result
