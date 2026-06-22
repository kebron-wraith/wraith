"""
PC Control Module - Faka's direct control over Kebron's Windows PC
Uses ctypes + win32api for mouse, keyboard, and screen control.
"""

import ctypes
import win32api
import win32con
import win32gui
import time
import sys

# ─── MOUSE CONTROL ───────────────────────────────────────────────

def get_mouse_pos():
    """Get current mouse cursor position."""
    x, y = win32api.GetCursorPos()
    return (x, y)

def move_mouse(x, y):
    """Move mouse to absolute screen coordinates."""
    win32api.SetCursorPos((x, y))

def click(x=None, y=None, button="left", double=False):
    """
    Click at position (x, y). If None, clicks at current position.
    button: 'left', 'right', 'middle'
    double: True for double-click
    """
    if x is not None and y is not None:
        move_mouse(x, y)
        time.sleep(0.05)

    btn_map = {
        "left":   (win32con.MOUSEEVENTF_LEFTDOWN,   win32con.MOUSEEVENTF_LEFTUP),
        "right":  (win32con.MOUSEEVENTF_RIGHTDOWN,  win32con.MOUSEEVENTF_RIGHTUP),
        "middle": (win32con.MOUSEEVENTF_MIDDLEDOWN, win32con.MOUSEEVENTF_MIDDLEUP),
    }

    down, up = btn_map[button]
    win32api.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(up, 0, 0, 0, 0)

    if double:
        time.sleep(0.05)
        win32api.mouse_event(down, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(up, 0, 0, 0, 0)

def right_click(x=None, y=None):
    """Right-click at position."""
    click(x, y, button="right")

def mouse_down(button="left"):
    """Hold mouse button down."""
    btn_map = {
        "left": win32con.MOUSEEVENTF_LEFTDOWN,
        "right": win32con.MOUSEEVENTF_RIGHTDOWN,
        "middle": win32con.MOUSEEVENTF_MIDDLEDOWN,
    }
    win32api.mouse_event(btn_map[button], 0, 0, 0, 0)

def mouse_up(button="left"):
    """Release mouse button."""
    btn_map = {
        "left": win32con.MOUSEEVENTF_LEFTUP,
        "right": win32con.MOUSEEVENTF_RIGHTUP,
        "middle": win32con.MOUSEEVENTF_MIDDLEUP,
    }
    win32api.mouse_event(btn_map[button], 0, 0, 0, 0)

def drag(start_x, start_y, end_x, end_y, duration=0.5):
    """Drag from start to end position."""
    move_mouse(start_x, start_y)
    time.sleep(0.1)
    mouse_down("left")
    time.sleep(0.1)
    steps = 20
    dx = (end_x - start_x) / steps
    dy = (end_y - start_y) / steps
    for i in range(steps):
        move_mouse(int(start_x + dx * (i+1)), int(start_y + dy * (i+1)))
        time.sleep(duration / steps)
    mouse_up("left")

def scroll(clicks):
    """Scroll mouse wheel. Positive=up, negative=down."""
    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, clicks * 120, 0)

# ─── KEYBOARD CONTROL ────────────────────────────────────────────

# Virtual key codes for common keys
VK_CODES = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B,
    "capslock": 0x14, "numlock": 0x90,
}

def _vk_from_key(key):
    """Convert key name to virtual key code."""
    key = key.lower().strip()
    if key in VK_CODES:
        return VK_CODES[key]
    if len(key) == 1:
        return ord(key.upper())
    raise ValueError(f"Unknown key: {key}")

def key_press(key):
    """Press and release a single key."""
    vk = _vk_from_key(key)
    win32api.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)

def key_down(key):
    """Hold a key down."""
    vk = _vk_from_key(key)
    win32api.keybd_event(vk, 0, 0, 0)

def key_up(key):
    """Release a key."""
    vk = _vk_from_key(key)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)

def hotkey(*keys):
    """Press a hotkey combination. E.g., hotkey('ctrl', 'c')"""
    vks = [_vk_from_key(k) for k in keys]
    for vk in vks:
        win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
    for vk in reversed(vks):
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)

def type_text(text, interval=0.02):
    """Type a string of text."""
    for char in text:
        vk = ord(char.upper()) if char.isalpha() else ord(char)
        # Use ctypes for unicode input
        ctypes.windll.user32.keybd_event(0, ctypes.windll.user32.VkKeyScanW(char), 0, 0)
        time.sleep(0.01)
        ctypes.windll.user32.keybd_event(0, ctypes.windll.user32.VkKeyScanW(char), 2, 0)
        time.sleep(interval)

# ─── SCREEN CONTROL ──────────────────────────────────────────────

def get_screen_size():
    """Get screen resolution."""
    w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    return (w, h)

def get_window_list():
    """List all visible windows with titles."""
    windows = []
    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                rect = win32gui.GetWindowRect(hwnd)
                windows.append({
                    "hwnd": hwnd,
                    "title": title,
                    "left": rect[0], "top": rect[1],
                    "right": rect[2], "bottom": rect[3],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1],
                })
    win32gui.EnumWindows(enum_callback, None)
    return windows

def find_window(title_substring):
    """Find a window by title substring."""
    windows = get_window_list()
    for w in windows:
        if title_substring.lower() in w["title"].lower():
            return w
    return None

def activate_window(title_substring):
    """Bring a window to foreground."""
    w = find_window(title_substring)
    if w:
        win32gui.SetForegroundWindow(w["hwnd"])
        time.sleep(0.2)
        return w
    return None

def get_pixel_color(x, y):
    """Get pixel color at screen coordinates."""
    hdc = win32gui.GetDC(0)
    color = win32gui.GetPixel(hdc, x, y)
    win32gui.ReleaseDC(0, hdc)
    r = color & 0xFF
    g = (color >> 8) & 0xFF
    b = (color >> 16) & 0xFF
    return (r, g, b)

# ─── MAIN - Quick test ───────────────────────────────────────────

if __name__ == "__main__":
    print("=== PC Control Module Test ===")
    print(f"Screen: {get_screen_size()}")
    print(f"Mouse: {get_mouse_pos()}")
    
    # List top 10 windows
    windows = get_window_list()
    print(f"\nTop {min(10, len(windows))} visible windows:")
    for w in windows[:10]:
        print(f"  [{w['hwnd']}] \"{w['title']}\" ({w['width']}x{w['height']})")
    
    print("\n✅ PC Control module loaded successfully!")
    print("Available functions:")
    print("  Mouse: get_mouse_pos, move_mouse, click, right_click, drag, scroll")
    print("  Keyboard: key_press, key_down, key_up, hotkey, type_text")
    print("  Screen: get_screen_size, get_window_list, find_window, activate_window, get_pixel_color")
