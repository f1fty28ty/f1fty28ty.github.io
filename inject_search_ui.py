#!/usr/bin/env python3
"""
Inserts the nav search widget markup and the search-index.js <script> tag
into every HTML page on the site (hub pages included — the widget must be
usable from anywhere, it's only the *index of searchable pages* that skips
the hubs, which build_search_index.py already handles).

Safe to re-run: it skips any file that already has the widget.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent
EXCLUDE_DIRS = {".git"}

WIDGET_MARKUP = """        <div class="site-search" id="site-search">
          <div class="site-search__input-wrap">
            <svg class="site-search__icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.4"/>
              <line x1="11.2" y1="11.2" x2="15" y2="15" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
            <input class="site-search__input" type="text" placeholder="Search the compendium…" aria-label="Search the compendium" autocomplete="off" spellcheck="false">
            <button class="site-search__clear" type="button" aria-label="Clear search">&times;</button>
          </div>
          <div class="site-search__results" role="listbox" aria-label="Search results"></div>
        </div>
"""

NAV_ANCHOR_RE = re.compile(
    r"(</button>\s*\n)(\s*<ul class=\"site-nav__links\")"
)

MAIN_JS_RE = re.compile(
    r'([ \t]*)<script src="((?:\.\./)*)assets/js/main\.js"></script>'
)


def process(path: Path):
    html = path.read_text(encoding="utf-8")
    original = html

    if 'id="site-search"' not in html:
        html = NAV_ANCHOR_RE.sub(lambda m: m.group(1) + WIDGET_MARKUP + m.group(2), html, count=1)

    if "search-index.js" not in html:
        def add_index_script(m):
            indent, prefix = m.group(1), m.group(2)
            return f'{indent}<script src="{prefix}assets/js/search-index.js"></script>\n{indent}<script src="{prefix}assets/js/main.js"></script>'
        html = MAIN_JS_RE.sub(add_index_script, html, count=1)

    if html != original:
        path.write_text(html, encoding="utf-8")
        return True
    return False


def main():
    changed = 0
    total = 0
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        total += 1
        if process(path):
            changed += 1
    print(f"Updated {changed}/{total} HTML files")


if __name__ == "__main__":
    main()
