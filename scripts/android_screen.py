#!/usr/bin/env python3
"""android_screen.py — Screenshot capture with optional diff."""
import sys, os, hashlib, time
sys.path.insert(0, os.path.dirname(__file__))
import android_controller as adb

DEFAULT_OUTPUT = '/tmp/android_screen.png'
STATE_FILE = '/tmp/android-automation-state.json'

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Capture Android screenshot')
    parser.add_argument('-o', '--output', default=DEFAULT_OUTPUT, help='Output path')
    parser.add_argument('--compare', help='Compare with baseline image path')
    parser.add_argument('--save-state', action='store_true', help='Update state file')
    args = parser.parse_args()

    path = adb.screenshot(args.output)
    size = os.path.getsize(path)
    md5 = hashlib.md5(open(path, 'rb').read()).hexdigest()
    print(f'Screenshot: {path}  ({size} bytes, md5={md5})')

    if args.compare and os.path.exists(args.compare):
        baseline = open(args.compare, 'rb').read()
        current = open(path, 'rb').read()
        if baseline != current:
            print('SCREEN CHANGED')
            if args.save_state:
                state = {'screenshot': path, 'changed': True, 'baseline': args.compare, 'timestamp': time.time()}
                with open(STATE_FILE, 'w') as f:
                    import json; json.dump(state, f, indent=2)
            sys.exit(1)
        else:
            print('SCREEN UNCHANGED')
            sys.exit(0)

    if args.save_state:
        state = {'screenshot': path, 'md5': md5, 'timestamp': time.time()}
        with open(STATE_FILE, 'w') as f:
            import json; json.dump(state, f, indent=2)

    sys.exit(0)
