# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ["backend_main.py"], pathex=["src"],
    datas=[
        ("src/rune_pilot/composition/desktop_routes.json", "rune_pilot/composition"),
    ],
    hiddenimports=collect_submodules("uvicorn"),
    excludes=["PyQt6", "selenium", "win10toast", "tkinter", "cryptography", "pyautogui", "pywinauto", "psutil"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="runepilot-backend", console=True, debug=False, strip=False, upx=False,
)
