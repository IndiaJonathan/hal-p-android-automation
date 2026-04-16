# Android Automation Skill

**Skill:** `android-automation`
**Type:** Device Control / QA Automation  
**Purpose:** Headless/headed Android app interaction via ADB — click, tap, swipe, dump UI, screenshot, install APK, verify screen state.  

---

## Core Concepts

### ADB (Android Debug Bridge)
All automation runs through `adb` commands executed via `exec`. ADB is at:
```
~/Library/Android/sdk/platform-tools/adb
```

### Emulator vs Real Device
- **Emulator:** connect via `adb connect emulator-5554` or auto-detect
- **Real device:** must have USB debugging enabled, connected via USB or same WiFi
- Emulator is unreliable for taps (ARM hypervisor + virtio multi-touch conflicts); prefer element-based coordinates over hardcoded taps

### Emulator Startup
```bash
# List available AVDs
~/Library/Android/sdk/emulator/emulator -list-avds

# Start a specific AVD (headless: -no-window; headed: omit)
nohup ~/Library/Android/sdk/emulator/emulator -avd AVD_NAME \
  -no-snapshot-load -no-audio -no-boot-anim > /tmp/emulator.log 2>&1 &

# Wait for boot
sleep 30
~/Library/Android/sdk/platform-tools/adb wait-for-device
```

### Always Check Device First
```bash
~/Library/Android/sdk/platform-tools/adb devices -l
```
Confirm exactly one device is present before running any interaction.

---

## UI Automation Flow

### Step 1 — Dump UI Hierarchy
```bash
~/Library/Android/sdk/platform-tools/adb exec-out uiautomator dump /sdcard/ui.xml
~/Library/Android/sdk/platform-tools/adb exec-out cat /sdcard/ui.xml > /tmp/ui.xml
```

### Step 2 — Parse Element Coordinates
Use `scripts/android_ui.py` to find element bounds:
```bash
python3 scripts/android_ui.py /tmp/ui.xml find --text "Sign In"
python3 scripts/android_ui.py /tmp/ui.xml find --clickable
python3 scripts/android_ui.py /tmp/ui.xml find --bounds "0,158][192,263"
```

### Step 3 — Tap by Coordinates
```bash
# Physical screen tap
~/Library/Android/sdk/platform-tools/adb shell "input touchscreen tap X Y"

# If simple tap doesn't work (virtio conflict), try:
~/Library/Android/sdk/platform-tools/adb shell "input tap X Y"
~/Library/Android/sdk/platform-tools/adb shell "sendevent /dev/input/eventX 3 0 X_SCREEN 0"
~/Library/Android/sdk/platform-tools/adb shell "sendevent /dev/input/eventX 3 1 Y_SCREEN 0"
```

### Step 4 — Wait + Screenshot
```bash
sleep 2
~/Library/Android/sdk/platform-tools/adb exec-out screencap -p > /tmp/screen.png
```

---

## Screenshot
```bash
~/Library/Android/sdk/platform-tools/adb exec-out screencap -p > /tmp/screen.png
# Or from script:
python3 scripts/android_screen.py [--output /tmp/screen.png]
```

---

## App Management
```bash
# Install/update APK
~/Library/Android/sdk/platform-tools/adb install -r /path/to.apk

# Clear app data (fresh start)
~/Library/Android/sdk/platform-tools/adb shell "pm clear com.package.name"

# Start app
~/Library/Android/sdk/platform-tools/adb shell "am start -n com.package.name/.MainActivity"

# Check if app is running
~/Library/Android/sdk/platform-tools/adb shell "dumpsys activity activities" | grep "com.package.name"
```

---

## Network / Proxy
```bash
# Set HTTP proxy (for emulator, use 10.0.2.2:PORT to reach host Mac)
~/Library/Android/sdk/platform-tools/adb shell "settings put global http_proxy 10.0.2.2:8111"

# Remove proxy
~/Library/Android/sdk/platform-tools/adb shell "settings put global http_proxy :0"

# Check proxy
~/Library/Android/sdk/platform-tools/adb shell "settings get global http_proxy"
```

---

## State Files (per-session)

Automation should write state to:
```
/tmp/android-automation-state.json
```

```json
{
  "session": "poem-qa-001",
  "last_screen": "HomeScreen",
  "last_screenshot": "/tmp/screen.png",
  "last_ui_dump": "/tmp/ui.xml",
  "last_tap": { "x": 540, "y": 1330 },
  "last_navigation": "Auth"
}
```

---

## Script Reference

| Script | Purpose |
|--------|---------|
| `scripts/android_ui.py` | Parse UI dump XML, find elements by text/desc/bounds/clickable |
| `scripts/android_screen.py` | Capture screenshot, optionally compare with baseline |
| `scripts/android_controller.py` | Python module — ADB wrapper + controller class |

---

## Example: Complete Sign-in Flow
```python
import subprocess, time
import scripts.android_controller as adb

device = adb.AndroidDevice()  # auto-detects device

# Start app fresh
device.clear_app("com.mahoodles.poemoftheday")
device.start_app("com.mahoodles.poemoftheday")
time.sleep(5)

# Dump UI and find Sign In button
device.dump_ui("/tmp/ui.xml")
elements = adb.find_elements("/tmp/ui.xml", text="Sign In")
tap_coords = elements[0].center()
device.tap(*tap_coords)
time.sleep(2)

# Type email
device.dump_ui("/tmp/ui2.xml")
email_field = adb.find_element("/tmp/ui2.xml", text="Email")
device.tap(*email_field.center())
device.type_text("test@poem.test")

# Take screenshot
device.screenshot("/tmp/post-signin.png")
```

---

## Limitations / Known Issues

- **Emulator taps:** `input tap` may not work reliably on ARM emulators (virtio multi-touch conflict). Use `sendevent` or accept headed browser testing as alternative.
- **Real device:** `exec-out screencap` works on both emulator and real device.
- **App not debuggable:** `run-as` package debugging requires debuggable flag; for release builds, use accessibility dump only.
- **Timing:** Always `sleep` after taps — UI takes time to update.
