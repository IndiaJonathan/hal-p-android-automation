#!/usr/bin/env python3
"""
poem_qa.py — Poem of the Day QA automation.
Run a full pass: install APK, complete onboarding, verify home screen, report.
"""
import sys, os, time, json

sys.path.insert(0, os.path.dirname(__file__))
import android_controller as adb
import android_ui

PKG = 'com.mahoodles.poemoftheday'
ACTIVITY = '.MainActivity'
APK = os.environ.get('POEM_APK', '/Users/jonathan/Projects/poem-of-the-day/apps/frontend/poem-of-the-day-v4.apk')
os.makedirs('/tmp/poem', exist_ok=True)
STATE_FILE = '/tmp/poem-qa-state.json'

def save_state(**kw):
    s = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            s = json.load(f)
    s.update(kw)
    s['timestamp'] = time.time()
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, indent=2)

def find_and_tap(dev, text, ui_path):
    """Find clickable element by text in current UI and tap it. Returns center coords."""
    elements = android_ui.parse_ui(ui_path)
    # Try to find a clickable element with this text or containing this text
    clickable = android_ui.find_clickable_parent(elements, text)
    if not clickable:
        # Fall back to any element with this text
        results = android_ui.find_by_text(elements, text)
        if not results:
            results = android_ui.find_by_content_desc(elements, text)
        if not results:
            return None
        clickable = results[0]
    cx, cy = clickable.center()
    dev.tap(cx, cy)
    return (cx, cy)

def run():
    print(f'=== Poem of the Day QA ===')
    dev = adb.AndroidDevice()
    print(f'Device: {dev.serial}')

    # 1. Install APK
    print(f'Installing {APK}...')
    ok = dev.install(APK)
    if not ok:
        print('FAIL: APK install failed')
        save_state(step='install', ok=False)
        return False
    print('APK installed OK')
    save_state(step='install', ok=True)

    # 2. Clear app data (fresh start)
    print('Clearing app data...')
    dev.clear_app(PKG)
    time.sleep(1)

    # 3. Start app
    print('Starting app...')
    dev.start_app(PKG, ACTIVITY)
    time.sleep(6)

    # 4. Get current screen
    ui_path = dev.dump_ui('/tmp/poem/ui_initial.xml')
    dev.screenshot('/tmp/poem/ui_initial.png')
    elements = android_ui.parse_ui(ui_path)
    texts = [(e.text, e.bounds) for e in elements if e.text.strip()]
    print(f'Initial screen texts: {texts[:5]}')

    # 5. Complete onboarding
    # Try to find and tap Skip on each page
    pages_completed = 0
    for page in range(5):  # max 5 pages
        time.sleep(2)
        ui_path = dev.dump_ui(f'/tmp/poem/ui_page{page}.xml')
        dev.screenshot(f'/tmp/poem/ui_page{page}.png')
        elements = android_ui.parse_ui(ui_path)

        # Look for Skip or Get Started
        for text in ['Skip', 'Get Started', 'Start Browsing']:
            coords = find_and_tap(dev, text, ui_path)
            if coords:
                print(f'Tapped "{text}" at {coords}')
                pages_completed += 1
                time.sleep(3)
                break
        else:
            # Check if we're already on the main app
            home_texts = [e.text for e in elements if e.text.strip()]
            if any(t for t in home_texts if t in ['Home', 'Browse', 'Favorites', 'Search', 'Profile']):
                print('Already on main app screen')
                break
            print(f'Could not find Skip/Get Started on page {page}, trying Next')
            # Try Next
            coords = find_and_tap(dev, 'Next', ui_path)
            if coords:
                print(f'Tapped "Next" at {coords}')
                time.sleep(2)
            else:
                print(f'No more pages found on iteration {page}')
                break

    print(f'Onboarding pages completed: {pages_completed}')
    save_state(step='onboarding', pages=pages_completed)

    # 6. Verify we're on the home/main screen
    time.sleep(3)
    ui_path = dev.dump_ui('/tmp/poem/ui_home.xml')
    dev.screenshot('/tmp/poem/ui_home.png')
    elements = android_ui.parse_ui(ui_path)
    texts = [e.text for e in elements if e.text.strip()]
    print(f'Home screen texts: {texts[:10]}')

    # 7. Look for poem content indicators
    poem_indicators = ['Poem', 'Browse', 'Daily', 'Today']
    found = [t for t in texts if any(ind.lower() in t.lower() for ind in poem_indicators)]
    if found:
        print(f'HOME SCREEN VERIFIED: {found}')
        save_state(step='home', verified=True, indicators=found)
    else:
        print('WARNING: No poem content indicators found on home screen')
        save_state(step='home', verified=False, texts=texts[:10])

    # 8. Check for crash
    crash_output = dev.shell('dumpsys package com.mahoodles.poemoftheday | grep -i crash')
    if crash_output.strip():
        print(f'CRASH DETECTED: {crash_output}')
        save_state(step='crash', detected=True)
    else:
        print('No crash detected')
        save_state(step='crash', detected=False)

    print('=== QA Complete ===')
    return True

if __name__ == '__main__':
    try:
        ok = run()
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f'ERROR: {e}')
        import traceback
        traceback.print_exc()
        save_state(step='error', error=str(e))
        sys.exit(1)
