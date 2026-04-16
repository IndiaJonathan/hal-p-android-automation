#!/usr/bin/env python3
"""
android_runner.py — High-level Android automation runner.
Usage:
  python3 android_runner.py [task] [options]

Tasks:
  explore         Dump UI, show all tappable elements
  tap-text TEXT   Find element by text and tap it
  tap-coords X Y Tap at coordinates
  swipe-dir DIR   Swipe direction (up/down/left/right)
  install APK     Install APK
  start PKG      Start app (package.Activity or just package)
  verify TEXT    Verify TEXT is visible on screen
  flow FILE      Run a JSON flow file

Flow file format (JSON):
  [
    {"action": "tap-text", "text": "Sign In"},
    {"action": "wait", "seconds": 2},
    {"action": "dump"},
    {"action": "type", "field": "Email", "text": "test@poem.test"},
    ...
  ]
"""
import sys, os, json, time, subprocess

sys.path.insert(0, os.path.dirname(__file__))
import android_controller as adb
import android_ui

STATE_FILE = '/tmp/android-automation-state.json'

def update_state(**kw):
    s = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            s = json.load(f)
    s.update(kw)
    s['timestamp'] = time.time()
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, indent=2)

def wait_for_boot(dev):
    """Wait for device to be fully booted."""
    for _ in range(30):
        out = dev.shell('getprop sys.boot_completed').strip()
        if out == '1':
            return True
        time.sleep(2)
    return False

def do_explore(dev, args):
    """Dump UI and show all elements."""
    path = dev.dump_ui('/tmp/ui_explore.xml')
    elements = android_ui.parse_ui(path)

    if args.text:
        results = android_ui.find_by_text(elements, args.text)
        print(f'Elements matching "{args.text}":')
        for e in results:
            print(f'  {e}')
    elif args.clickable:
        print('Clickable elements:')
        android_ui.print_elements(elements, clickable_only=True)
    else:
        print('All texts on screen:')
        android_ui.print_elements(elements)

    update_state(action='explore', screen_path=path, element_count=len(elements))
    return elements

def do_tap_text(dev, args):
    """Find element by text and tap it."""
    path = dev.dump_ui('/tmp/ui_tap.xml')
    elements = android_ui.parse_ui(path)

    results = android_ui.find_by_text(elements, args.text)
    if not results:
        results = android_ui.find_by_content_desc(elements, args.text)

    if not results:
        print(f'ERROR: No element found matching: {args.text}')
        print('All texts:')
        android_ui.print_elements(elements)
        sys.exit(1)

    # Prefer clickable elements
    clickable = [e for e in results if e.clickable]
    target = clickable[0] if clickable else results[0]
    cx, cy = target.center()
    print(f'Tapping: "{target.text or target.content_desc}" at ({cx},{cy})')
    dev.tap(cx, cy)
    update_state(action='tap-text', text=args.text, coords=(cx, cy))

def do_tap_coords(dev, args):
    x, y = int(args.x), int(args.y)
    print(f'Tapping at ({x},{y})')
    dev.tap(x, y)
    update_state(action='tap-coords', coords=(x, y))

def do_swipe(dev, args):
    """Swipe in direction. Uses screen center as start point."""
    w_out = dev.shell('wm size').strip()
    # e.g. "Physical size: 1080x1920"
    try:
        wh = w_out.split(':')[-1].strip()
        w, h = map(int, wh.split('x'))
    except:
        w, h = 540, 960  # fallback

    cx, cy = w // 2, h // 2
    dist = min(w, h) // 3
    dirs = {
        'up':    (cx, cy - dist, cx, cy + dist),
        'down':  (cx, cy + dist, cx, cy - dist),
        'left':  (cx - dist, cy, cx + dist, cy),
        'right': (cx + dist, cy, cx - dist, cy),
    }
    if args.dir not in dirs:
        print(f'Unknown direction: {args.dir}. Use: up/down/left/right')
        sys.exit(1)

    x1, y1, x2, y2 = dirs[args.dir]
    print(f'Swiping {args.dir}: ({x1},{y1}) → ({x2},{y2})')
    dev.swipe(x1, y1, x2, y2, 400)
    update_state(action='swipe', direction=args.dir)

