#!/usr/bin/env python3
"""
poem_qa.py — Poem of the Day end-to-end QA using uiautomator2.

Usage:
    python3 poem_qa.py [--device emulator-5554] [--apk PATH] [--verbose]

Exit codes:
    0 = all checks passed
    1 = checks failed
    2 = setup/installation error
"""
import subprocess, time, json, os, sys, argparse

try:
    import uiautomator2 as u2
except ImportError:
    print("ERROR: uiautomator2 not installed. Run: pip3 install --break-system-packages uiautomator2")
    sys.exit(2)

PKG = 'com.mahoodles.poemoftheday'
ACTIVITY = '.MainActivity'
DEFAULT_APK = '/Users/jonathan/Projects/poem-of-the-day/apps/frontend/poem-of-the-day-v4.apk'
STATE_FILE = '/tmp/poem-qa-state.json'
REPORT_FILE = '/tmp/poem-qa-report.json'
ADB = '/Users/jonathan/Library/Android/sdk/platform-tools/adb'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')


def save_state(**kw):
    s = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            s = json.load(f)
    s.update(kw)
    s['timestamp'] = time.time()
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, indent=2)


def fresh_bounds(d, desc=None, text=None):
    """Get fresh bounds from a fresh element lookup. Avoids cached stale coordinates."""
    if desc is not None:
        el = d(description=desc, timeout=0)
        if el.exists:
            return el.info['bounds']
    if text is not None:
        el = d(text=text, timeout=0)
        if el.exists:
            return el.info['bounds']
    return None


def tap(d, desc=None, text=None):
    """Fresh lookup + tap. Returns True if element found and tapped."""
    if desc is not None:
        el = d(description=desc, timeout=5)
        if el.exists:
            bounds = el.info['bounds']
            cx = (bounds['left'] + bounds['right']) // 2
            cy = (bounds['top'] + bounds['bottom']) // 2
            d.click(cx, cy)
            return True
    if text is not None:
        el = d(text=text, timeout=5)
        if el.exists:
            bounds = el.info['bounds']
            cx = (bounds['left'] + bounds['right']) // 2
            cy = (bounds['top'] + bounds['bottom']) // 2
            d.click(cx, cy)
            return True
    return False


def get_screen_texts(d):
    """Get all visible text strings on screen."""
    texts = []
    for el in d(text=True):
        try:
            t = el.text
            if t and t.strip():
                texts.append(t.strip())
        except Exception:
            pass
    return texts


def get_screen_descs(d):
    """Get all visible content-desc strings on screen."""
    descs = []
    for el in d(description=True):
        try:
            c = el.info.get('contentDescription', '')
            if c:
                descs.append(c)
        except Exception:
            pass
    return descs


def save_report(ok: bool, checks: dict, errors: list):
    report = {'ok': ok, 'checks': checks, 'errors': errors, 'timestamp': time.time()}
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2)
    return report


