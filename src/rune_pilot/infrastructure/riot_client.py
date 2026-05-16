"""
Riot Client (Riot Client.exe) entegrasyonu.
Riot Client, Electron/Chromium tabanlı olduğundan UIA element araması çalışmaz.
Bu modül: pyautogui ile mutlak ekran koordinatı tıklama + pano yapıştırma kullanır.
"""

import os
import time
import subprocess
import psutil

from typing import Optional


def _find_riot_client_path() -> Optional[str]:
    """RiotClientServices.exe kurulum yolunu bulur."""
    candidates = [
        r"C:\Riot Games\Riot Client\RiotClientServices.exe",
        r"C:\Program Files\Riot Games\Riot Client\RiotClientServices.exe",
        r"C:\Program Files (x86)\Riot Games\Riot Client\RiotClientServices.exe",
    ]
    appdata = os.path.join(
        os.getenv("LOCALAPPDATA", ""),
        r"Riot Games\Riot Client\RiotClientServices.exe"
    )
    if os.path.exists(appdata):
        candidates.insert(0, appdata)
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def is_riot_client_running() -> bool:
    """Riot Client çalışıyor mu?"""
    valid_names = {'riotclientux.exe', 'riot client.exe', 'riotclientservices.exe'}
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info.get('name', '').lower() in valid_names:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def launch_riot_client() -> bool:
    """Riot Client'i başlatır."""
    path = _find_riot_client_path()
    if not path:
        return False
    try:
        subprocess.Popen(
            [path, "--launch-product=league_of_legends", "--launch-patchline=live"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        return True
    except Exception as e:
        print(f"Riot Client başlatma hatası: {e}")
        return False


def _get_riot_window_rect():
    """
    Riot Client penceresinin mutlak ekran koordinatlarını döndürür.
    Returns: (x, y, w, h) veya None
    """
    try:
        from pywinauto import Desktop
        for w in Desktop(backend="uia").windows():
            try:
                if w.window_text() == "Riot Client":
                    r = w.rectangle()
                    return r.left, r.top, r.right - r.left, r.bottom - r.top
            except Exception:
                continue
    except Exception:
        pass
    return None


def _bring_riot_to_front():
    """Riot Client penceresini ön plana getirir."""
    try:
        from pywinauto import Desktop
        for w in Desktop(backend="uia").windows():
            try:
                if w.window_text() == "Riot Client":
                    w.set_focus()
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def auto_login_ui(username: str, password: str, timeout: int = 30) -> dict:
    """
    Riot Client giriş formuna pyautogui (mutlak koordinat) + pano yapıştırma ile giriş yapar.
    
    Adımlar:
    1. Riot Client penceresini bul (mutlak ekran koordinatları)
    2. Username alanına tıkla → panoya kopyala → Ctrl+V yapıştır
    3. Password alanına tıkla → panoya kopyala → Ctrl+V yapıştır
    4. Enter'a bas → formu gönder
    """
    try:
        import pyautogui
        import pyperclip
    except ImportError as e:
        return {"success": False, "message": f"Gerekli kütüphane eksik: {e}. 'pip install pyautogui pyperclip' çalıştırın."}

    # Riot Client açık değilse başlat
    if not is_riot_client_running():
        print("Riot Client kapalı, başlatılıyor...")
        if not launch_riot_client():
            return {"success": False, "message": "Riot Client başlatılamadı."}
        time.sleep(6)

    # Pencereyi bekle ve ön plana getir
    print("Riot Client penceresi aranıyor...")
    deadline = time.time() + timeout
    rect = None
    while time.time() < deadline:
        rect = _get_riot_window_rect()
        if rect:
            break
        time.sleep(1)

    if not rect:
        return {"success": False, "message": f"Riot Client penceresi {timeout}s içinde bulunamadı."}

    x, y, w, h = rect
    print(f"Pencere bulundu: x={x}, y={y}, w={w}, h={h}")

    # Ön plana getir
    _bring_riot_to_front()
    time.sleep(1.0)

    try:
        # Mutlak ekran koordinatları hesapla
        center_x = x + w // 2
        username_y = y + int(h * 0.35)
        password_y = y + int(h * 0.45)

        # --- USERNAME ---
        print(f"Username alanına tıklanıyor ({center_x}, {username_y})...")
        pyautogui.click(center_x, username_y)
        time.sleep(0.5)

        # Tümünü seç ve sil
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.press('backspace')
        time.sleep(0.1)

        # Kullanıcı adını panoya kopyala ve yapıştır
        print(f"Kullanıcı adı yapıştırılıyor: {username}")
        pyperclip.copy(username)
        time.sleep(0.15)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)

        # --- PASSWORD ---
        print(f"Password alanına tıklanıyor ({center_x}, {password_y})...")
        pyautogui.click(center_x, password_y)
        time.sleep(0.5)

        # Tümünü seç ve sil
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.press('backspace')
        time.sleep(0.1)

        # Şifreyi panoya kopyala ve yapıştır
        print("Şifre yapıştırılıyor...")
        pyperclip.copy(password)
        time.sleep(0.15)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)

        # Güvenlik: panoyu temizle
        pyperclip.copy("")

        # --- SUBMIT ---
        print("Enter ile gönderiliyor...")
        pyautogui.press('enter')
        time.sleep(0.5)

        print("✅ Giriş formu dolduruldu ve gönderildi.")
        return {
            "success": True,
            "message": (
                "Giriş formu dolduruldu ve gönderildi.\n\n"
                "Riot Client'ı kontrol edin:\n"
                "• Giriş başarılıysa 'Giriş Yapmadan Devam Et'e tıklayın.\n"
                "• Hata varsa bilgilerinizi kontrol edip tekrar deneyin."
            )
        }

    except Exception as e:
        return {"success": False, "message": f"Otomasyon hatası: {str(e)}"}


# ---- Geriye dönük uyumluluk wrapper'ı ----

class RiotClientAPI:
    """Önceki koda uyumluluk için tutulan sarmalayıcı sınıf."""

    def __init__(self):
        pass

    def is_running(self) -> bool:
        return is_riot_client_running()

    def wait_for_client(self, timeout: int = 20) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_running():
                return True
            time.sleep(1)
        return False

    def auto_login(self, username: str, password: str, persist_login: bool = False) -> dict:
        result = auto_login_ui(username, password)
        if result["success"]:
            return {"type": "response", "message": result["message"]}
        return {"type": "error", "message": result["message"]}