def do_install(dev, args):
    pkg = args.package or 'com.unknown.app'
    print(f'Installing {args.apk}...')
    ok = dev.install(args.apk)
    print('Success' if ok else 'FAILED')
    sys.exit(0 if ok else 1)

def do_start(dev, args):
    pkg, activity = args.pkg, None
    if '/' in pkg:
        pkg, activity = pkg.split('/', 1)
    dev.start_app(pkg, activity or '.MainActivity')
    print(f'Started: {pkg}/{activity or ".MainActivity"}')
    update_state(action='start', package=pkg)

def do_verify(dev, args):
    """Wait for text to appear on screen (poll for N seconds)."""
    path = '/tmp/ui_verify.xml'
    found = False
    for i in range(int(args.timeout)):
        dev.dump_ui(path)
        elements = android_ui.parse_ui(path)
        results = android_ui.find_by_text(elements, args.text)
        if results:
            print(f'FOUND: "{args.text}" appeared after ~{i}s')
            update_state(action='verify', text=args.text, found=True, wait_time=i)
            sys.exit(0)
        time.sleep(1)

    print(f'NOT FOUND: "{args.text}" after {args.timeout}s')
    android_ui.print_elements(android_ui.parse_ui(path))
    update_state(action='verify', text=args.text, found=False)
    sys.exit(1)

def do_wait(dev, args):
    t = float(args.seconds)
    print(f'Waiting {t}s...')
    time.sleep(t)

def do_dump(dev, args):
    path = args.output or '/tmp/ui_dump.xml'
    dev.dump_ui(path)
    print(f'Dumped UI to: {path}')
    return path

def do_screenshot(dev, args):
    path = args.output or '/tmp/android_screen.png'
    dev.screenshot(path)
    print(f'Screenshot: {path}')

def do_clear_app(dev, args):
    dev.clear_app(args.package)
    print(f'Cleared: {args.package}')

