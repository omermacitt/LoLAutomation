"""
Riot Client (RiotClientServices.exe) integration.

Primary login strategy: Riot Client local HTTP API (lockfile auth, same pattern as LCU).
Fallback: pyautogui UI automation (UIA → Tab → coordinates).
"""

import base64
import os
import time
import subprocess
import psutil

from typing import Optional


def _find_riot_client_path() -> Optional[str]:
    """Locates the RiotClientServices.exe installation path."""
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


def _find_riot_client_ux_path() -> Optional[str]:
    """Locates Riot Client.exe (the Electron UI process)."""
    candidates = [
        r"C:\Riot Games\Riot Client\RiotClientElectron\Riot Client.exe",
        r"C:\Program Files\Riot Games\Riot Client\RiotClientElectron\Riot Client.exe",
        r"C:\Program Files (x86)\Riot Games\Riot Client\RiotClientElectron\Riot Client.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _is_riot_client_ux_running() -> bool:
    """Returns True if the Riot Client Electron UI (Riot Client.exe) is running."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info.get('name', '').lower() == 'riot client.exe':
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _launch_riot_client_ux() -> bool:
    """Launches the Riot Client Electron UI (shows the login/lobby screen)."""
    path = _find_riot_client_ux_path()
    if not path:
        return False
    try:
        subprocess.Popen(
            [path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        return True
    except Exception as e:
        print(f"Riot Client UX launch error: {e}")
        return False


def is_riot_client_running() -> bool:
    """Returns True if Riot Client is currently running."""
    valid_names = {'riotclientux.exe', 'riot client.exe', 'riotclientservices.exe'}
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info.get('name', '').lower() in valid_names:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def launch_riot_client() -> bool:
    """Launches the Riot Client."""
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
        print(f"Riot Client launch error: {e}")
        return False


def _get_riot_window_rect():
    """
    Returns the absolute screen coordinates of the Riot Client window.
    Returns: (x, y, w, h) or None
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
    """Brings the Riot Client window to the foreground."""
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


def _find_riot_client_lockfile() -> Optional[str]:
    """Returns the Riot Client lockfile path if it exists, else None."""
    path = os.path.join(
        os.getenv("LOCALAPPDATA", ""),
        "Riot Games", "Riot Client", "Config", "lockfile",
    )
    return path if os.path.exists(path) else None


def _parse_riot_client_lockfile() -> Optional[tuple]:
    """Parses the Riot Client lockfile and returns (port, password) or None."""
    path = _find_riot_client_lockfile()
    if not path:
        return None
    try:
        with open(path, "r") as f:
            parts = f.read().strip().split(":")
        # format: name:pid:port:password:protocol
        if len(parts) < 5:
            return None
        return int(parts[2]), parts[3]
    except Exception:
        return None


_PRODUCT_NAMES = {
    "valorant": "VALORANT",
    "league_of_legends": "League of Legends",
    "bacon": "Teamfight Tactics",
}


def _get_active_product(port: int, headers: dict) -> Optional[str]:
    """
    Returns the display name of any non-idle game product, or None if idle.
    Checks ALL sessions — do NOT filter by isInternal, as LoL may be marked internal.
    """
    try:
        import requests as _req
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        s = _req.Session()
        s.verify = False
        s.headers.update(headers)
        r = s.get(f"https://127.0.0.1:{port}/product-session/v1/sessions", timeout=5)
        if r.status_code != 200:
            print(f"[API] product-session check: {r.status_code}")
            return None
        idle = {"None", "", None}
        sessions = r.json()
        print(f"[API] product-session: {sessions}")
        for _key, data in sessions.items():
            phase = data.get("phase", "None")
            product_id = data.get("productId", "")
            if product_id in ("riot_client", ""):
                continue
            if phase not in idle:
                return _PRODUCT_NAMES.get(product_id, product_id)
    except Exception as e:
        print(f"[API] product-session check failed: {e}")
    return None


def auto_login_api(username: str, password: str, timeout: int = 30) -> dict:
    """
    Authenticates via the Riot Client local HTTP API (rso-authenticator, new flow).

    Riot Client (post mid-2026) uses /rso-authenticator/v1/authentication instead
    of the old /rso-auth/v1/session flow.  The new endpoint is always reachable
    (no RSO-initialization wait needed) and supports direct credential submission.

    Flow:
      1. GET /rso-authenticator/v1/authentication → type=="auth" means ready.
         If the user is already logged in, DELETE /rso-auth/v1/authorization first.
      2. PUT /rso-authenticator/v1/authentication with {username, password, remember}
      3. Classify response by type field.

    Returns a dict with key 'type':
      'response'     — credentials accepted, client is logging in
      'auth_failure' — wrong username or password
      'multifactor'  — 2FA required; user must complete it in Riot Client
      'captcha'      — hcaptcha required (Riot Client must be interacted with manually)
      'error'        — something else went wrong ('message' has details)
    """
    try:
        import requests as _req
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except ImportError as e:
        return {"type": "error", "message": f"'requests' library missing: {e}"}

    if not is_riot_client_running():
        print("[API] Riot Client not running — launching...")
        if not launch_riot_client():
            return {"type": "error", "message": "Failed to launch Riot Client."}
        time.sleep(8)

    print("[API] Waiting for Riot Client lockfile...")
    deadline = time.time() + timeout
    creds = None
    while time.time() < deadline:
        creds = _parse_riot_client_lockfile()
        if creds:
            break
        time.sleep(1)

    if not creds:
        return {
            "type": "error",
            "message": (
                "Riot Client lockfile not found. "
                "The client may still be loading — try again in a few seconds."
            ),
        }

    # NOTE: Never launch Riot Client.exe directly — when started without the
    # args that RiotClientServices passes (--app-port, --remoting-auth-token,
    # --app-pid), the UX falls back to developer mode and spawns its own
    # Services instance with mismatched tokens.  RSO then never initializes.
    # RiotClientServices.exe manages the UX lifecycle; we only ever launch Services.
    port, lockfile_pw = creds
    auth_b64 = base64.b64encode(f"riot:{lockfile_pw}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json",
    }

    # Pre-check — refuse if a game is actively running.
    active = _get_active_product(port, headers)
    if active:
        return {
            "type": "error",
            "message": (
                f"{active} is currently running. "
                "Close the game before switching accounts."
            ),
        }

    url_auth      = f"https://127.0.0.1:{port}/rso-auth/v1/authorization"
    url_authn     = f"https://127.0.0.1:{port}/rso-authenticator/v1/authentication"

    try:
        session = _req.Session()
        session.verify = False
        session.headers.update(headers)

        # Step 1 — get current authenticator state.
        print("[API] GET /rso-authenticator/v1/authentication ...")
        try:
            r1 = session.get(url_authn, timeout=10)
        except Exception as e:
            return {"type": "error", "message": f"Cannot reach Riot Client API: {e}"}

        print(f"[API] Authenticator state: {r1.status_code} type={r1.json().get('type')!r}")
        d1 = r1.json()
        state = d1.get("type", "")

        # If already logged in (success/response state), sign out first.
        if state not in ("auth", "multifactor", ""):
            print(f"[API] Currently logged in (type={state!r}) — signing out...")
            try:
                session.delete(url_auth, timeout=5)
                time.sleep(3)
                r1 = session.get(url_authn, timeout=10)
                d1 = r1.json()
                state = d1.get("type", "")
                print(f"[API] After sign-out: type={state!r}")
            except Exception as e:
                print(f"[API] Sign-out failed: {e}")

        if state == "multifactor":
            return {
                "type": "multifactor",
                "message": "Two-factor authentication is already pending in Riot Client.",
            }

        if state == "error":
            # "invalid_prompt" or similar — the authenticator session may be stale.
            # Retry once with a fresh GET to get a new session.
            print(f"[API] Authenticator error={d1.get('error')!r} — retrying GET...")
            time.sleep(2)
            r1 = session.get(url_authn, timeout=10)
            d1 = r1.json()
            state = d1.get("type", "")
            print(f"[API] Retry state: {state!r} error={d1.get('error')!r}")

        if state == "multifactor":
            return {
                "type": "multifactor",
                "message": "Two-factor authentication is already pending in Riot Client.",
            }

        if state != "auth":
            return {
                "type": "error",
                "message": (
                    f"Riot Client authenticator returned: {state!r} "
                    f"(error={d1.get('error')!r}).\n"
                    "Make sure Riot Client is open and at the login screen."
                ),
            }

        # Step 2 — submit credentials.
        suuid = d1.get("suuid") or ""
        captcha_info = d1.get("captcha") or {}
        captcha_type = captcha_info.get("type", "none")

        # If Riot Client requires captcha, we cannot solve it programmatically.
        # Signal the caller so it can fall back to UI automation (pre-fill form).
        if captcha_type not in (None, "none", ""):
            return {
                "type": "captcha",
                "message": (
                    "Riot Client requires captcha verification.\n"
                    "Credentials will be entered automatically — "
                    "please solve the captcha in the Riot Client window,\n"
                    "then click 'Continue Without Login'."
                ),
            }

        body: dict = {"username": username, "password": password, "remember": False}
        if suuid:
            body["suuid"] = suuid

        print(f"[API] PUT /rso-authenticator/v1/authentication (suuid={bool(suuid)}, captcha={bool(captcha_data)}) ...")
        r2 = session.put(url_authn, json=body, timeout=15)
        d2 = r2.json()
        t2 = d2.get("type", "")
        print(f"[API] Credentials response: status={r2.status_code} type={t2!r} error={d2.get('error')!r}")

        if t2 == "response" or d2.get("success", {}).get("login_token"):
            # Credentials accepted — wait for Riot Client to finish the login
            # process (token exchange, account data load) before signalling
            # the caller to launch League of Legends.  Without this wait,
            # launch_riot_client() arrives while the client is still mid-login
            # and the product launch command is ignored.
            print("[API] Credentials accepted — waiting for Riot Client login to finalise...")
            login_deadline = time.time() + 40
            while time.time() < login_deadline:
                try:
                    r_check = session.get(url_auth, timeout=5)
                    if r_check.status_code == 200:
                        print("[API] Login complete — ready to launch League.")
                        break
                except Exception:
                    pass
                time.sleep(2)
            return {
                "type": "response",
                "message": "Login complete — launching League of Legends.",
            }
        if t2 == "multifactor":
            return {"type": "multifactor"}
        if t2 == "auth":
            err = d2.get("error", "")
            if err in ("auth_failure", "wrong_credentials"):
                return {"type": "auth_failure"}
            remaining_captcha = (d2.get("captcha") or {}).get("type", "none")
            if remaining_captcha not in (None, "none", ""):
                return {
                    "type": "captcha",
                    "message": (
                        "Riot Client requires captcha verification.\n"
                        "Please complete the login in the Riot Client window manually,\n"
                        "then click 'Continue Without Login'."
                    ),
                }
            if err:
                return {"type": "error", "message": f"Login failed: {err}"}
            return {"type": "error", "message": f"Unexpected auth response: {d2}"}
        if t2 == "error":
            err = d2.get("error", "unknown")
            return {"type": "error", "message": f"Authenticator error: {err}"}

        return {"type": "error", "message": f"Unexpected credentials response: {d2}"}

    except Exception as e:
        return {"type": "error", "message": f"Riot Client API request failed: {e}"}


def _paste_into_field(text: str) -> None:
    """Selects all existing text in the focused field and pastes new text via clipboard."""
    import pyautogui
    import pyperclip
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(text)
    time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.3)


