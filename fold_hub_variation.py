#!/usr/bin/env python3
"""
fold_hub_variation.py

On the four realm hub pages (freestyle/index.html, freeride/index.html,
powder/index.html, carving/index.html) each trick row currently shows:

    [badge]  Manual        Nose        Flat
             ^name         ^variation  ^terrain
                           (trick-row__category, ~22% filled)

The "variation" column is sparse (mostly "—") and, worse, out of sync
with the trick's own page, which already folds it into the title
(e.g. manual-nose.html's <h1> reads "Manual — Nose"). This script
folds it the same way on the hub rows -- "Manual — Nose" -- and drops
the now-empty column entirely, leaving [badge] name — variation | terrain.

Rows with no variation ("—") are left as a plain name -- nothing folds
onto them.

Safe to re-run: rows that no longer have a trick-row__category span are
left untouched.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent
HUB_FILES = [
    "freestyle/index.html",
    "freeride/index.html",
    "powder/index.html",
    "carving/index.html",
]

ROW_RE = re.compile(
    r'(?P<indent>[ \t]*)<a class="trick-row" href="(?P<href>[^"]+)" role="listitem">\s*\n'
    r'[ \t]*(?P<badge><span class="badge"[^>]*></span>)\s*\n'
    r'[ \t]*<span class="trick-row__name">(?P<name>[^<]*)</span>\s*\n'
    r'[ \t]*<span class="trick-row__category">(?P<variation>[^<]*)</span>\s*\n'
    r'[ \t]*<span class="trick-row__realm">(?P<terrain>[^<]*)</span>\s*\n'
    r'[ \t]*</a>'
)

TABLE_RE = re.compile(r'<div class="trick-table"( role="list")?>')


def fold_row(m):
    indent = m.group("indent")
    inner = indent + "  "
    name = m.group("name")
    variation = m.group("variation").strip()
    terrain = m.group("terrain")
    folded_name = f"{name} — {variation}" if variation and variation != "—" else name

    return (
        f'{indent}<a class="trick-row" href="{m.group("href")}" role="listitem">\n'
        f'{inner}{m.group("badge")}\n'
        f'{inner}<span class="trick-row__name">{folded_name}</span>\n'
        f'{inner}<span class="trick-row__realm">{terrain}</span>\n'
        f'{indent}</a>'
    )


def process(path: Path):
    html = path.read_text(encoding="utf-8")
    original = html

    html, n_rows = ROW_RE.subn(fold_row, html)
    html = TABLE_RE.sub(
        lambda m: '<div class="trick-table trick-table--3col"' + (m.group(1) or "") + ">",
        html,
    )

    if html != original:
        path.write_text(html, encoding="utf-8")
    return n_rows


def main():
    for rel in HUB_FILES:
        path = ROOT / rel
        n = process(path)
        print(f"{rel}: folded {n} rows")


if __name__ == "__main__":
    main()
