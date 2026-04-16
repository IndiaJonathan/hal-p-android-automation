#!/usr/bin/env python3
"""
android_controller.py — uiautomator2 wrapper for Android automation.
pip install: pip3 install --break-system-packages uiautomator2
"""
import uiautomator2 as u2, time, os, json, subprocess
from typing import Optional

DEFAULT_DEVICE = 'emulator-5554'
STATE_FILE = '/tmp/android-automation-state.json'

def connect(serial: Optional[str] = None) -> u2.Device:
    """Connect to a device. Auto-detects emulator if no serial given."""
    if serial:
        return u2.connect(serial)
    # Try to auto-detect
    output = subprocess.run(
        ['/Users/jonathan/Library/Android/sdk/platform-tools/adb', 'devices', '-l'],
        capture_output=True, text=True
    ).stdout
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'device':
            serial = parts[0]
            break
    if not serial:
        raise RuntimeError('No Android device found')
    return u2.connect(serial)


class AndroidDevice:
    """High-level Android automation using uiautomator2."""

    def __init__(self, serial: Optional[str] = None):
        self._serial = serial or os.environ.get('ANDROID_SERIAL', DEFAULT_DEVICE)
        self._d = connect(self._serial)
        self._last_screenshot = None

    @property
    def d(self) -> u2.Device:
        return self._d

    @property
    def serial(self) -> str:
        return self._serial

    # ─── Navigation ─────────────────────────────────────────────────────────────

    def start(self, package: str, activity: str = '.MainActivity') -> None:
        """Start an app by package/activity."""
        self._d.app_start(package, activity)

    def stop(self, package: str) -> None:
        """Stop an app."""
        self._d.app_stop(package)

    def clear(self, package: str) -> None:
        """Clear app data (fresh start)."""
        self._d.app_clear(package)

    def restart(self, package: str, activity: str = '.MainActivity') -> None:
        """Stop and start an app."""
        self._d.app_stop(package)
        time.sleep(1)
        self._d.app_start(package, activity)

    def press_back(self) -> None:
        self._d.press.back()

    def press_home(self) -> None:
        self._d.press.home()

    # ─── Input ────────────────────────────────────────────────────────────────

    def tap(self, x: int, y: int) -> None:
        """Tap at coordinates."""
        self._d.click(x, y)

    def tap_element(self, element) -> None:
        """Tap a uiautomator2 element."""
        element.click()

    def click_description(self, desc: str, timeout: float = 10) -> bool:
        """Find by content-desc and tap. Returns True if found."""
        el = self._d(description=desc, timeout=timeout)
        if el.exists:
            el.click()
            return True
        return False

    def click_text(self, text: str, timeout: float = 10) -> bool:
        """Find by text and tap. Returns True if found."""
        el = self._d(text=text, timeout=timeout)
        if el.exists:
            el.click()
            return True
        return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None:
        """Swipe from (x1,y1) to (x2,y2) over duration seconds."""
        self._d.swipe(x1, y1, x2, y2, duration=duration)

    def swipe_up(self, duration: float = 0.5) -> None:
        """Swipe up (scroll up)."""
        w, h = self.screen_size()
        self._d.swipe(w // 2, int(h * 0.8), w // 2, int(h * 0.2), duration=duration)

    def swipe_down(self, duration: float = 0.5) -> None:
        """Swipe down."""
        w, h = self.screen_size()
        self._d.swipe(w // 2, int(h * 0.2), w // 2, int(h * 0.8), duration=duration)

    def long_press(self, x: int, y: int, duration: float = 1.0) -> None:
        """Long press at coordinates."""
        self._d.long_click(x, y, duration=duration)

    def set_text(self, text: str) -> None:
        """Type text (requires focused input)."""
        self._d.set_fastinput_ime(True)
        self._d.send_text(text)
        self._d.set_fastinput_ime(False)

    def press_enter(self) -> None:
        self._d.press.enter()

    def press_delete(self) -> None:
        self._d.press.delete()

    def clear_text_field(self) -> None:
        """Clear current text field."""
        self._d.press.delete()
        self._d.press("enter")  # dismiss any autocomplete

    # ─── Screen ────────────────────────────────────────────────────────────────

    def screenshot(self, path: str = '/tmp/android_screen.png') -> str:
        """Capture screenshot. Returns path."""
        self._d.screenshot(path)
        self._last_screenshot = path
        return path

    def screen_size(self) -> tuple[int, int]:
        """Return (width, height)."""
        info = self._d.info
        return (info['displayWidth'], info['displayHeight'])

    # ─── Queries ───────────────────────────────────────────────────────────────

    def exists_description(self, desc: str) -> bool:
        return self._d(description=desc).exists

    def exists_text(self, text: str) -> bool:
        return self._d(text=text).exists

    def wait_for_description(self, desc: str, timeout: float = 10) -> bool:
        """Wait for content-desc to appear."""
        return self._d(description=desc, timeout=timeout).wait(timeout=timeout)

    def wait_for_text(self, text: str, timeout: float = 10) -> bool:
        """Wait for text to appear."""
        return self._d(text=text, timeout=timeout).wait(timeout=timeout)

    def get_texts(self) -> list[str]:
        """Get all visible text on screen."""
        texts = []
        for el in self._d(text=True):
            try:
                if el.text and el.text.strip():
                    texts.append(el.text.strip())
            except Exception:
                pass
        return texts

    def get_descriptions(self) -> list[tuple[str, str]]:
        """Get all visible content-descriptions with their values."""
        results = []
        for el in self._d(description=True):
            try:
                desc = el.info.get('contentDescription', '')
                if desc:
                    results.append(desc)
            except Exception:
                pass
        return results

    # ─── App Info ─────────────────────────────────────────────────────────────

    def current_package(self) -> str:
        return self._d.info.get('currentPackageName', '')

    def device_info(self) -> dict:
        info = self._d.info
        return {
            'serial': self._serial,
            'package': info.get('currentPackageName', ''),
            'display': (info.get('displayWidth', 0), info.get('displayHeight', 0)),
            'sdk': info.get('sdkInt', 0),
        }

    # ─── State ────────────────────────────────────────────────────────────────

    def save_state(self, action: str, **data) -> None:
        state = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                state = json.load(f)
        state['last_action'] = action
        state['last_data'] = data
        state['timestamp'] = time.time()
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)

    # ─── Wait helpers ─────────────────────────────────────────────────────────

    def wait(self, seconds: float) -> None:
        time.sleep(seconds)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