def _try_uia_login(username: str, password: str) -> bool:
    """
    Strategy 1: find the two Edit controls in the Riot Client window via UIA accessibility
    and type directly into them. Returns True if it managed to fill both fields.
    """
    try:
        from pywinauto import Desktop
        app = Desktop(backend="uia")

        riot_win = None
        for w in app.windows():
            try:
                title = w.window_text()
                if "riot client" in title.lower():
                    riot_win = w
                    break
            except Exception:
                continue

        if riot_win is None:
            return False

        edits = riot_win.descendants(control_type="Edit")
        if len(edits) < 2:
            print(f"[UIA] Found {len(edits)} Edit control(s) — need at least 2, skipping UIA strategy.")
            return False

        import pyperclip
        print("[UIA] Found Edit controls, filling via UIA...")

        edits[0].set_focus()
        time.sleep(0.3)
        edits[0].type_keys("^a", pause=0.05)
        pyperclip.copy(username)
        edits[0].type_keys("^v", pause=0.05)
        time.sleep(0.3)

        edits[1].set_focus()
        time.sleep(0.3)
        edits[1].type_keys("^a", pause=0.05)
        pyperclip.copy(password)
        edits[1].type_keys("^v", pause=0.05)
        time.sleep(0.3)

        pyperclip.copy("")
        edits[1].type_keys("{ENTER}", pause=0.05)
        return True

    except Exception as e:
        print(f"[UIA] Strategy failed: {e}")
        return False