def run_flow(dev, flow_path: str):
    """Run a JSON flow file."""
    with open(flow_path) as f:
        steps = json.load(f)

    print(f'Running flow: {flow_path} ({len(steps)} steps)')
    results = []

    for i, step in enumerate(steps):
        action = step.get('action')
        print(f'  [{i+1}/{len(steps)}] {action}: {step}')

        if action == 'wait':
            time.sleep(float(step.get('seconds', 1)))
        elif action == 'dump':
            path = do_dump(dev, argparse.Namespace(output=step.get('output')))
            results.append({'action': 'dump', 'path': path})
        elif action == 'screenshot':
            path = step.get('output', '/tmp/android_screen.png')
            do_screenshot(dev, argparse.Namespace(output=path))
            results.append({'action': 'screenshot', 'path': path})
        elif action == 'tap-text':
            path = dev.dump_ui('/tmp/ui_flow.xml')
            elements = android_ui.parse_ui(path)
            results_list = android_ui.find_by_text(elements, step['text'])
            if not results_list:
                results_list = android_ui.find_by_content_desc(elements, step['text'])
            if results_list:
                e = results_list[0]
                cx, cy = e.center()
                dev.tap(cx, cy)
                print(f'  Tapped: "{e.text or e.content_desc}" at ({cx},{cy})')
            time.sleep(float(step.get('wait', 2)))
        elif action == 'tap-coords':
            dev.tap(int(step['x']), int(step['y']))
            time.sleep(float(step.get('wait', 2)))
        elif action == 'type':
            field_text = step.get('field', '')
            if field_text:
                path = dev.dump_ui('/tmp/ui_flow.xml')
                elements = android_ui.parse_ui(path)
                field_elems = android_ui.find_by_text(elements, field_text)
                if field_elems:
                    cx, cy = field_elems[0].center()
                    dev.tap(cx, cy)
                    time.sleep(0.5)
            dev.type_text(step['text'])
            time.sleep(float(step.get('wait', 1)))
        elif action == 'swipe':
            do_swipe(dev, argparse.Namespace(dir=step.get('dir', 'up')))
            time.sleep(float(step.get('wait', 2)))
        elif action == 'verify':
            do_verify(dev, argparse.Namespace(text=step['text'], timeout=step.get('timeout', 5)))
        elif action == 'start':
            do_start(dev, argparse.Namespace(pkg=step['package']))
            time.sleep(float(step.get('wait', 3)))
        else:
            print(f'  Unknown action: {action}, skipping')

    update_state(action='flow_complete', flow=flow_path, steps=len(steps), results=results)
    print(f'Flow complete: {len(steps)} steps')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Android automation runner')
    sub = parser.add_subparsers(dest='task')

    explore_parser = sub.add_parser('explore')
    explore_parser.add_argument('-t', '--text', help='Filter by text')
    explore_parser.add_argument('-c', '--clickable', action='store_true', help='Show clickable only')

    tap_text = sub.add_parser('tap-text', help='Tap element by text')
    tap_text.add_argument('text', help='Text or content-desc to find and tap')

    tap_coords = sub.add_parser('tap-coords', help='Tap at coordinates')
    tap_coords.add_argument('x', help='X coordinate')
    tap_coords.add_argument('y', help='Y coordinate')

    swipe_parser = sub.add_parser('swipe', help='Swipe direction')
    swipe_parser.add_argument('dir', help='up/down/left/right')

    install_parser = sub.add_parser('install', help='Install APK')
    install_parser.add_argument('apk', help='Path to APK')
    install_parser.add_argument('-p', '--package', help='Package name (optional)')

    start_parser = sub.add_parser('start', help='Start app')
    start_parser.add_argument('pkg', help='Package or package/activity')

    verify_parser = sub.add_parser('verify', help='Verify text on screen')
    verify_parser.add_argument('text', help='Text to find')
    verify_parser.add_argument('-T', '--timeout', default='5', help='Seconds to wait')

    wait_parser = sub.add_parser('wait', help='Wait N seconds')
    wait_parser.add_argument('seconds', default='2', help='Seconds to wait')

    dump_parser = sub.add_parser('dump', help='Dump UI to file')
    dump_parser.add_argument('-o', '--output', help='Output path')

    screenshot_parser = sub.add_parser('screenshot', help='Capture screenshot')
    screenshot_parser.add_argument('-o', '--output', help='Output path')

    clear_parser = sub.add_parser('clear', help='Clear app data')
    clear_parser.add_argument('package', help='Package name')

    flow_parser = sub.add_parser('flow', help='Run JSON flow file')
    flow_parser.add_argument('file', help='Path to JSON flow file')

    args = parser.parse_args()

    if not args.task:
        parser.print_help()
        sys.exit(1)

    try:
        dev = adb.AndroidDevice()
        print(f'Device: {dev.serial}')
    except RuntimeError as e:
        print(f'ERROR: {e}')
        sys.exit(1)

    if args.task == 'explore':
        do_explore(dev, args)
    elif args.task == 'tap-text':
        do_tap_text(dev, args)
    elif args.task == 'tap-coords':
        do_tap_coords(dev, args)
    elif args.task == 'swipe':
        do_swipe(dev, args)
    elif args.task == 'install':
        do_install(dev, args)
    elif args.task == 'start':
        do_start(dev, args)
    elif args.task == 'verify':
        do_verify(dev, args)
    elif args.task == 'wait':
        do_wait(dev, args)
    elif args.task == 'dump':
        do_dump(dev, args)
    elif args.task == 'screenshot':
        do_screenshot(dev, args)
    elif args.task == 'clear':
        do_clear_app(dev, args)
    elif args.task == 'flow':
        run_flow(dev, args.file)
