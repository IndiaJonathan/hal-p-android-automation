#!/usr/bin/env python3
"""android_ui.py — Parse Android UI dump XML, find elements by various criteria."""
import sys, re, xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

@dataclass
class UIElement:
    text: str
    content_desc: str
    bounds: str  # "[x1,y1][x2,y2]"
    clickable: bool
    class_name: str
    resource_id: str

    def center(self) -> tuple[int, int]:
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', self.bounds)
        if not m:
            return (0, 0)
        return ((int(m.group(1)) + int(m.group(3))) // 2,
                (int(m.group(2)) + int(m.group(4))) // 2)

    def __repr__(self):
        c = self.center()
        return '"%s" tap=(%s,%s) %s [%s]' % (self.text or self.content_desc, c[0], c[1], self.bounds, self.class_name)


def parse_ui(xml_path: str) -> list[UIElement]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    elements = []

    for node in root.iter('node'):
        text = node.get('text', '')
        desc = node.get('content-desc', '')
        bounds = node.get('bounds', '')
        clickable = node.get('clickable', 'false') == 'true'
        class_name = node.get('class', '')
        resource_id = node.get('resource-id', '')

        if bounds:
            elements.append(UIElement(
                text=text, content_desc=desc, bounds=bounds,
                clickable=clickable, class_name=class_name, resource_id=resource_id
            ))

    return elements


def find_by_text(elements: list[UIElement], text: str, exact: bool = False) -> list[UIElement]:
    if exact:
        return [e for e in elements if e.text == text]
    return [e for e in elements if text.lower() in e.text.lower()]


def find_by_content_desc(elements: list[UIElement], desc: str) -> list[UIElement]:
    return [e for e in elements if desc.lower() in e.content_desc.lower()]


def find_clickable(elements: list[UIElement]) -> list[UIElement]:
    return [e for e in elements if e.clickable]


def find_by_bounds(elements: list[UIElement], bounds: str) -> list[UIElement]:
    return [e for e in elements if e.bounds == bounds]


def all_texts(elements: list[UIElement]) -> list[str]:
    return [(e.text or e.content_desc, e.bounds, e.clickable)
            for e in elements if e.text.strip() or e.content_desc.strip()]


def print_elements(elements: list[UIElement], clickable_only: bool = False):
    for e in elements:
        if clickable_only and not e.clickable:
            continue
        c = e.center()
        label = e.text or e.content_desc or '(no label)'
        print(f'  Tap({c[0]},{c[1]}) | "{label}" | {e.bounds} | clickable={e.clickable}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Android UI dump parser')
    parser.add_argument('xml', help='Path to UI dump XML file')
    parser.add_argument('--find', '-f', help='Text to search for')
    parser.add_argument('--clickable', '-c', action='store_true', help='Show only clickable')
    parser.add_argument('--all', '-a', action='store_true', help='Show all texts')
    args = parser.parse_args()

    elements = parse_ui(args.xml)

    if args.all:
        for t, b, click in all_texts(elements):
            print(f'  "{t}" | {b} | clickable={click}')
    elif args.clickable:
        print_elements(elements, clickable_only=True)
    elif args.find:
        results = find_by_text(elements, args.find)
        if not results:
            results = find_by_content_desc(elements, args.find)
        if results:
            for e in results:
                print(e)
        else:
            print(f'No element found matching: {args.find}')
            sys.exit(1)
    else:
        print_elements(elements)

    sys.exit(0)