def _try_tab_login(username: str, password: str, rect: tuple) -> bool:
    """
    Strategy 2: click the window centre to focus it, then use Tab to reach the
    username field, paste, Tab to password field, paste, then press Enter.
    """
    try:
        import pyautogui
        import pyperclip

        x, y, w, h = rect
        center_x = x + w // 2
        center_y = y + h // 2

        print("[TAB] Clicking window centre to focus...")
        pyautogui.click(center_x, center_y)
        time.sleep(0.5)

        # Dismiss any popup / overlay that might be in focus
        pyautogui.press('escape')
        time.sleep(0.3)

        # Tab to the username field — it is the first focusable input on the login form
        print("[TAB] Tabbing to username field...")
        pyautogui.hotkey('shift', 'tab')   # cycle backwards to wrap to last → first
        time.sleep(0.2)
        pyautogui.press('tab')
        time.sleep(0.3)

        print("[TAB] Pasting username...")
        _paste_into_field(username)

        # Tab forward to the password field
        pyautogui.press('tab')
        time.sleep(0.3)

        print("[TAB] Pasting password...")
        _paste_into_field(password)

        pyperclip.copy("")
        pyautogui.press('enter')
        time.sleep(0.5)
        return True

    except Exception as e:
        print(f"[TAB] Strategy failed: {e}")
        return False


