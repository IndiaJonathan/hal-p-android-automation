# Android Automation Skill

**Skill:** `android-automation`  
**Repo:** https://github.com/IndiaJonathan/hal-p-android-automation  
**Type:** Device Control / QA Automation  
**Purpose:** Click, tap, swipe, dump UI, screenshot, install APK, verify screen state on Android devices.

---

## TL;DR — Quick Start

```bash
# Install
pip3 install --break-system-packages uiautomator2

# Connect (real device via USB, or emulator via serial)
python3 -c "import uiautomator2 as u2; d = u2.connect('emulator-5554')"
python3 -c "import uiautomator2 as u2; d = u2.connect_usb('YOUR_SERIAL')"

# Tap by content-desc
d(description="Skip").click()

# Tap by text
d(text="Sign In").click()

# Type
d.set_fastinput_ime(True)
d.send_text("hello@example.com")
d.set_fastinput_ime(False)

# Screenshot
d.screenshot("/tmp/screen.png")

# Run QA
python3 scripts/poem_qa.py --device emulator-5554
```

---

## Core Library: uiautomator2

`uiautomator2` is the standard Python Android automation library. It works via an HTTP server on the device (`atx-agent` + `u2.jar`).

### Installation

```bash
pip3 install --break-system-packages uiautomator2
```

### Device Connection

```python
import uiautomator2 as u2

# Emulator
d = u2.connect('emulator-5554')        # via ADB port forward
d = u2.connect('localhost:5557')       # direct emulator VNC port

# Real device (USB debugging enabled)
d = u2.connect_usb('SERIAL')           # USB via ADB serial

# WiFi (device must have atx-agent running)
d = u2.connect('http://192.168.1.100:9007')
```

### IMPORTANT: atx-agent Required

uiautomator2 **requires `atx-agent` to be installed on the device** for full functionality:
- Real Android device: `python -m uiautomator2 install-daemon` (from a computer with the device connected via USB) — this pushes `atx-agent` and `u2.jar` to the device
- Emulator: `atx-agent` is **not pre-installed** by default. For emulators, use the **pure subprocess fallback** (see below)

When `atx-agent` is running, u2 operations are reliable (tap, swipe, text, screenshot all work). When it's not running, UI operations hang or fail.

### Verify Connection

```python
d = u2.connect('emulator-5554')
print(d.info)  # prints device info — works even without atx-agent
```

---

## Pure Subprocess Fallback (Emulators)

For emulators without `atx-agent`, use direct ADB commands. This works but taps may be unreliable on ARM emulators due to virtio multi-touch quirks.

```bash
# Tap (works reliably on x86 emulators, flaky on ARM)
~/Library/Android/sdk/platform-tools/adb shell "input touchscreen tap X Y"

# Screenshot
~/Library/Android/sdk/platform-tools/adb exec-out screencap -p > screen.png

# UI dump
~/Library/Android/sdk/platform-tools/adb exec-out uiautomator dump /sdcard/ui.xml
~/Library/Android/sdk/platform-tools/adb exec-out cat /sdcard/ui.xml > ui.xml
```

See `scripts/android_ui.py` to parse the UI dump and find element coordinates.

---

## Scripts Provided

| Script | Purpose |
|--------|---------|
| `android_controller.py` | ADB wrapper using pure subprocess. Use for emulators without atx-agent. |
| `poem_qa.py` | Poem of the Day QA runner. Works with both u2 (real device) and subprocess (emulator). |
| `android_ui.py` | Parse `uiautomator dump` XML. Find elements by text/desc/bounds. CLI: `python3 android_ui.py ui.xml --find "Sign In"` |

---

## poem_qa.py Usage

```bash
# Run full QA (installs APK, completes onboarding, verifies home screen)
python3 scripts/poem_qa.py --device emulator-5554 --apk ./app-release.apk

# Skip install (app already on device)
python3 scripts/poem_qa.py --device emulator-5554 --no-install

# Real device via USB
python3 scripts/poem_qa.py --device USB:SERIAL --apk ./app-release.apk
```

Exit codes: `0` = pass, `1` = fail, `2` = error

---

## Quick Reference

### Find and tap elements
```python
d(description="Skip").click()
d(text="Sign In").click()
d.xpath('//android.widget.Button[@text="Next"]').click()
```

### Get fresh element bounds (avoid cached stale coordinates)
```python
el = d(description="Skip", timeout=0)  # fresh lookup
bounds = el.info['bounds']
cx = (bounds['left'] + bounds['right']) // 2
cy = (bounds['top'] + bounds['bottom']) // 2
d.click(cx, cy)
```

### Swipe
```python
d.swipe(540, 1500, 540, 500)  # swipe up
d.swipe(800, 960, 280, 960)    # swipe left
```

### App management
```python
d.app_start('com.example.app')
d.app_clear('com.example.app')  # fresh start
d.app_stop('com.example.app')
```

### Wait for element
```python
if d(description="Home", timeout=10).exists():
    d(description="Home").click()
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `d.info` works but `click()` hangs | `atx-agent` not running | Install: `python -m uiautomator2 install-daemon` |
| All taps silently do nothing | `atx-agent` not running | Same as above |
| Element found but wrong coordinates | Cached element reference | Always fresh lookup: `d(desc).click()` directly |
| Emulator tap misses target | ARM virtio multi-touch conflict | Use real device, or accept slight coordinate drift |
| `pip install uiautomator2` fails | PEP 668 pinned env | `pip3 install --break-system-packages uiautomator2` |

---

## Pre-Delivery QA Checklist (use poem_qa.py)

- [ ] APK installs cleanly (`Success` from `adb install`)
- [ ] App launches to onboarding (not crash/blank screen)
- [ ] Onboarding completes — reaches home/main screen
- [ ] Home screen shows poem content
- [ ] No crash logged in `dumpsys package`
- [ ] Tab navigation works (Browse, Favorites, Profile)
