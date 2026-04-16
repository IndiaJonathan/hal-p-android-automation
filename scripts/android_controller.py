#!/usr/bin/env python3
"""android_controller.py — ADB wrapper + AndroidDevice class for automation."""
import subprocess, time, os, json
from pathlib import Path
from typing import Optional

ADB = os.environ.get('ADB_PATH', '/Users/jonathan/Library/Android/sdk/platform-tools/adb')

# ─── ADB Helpers ────────────────────────────────────────────────────────────────

def run(*args, timeout: int = 10) -> str:
    cmd = [ADB] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()

def shell(cmd: str, timeout: int = 10) -> str:
    return run('shell', cmd, timeout=timeout)

def exec_out(cmd: str, timeout: int = 15) -> bytes:
    """Use exec-out for binary output (screenshots)."""
    result = subprocess.run(
        [ADB, 'exec-out', cmd], capture_output=True, timeout=timeout
    )
    return result.stdout

# ─── Device Detection ──────────────────────────────────────────────────────────

def get_device() -> Optional[str]:
    """Return the first available device serial, or None."""
    output = run('devices', '-l')
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in ('device', 'unauthorized'):
            return parts[0]
    return None

def wait_for_device(timeout: int = 60):
    """Block until a device is available."""
    run('wait-for-device')
    time.sleep(2)  # give boot animation time to settle

def device_info(serial: Optional[str] = None) -> dict:
    """Get device properties."""
    prefix = ['-s', serial] if serial else []
    out = shell('getprop ro.build.version.release')
    model = shell('getprop ro.product.model')
    manufacturer = shell('getprop ro.product.manufacturer')
    sdk = shell('getprop ro.build.version.sdk')
    return {
        'release': out, 'model': model, 'manufacturer': manufacturer,
        'sdk': sdk, 'serial': serial or get_device()
    }

# ─── UI / Screenshot ───────────────────────────────────────────────────────────

UI_DUMP_REMOTE = '/sdcard/ui.xml'
DEFAULT_UI_LOCAL = '/tmp/android_ui.xml'
DEFAULT_SCREEN_LOCAL = '/tmp/android_screen.png'
STATE_FILE = '/tmp/android-automation-state.json'

def dump_ui(local_path: str = DEFAULT_UI_LOCAL) -> str:
    """Dump UI hierarchy to local file. Returns local path."""
    shell(f'uiautomator dump {UI_DUMP_REMOTE}')
    data = exec_out(f'cat {UI_DUMP_REMOTE}')
    with open(local_path, 'wb') as f:
        f.write(data)
    return local_path

def screenshot(local_path: str = DEFAULT_SCREEN_LOCAL) -> str:
    """Capture screenshot. Returns local path."""
    data = exec_out('screencap -p')
    with open(local_path, 'wb') as f:
        f.write(data)
    return local_path

# ─── Input Events ──────────────────────────────────────────────────────────────

def tap(x: int, y: int, use_sendevent: bool = False) -> None:
    """Tap screen at (x, y)."""
    if use_sendevent:
        # Try sendevent path for virtio touch devices
        _sendevent_tap(x, y)
    else:
        shell(f'input touchscreen tap {x} {y}')
    _save_state('tap', {'x': x, 'y': y})

def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
    """Swipe from (x1,y1) to (x2,y2)."""
    shell(f'input swipe {x1} {y1} {x2} {y2} {duration_ms}')
    _save_state('swipe', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})

def type_text(text: str) -> None:
    """Type text (requires keyboard to be visible)."""
    # Escape special shell characters
    escaped = text.replace(' ', '%s').replace("'", "''")
    shell(f'input text "{escaped}"')

def press_key(keycode: int) -> None:
    """Send a keycode (e.g. 4=back, 66=enter, 67=delete)."""
    shell(f'input keyevent {keycode}')

def clear_text_field() -> None:
    """Clear text by selecting all and deleting."""
    shell('input keyevent 67')  # delete
    time.sleep(0.1)

def dismiss_keyboard() -> None:
    shell('input keyevent 4')  # back / dismiss

# ─── App Management ────────────────────────────────────────────────────────────

def install_apk(apk_path: str, upgrade: bool = True) -> bool:
    """Install APK. Returns True on success."""
    cmd = [ADB, 'install']
    if upgrade:
        cmd.append('-r')
    cmd.append(apk_path)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return 'Success' in result.stdout

def clear_app(package: str) -> None:
    shell(f'pm clear {package}')

def start_app(package: str, activity: str = '.MainActivity') -> None:
    shell(f'am start -n {package}/{activity}')

def get_current_activity(package: str) -> Optional[str]:
    """Get the current activity for a package."""
    output = shell(f'dumpsys activity activities | grep {package}')
    for line in output.splitlines():
        if 'mResumedActivity' in line or 'mFocusedApp' in line:
            return line.strip()
    return None

# ─── State ────────────────────────────────────────────────────────────────────

def _save_state(action: str, data: dict):
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
    state['last_action'] = action
    state['last_data'] = data
    state['timestamp'] = time.time()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

# ─── Proxy ────────────────────────────────────────────────────────────────────

def set_proxy(host: str = '10.0.2.2', port: int = 8111) -> None:
    """Set HTTP proxy on device (for emulator -> host Mac)."""
    shell(f'settings put global http_proxy {host}:{port}')

def clear_proxy() -> None:
    shell('settings put global http_proxy :0')

def get_proxy() -> str:
    return shell('settings get global http_proxy').strip()

# ─── AndroidDevice Class (convenience wrapper) ─────────────────────────────────

class AndroidDevice:
    def __init__(self, serial: Optional[str] = None):
        self.serial = serial or get_device()
        if not self.serial:
            raise RuntimeError('No Android device found. Is ADB running?')
        self.prefix = [ADB, '-s', self.serial] if self.serial else [ADB]

    def run(self, *args, **kw):
        kw.setdefault('timeout', 10)
        return run(*([self.serial] if self.serial else []) + list(args), **kw)

    def shell(self, cmd: str, **kw):
        return shell(cmd, **kw)

    def dump_ui(self, path: str = DEFAULT_UI_LOCAL) -> str:
        return dump_ui(path)

    def screenshot(self, path: str = DEFAULT_SCREEN_LOCAL) -> str:
        return screenshot(path)

    def tap(self, x: int, y: int) -> None:
        tap(x, y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> None:
        swipe(x1, y1, x2, y2, ms)

    def type_text(self, text: str) -> None:
        type_text(text)

    def install(self, apk: str) -> bool:
        return install_apk(apk)

    def clear_app(self, pkg: str) -> None:
        clear_app(pkg)

    def start_app(self, pkg: str, activity: str = '.MainActivity') -> None:
        start_app(pkg, activity)

    def set_proxy(self, host: str = '10.0.2.2', port: int = 8111) -> None:
        set_proxy(host, port)

    def clear_proxy(self) -> None:
        clear_proxy()

    def info(self) -> dict:
        return device_info(self.serial)


if __name__ == '__main__':
    dev = AndroidDevice()
    print(f'Device: {dev.serial}')
    print(f'Info: {dev.info()}')