def _try_coordinate_login(username: str, password: str, rect: tuple) -> bool:
    """
    Strategy 3 (fallback): click at percentage-based coordinates for the
    username and password fields and paste via clipboard.
    These offsets target the Riot Client login form layout as of 2024-2025.
    """
    try:
        import pyautogui
        import pyperclip

        x, y, w, h = rect
        center_x = x + w // 2
        # Fields are roughly in the upper-middle vertical band of the login form
        username_y = y + int(h * 0.42)
        password_y = y + int(h * 0.52)

        print(f"[COORD] Clicking username at ({center_x}, {username_y})...")
        pyautogui.click(center_x, username_y)
        time.sleep(0.5)
        _paste_into_field(username)

        print(f"[COORD] Clicking password at ({center_x}, {password_y})...")
        pyautogui.click(center_x, password_y)
        time.sleep(0.5)
        _paste_into_field(password)

        pyperclip.copy("")
        pyautogui.press('enter')
        time.sleep(0.5)
        return True

    except Exception as e:
        print(f"[COORD] Strategy failed: {e}")
        return False


def auto_login_ui(username: str, password: str, timeout: int = 30) -> dict:
    """
    Fills the Riot Client login form using three strategies in order:
    1. UIA accessibility — finds Edit controls directly (most reliable).
    2. Tab navigation — focuses the window and tabs to each field.
    3. Coordinate fallback — clicks at estimated field positions.
    """
    try:
        import pyautogui  # noqa: F401
        import pyperclip  # noqa: F401
    except ImportError as e:
        return {"success": False, "message": f"Required library missing: {e}. Run 'pip install pyautogui pyperclip'."}

    if not is_riot_client_running():
        print("Riot Client is not running, launching...")
        if not launch_riot_client():
            return {"success": False, "message": "Failed to launch Riot Client."}
        time.sleep(6)

    print("Looking for Riot Client window...")
    deadline = time.time() + timeout
    rect = None
    while time.time() < deadline:
        rect = _get_riot_window_rect()
        if rect:
            break
        time.sleep(1)

    if not rect:
        return {"success": False, "message": f"Riot Client window not found within {timeout}s."}

    x, y, w, h = rect
    print(f"Window found: x={x}, y={y}, w={w}, h={h}")

    _bring_riot_to_front()
    time.sleep(0.8)

    ok = _try_uia_login(username, password)
    if not ok:
        print("UIA strategy failed, trying Tab navigation...")
        ok = _try_tab_login(username, password, rect)
    if not ok:
        print("Tab strategy failed, trying coordinate fallback...")
        ok = _try_coordinate_login(username, password, rect)

    if not ok:
        return {"success": False, "message": "All login strategies failed. Check that the Riot Client login screen is visible."}

    return {
        "success": True,
        "message": (
            "Login form filled and submitted.\n\n"
            "Check Riot Client:\n"
            "• If login succeeded, click 'Continue without logging in'.\n"
            "• If there was an error, check your credentials and try again."
        )
    }


# ---- Backward-compatibility wrapper ----

class RiotClientAPI:
    """Wrapper class retained for backward compatibility."""

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