def run():
    parser = argparse.ArgumentParser(description='Poem of the Day QA')
    parser.add_argument('--device', '-d', default=os.environ.get('ANDROID_DEVICE', 'emulator-5554'))
    parser.add_argument('--apk', '-a', default=os.environ.get('POEM_APK', DEFAULT_APK))
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--no-install', action='store_true', help='Skip APK install')
    args = parser.parse_args()

    log(f'Connecting to {args.device}...')
    try:
        d = u2.connect(args.device)
        log(f'Device OK — SDK {d.info.get("sdkInt", "?")} | Display {d.info.get("displayWidth")}x{d.info.get("displayHeight")}')
    except Exception as e:
        log(f'ERROR: Could not connect to {args.device}: {e}')
        sys.exit(2)

    checks = {}
    errors = []

    # ── 1. Install APK ──────────────────────────────────────────────────────────
    if not args.no_install:
        if not os.path.exists(args.apk):
            log(f'ERROR: APK not found: {args.apk}')
            save_report(False, {}, [f'APK not found: {args.apk}'])
            sys.exit(2)

        log(f'Installing {args.apk}...')
        result = subprocess.run(
            [ADB, '-s', args.device, 'install', '-r', args.apk],
            capture_output=True, text=True, timeout=120
        )
        if 'Success' not in result.stdout:
            log(f'ERROR: Install failed: {result.stdout} {result.stderr}')
            save_report(False, {}, [f'Install failed: {result.stdout}'])
            sys.exit(2)
        log('APK installed OK')
        checks['install'] = 'pass'
    else:
        log('Skipping install (--no-install)')

    # ── 2. Clear and start app ─────────────────────────────────────────────────
    log('Clearing app data...')
    d.app_clear(PKG)
    time.sleep(1)

    log('Starting app...')
    d.app_start(PKG, ACTIVITY)
    time.sleep(7)

    if d.info['currentPackageName'] != PKG:
        log(f'WARNING: App may not have started (current: {d.info["currentPackageName"]})')
        errors.append(f'App not started, got {d.info["currentPackageName"]}')

    # ── 3. Complete onboarding ──────────────────────────────────────────────────
    onboarding_pages = 0
    max_pages = 6

    for page in range(max_pages):
        time.sleep(2)

        # Fresh lookups each iteration (avoids cached stale bounds)
        if tap(d, desc='Skip'):
            bounds = fresh_bounds(d, desc='Skip')
            log(f'  Page {page+1}: tapped Skip at {bounds}')
            time.sleep(3)
            onboarding_pages += 1
            continue

        if tap(d, desc='Next →'):
            bounds = fresh_bounds(d, desc='Next →')
            log(f'  Page {page+1}: tapped Next → at {bounds}')
            time.sleep(3)
            onboarding_pages += 1
            continue

        for text in ['Get Started', 'Start Browsing', 'Start Reading']:
            if tap(d, text=text):
                log(f'  Page {page+1}: tapped "{text}"')
                time.sleep(4)
                onboarding_pages += 1
                break
            if tap(d, desc=text):
                log(f'  Page {page+1}: tapped "{text}" (desc)')
                time.sleep(4)
                onboarding_pages += 1
                break
        else:
            # No skip/next found — check if we're on home screen
            texts = get_screen_texts(d)
            descs = get_screen_descs(d)
            combined = ' '.join(texts + descs)
            home_indicators = ['Home', 'Browse', 'Daily', 'Poem', 'Search', 'Favorites', 'Profile']
            if any(ind in combined for ind in home_indicators):
                log(f'  Onboarding complete — home screen reached')
                break
            else:
                log(f'  Page {page+1}: no skip/next found, trying swipe left...')
                w, h = d.info['displayWidth'], d.info['displayHeight']
                d.swipe(int(w * 0.8), h // 2, int(w * 0.2), h // 2)
                time.sleep(2)

    log(f'Onboarding: {onboarding_pages} page(s) completed')
    checks['onboarding'] = 'pass' if onboarding_pages > 0 else 'fail'

    # ── 4. Verify home screen ─────────────────────────────────────────────────
    time.sleep(3)
    d.screenshot('/tmp/poem/ui_home.png')

    texts = get_screen_texts(d)
    descs = get_screen_descs(d)
    all_content = ' '.join(texts + descs)

    home_indicators = ['Home', 'Browse', 'Daily', 'Poem', 'Search', 'Favorites', 'Profile']
    found_indicators = [ind for ind in home_indicators if ind in all_content]

    log(f'Home screen texts: {texts[:8]}')
    log(f'Home screen descs: {descs[:5]}')

    if found_indicators:
        log(f'HOME VERIFIED: {found_indicators}')
        checks['home_screen'] = 'pass'
    else:
        log(f'HOME NOT FOUND')
        checks['home_screen'] = 'fail'
        errors.append('Home screen not reached after onboarding')

    # ── 5. Verify poem content visible ─────────────────────────────────────────
    poem_texts = [t for t in texts if len(t) > 20]
    if poem_texts:
        log(f'Poem content: {poem_texts[0][:80]}')
        checks['poem_content'] = 'pass'
    else:
        log('WARNING: No long-form poem text found')
        checks['poem_content'] = 'warn'

    # ── 6. Crash check ────────────────────────────────────────────────────────
    result = subprocess.run(
        [ADB, '-s', args.device, 'shell', 'dumpsys', 'package', PKG],
        capture_output=True, text=True, timeout=10
    )
    if 'has crashed' in result.stdout.lower():
        log('CRASH DETECTED')
        checks['crash'] = 'fail'
        errors.append('App crash detected')
    else:
        log('No crash detected')
        checks['crash'] = 'pass'

    # ── 7. Navigate to Browse tab ───────────────────────────────────────────────
    if tap(d, desc='Browse'):
        time.sleep(3)
        browse_texts = get_screen_texts(d)
        log(f'Browse screen: {browse_texts[:5]}')
        checks['browse_nav'] = 'pass'
        d.press_back()
        time.sleep(2)
    elif tap(d, text='Browse'):
        time.sleep(3)
        browse_texts = get_screen_texts(d)
        log(f'Browse screen: {browse_texts[:5]}')
        checks['browse_nav'] = 'pass'
        d.press_back()
        time.sleep(2)
    else:
        log('Browse tab: not found (may be labelled differently)')
        checks['browse_nav'] = 'warn'

    # ── Summary ────────────────────────────────────────────────────────────────
    ok = all(v != 'fail' for v in checks.values())
    save_report(ok, checks, errors)

    log('')
    log('══════════════════════════════════════')
    for k, v in checks.items():
        icon = '✅' if v == 'pass' else ('⚠️' if v == 'warn' else '❌')
        log(f'  {icon} {k}: {v}')
    log('══════════════════════════════════════')
    if errors:
        for e in errors:
            log(f'  ❌ {e}')
    log(f'Overall: {"PASS ✅" if ok else "FAIL ❌"}')
    log(f'Report: {REPORT_FILE}')
    log(f'Screenshot: /tmp/poem/ui_home.png')

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    try:
        os.makedirs('/tmp/poem', exist_ok=True)
        run()
    except Exception as e:
        log(f'FATAL ERROR: {e}')
        import traceback
        traceback.print_exc()
        save_report(False, {}, [str(e)])
        sys.exit(2)
