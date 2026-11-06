"""Auto-Click & Execution Agent for Web Platforms (Windows native ctypes).

Executes mouse clicks on calibrated broker buttons (CALL / BUY or PUT / SELL).
"""
import ctypes
import json
import os
import time

CALIBRATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration.json")

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def load_calibration() -> dict:
    if os.path.exists(CALIBRATION_FILE):
        try:
            with open(CALIBRATION_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"call_button": None, "put_button": None, "auto_click_enabled": False}


def save_calibration(data: dict):
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(data, f, indent=2)


def click_at(x: int, y: int, dry_run: bool = False) -> bool:
    """Move mouse and click at (x, y) on the screen."""
    if dry_run or os.name != "nt":
        return True
    user32 = ctypes.windll.user32
    # Save current cursor pos
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))

    # Move and click
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.05)

    # Return cursor back to user
    user32.SetCursorPos(pt.x, pt.y)
    return True


def execute_action(action: str, dry_run: bool = False) -> dict:
    """Trigger click on calibrated button based on action ('CALL' or 'PUT')."""
    calib = load_calibration()
    key = "call_button" if "CALL" in action.upper() or "BUY" in action.upper() else "put_button"
    coords = calib.get(key)
    if not coords or "x" not in coords or "y" not in coords:
        return {
            "ok": False,
            "error": f"No calibrated coordinates for {action}. Please click 'Calibrate {action}' first.",
        }

    x, y = coords["x"], coords["y"]
    success = click_at(x, y, dry_run=dry_run)
    return {
        "ok": success,
        "action": action,
        "coords": {"x": x, "y": y},
        "mode": "DRY_RUN" if dry_run else "CLICKED",
        "time": time.time(),
    }

