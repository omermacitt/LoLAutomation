"""
Visual diagnostic: moves mouse to where we WOULD click and waits so you can see it.
Watch the mouse cursor - does it land on the USERNAME field?
"""
import time
import pyautogui
from pywinauto import Desktop

def get_riot_rect():
    for w in Desktop(backend="uia").windows():
        try:
            if w.window_text() == "Riot Client":
                r = w.rectangle()
                return r.left, r.top, r.right - r.left, r.bottom - r.top
        except Exception:
            pass
    return None

rect = get_riot_rect()
if not rect:
    print("Riot Client not found!")
    exit(1)

x, y, w, h = rect
print(f"Window: left={x}, top={y}, w={w}, h={h}")
print(f"Screen resolution: {pyautogui.size()}")

# TEST DIFFERENT X POSITIONS
# The form is on the LEFT side of the screen
test_positions = [
    ("Center of window (WRONG - hero image area)", x + w // 2, y + int(h * 0.35)),
    ("9% of width (form area candidate 1)",  x + int(w * 0.09), y + int(h * 0.35)),
    ("12% of width (form area candidate 2)", x + int(w * 0.12), y + int(h * 0.35)),
    ("150px from left (fixed)",              x + 150, y + int(h * 0.35)),
    ("200px from left (fixed)",              x + 200, y + int(h * 0.35)),
]

for label, px, py in test_positions:
    print(f"\nMoving to: {label}")
    print(f"  Absolute coords: ({px}, {py})")
    pyautogui.moveTo(px, py, duration=0.5)
    time.sleep(2.0)  # pause so you can see where mouse is

print("\nDiagnostic complete. Which position was on the USERNAME field?")
