#!/usr/bin/env python3
"""
build_table.py

Replaces the per-category <details> accordion on each hub page
(freestyle/freeride/powder/carving/drills index.html) with a single
always-visible <table> plus a row of toggle chips (one per category,
all active by default) that filter which rows show. No more "expand
the category, then click the trick" -- one click gets you to a page,
and toggling categories off narrows the list instead of hiding it
behind a second click.

Columns: [difficulty badge] | Name | (Level/Variation, if the rows have
one) | Category | Terrain.  Hubs with only one category (freeride,
powder, carving) get no chip row and no Category column, since every
row would say the same thing.

Self-contained: the script also writes assets/css/hub-table.css and
assets/js/hub-table.js (the styling + chip/row-click behaviour the new
table needs) and links them from each hub page, so you don't have to
touch main.css or main.js. Commit those two new files along with the hubs.

Counts: every run also recounts the rows in each hub's table and rewrites the
numbers that are derived from them -- the "Realm - N Tricks" eyebrow, the meta
description, the per-category chip counts, and on the home page the realm
cards, the "By the Numbers" rows and the Total. So after you add or delete
tricks, just re-run this script and everything agrees.

Re-running: converting the accordion is a one-way trip, so a hub that is
already a table is reported as "already converted" and its table is left
alone (asset links and counts are still refreshed). The two asset files are
rewritten every run. To rebuild a hub's table, restore its accordion version
from git first.

Needs: pip install beautifulsoup4
"""
import html
import re
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent

# (file, item noun used in the empty-state text)
HUB_FILES = [
    ("freestyle/index.html", "tricks"),
    ("freeride/index.html", "tricks"),
    ("powder/index.html", "tricks"),
    ("carving/index.html", "tricks"),
    ("drills/index.html", "drills"),
]

STEPS_BLOCK_RE = re.compile(
    r'(?P<indent>[ \t]*)<div class="steps" role="list">\n'
    r'(?P<body>.*?)\n'
    r'(?P=indent)</div>\n',
    re.DOTALL,
)


CSS_PATH = ROOT / "assets/css/hub-table.css"
JS_PATH = ROOT / "assets/js/hub-table.js"

HUB_CSS = r'''/* hub-table.css -- written by build_table.py (re-running the script regenerates it).
   Styles the category filter chips + table on the realm/drills hub pages.
   Every var() has a fallback so this still looks right if a token is missing. */

/* main.css sets overflow-x:hidden on <html> AND <body>. That makes <body> a scroll
   container, which silently disables every position:sticky (the nav and the table
   header below). 'clip' crops the same way without doing that. Browsers that don't
   know 'clip' ignore this line and keep 'hidden'. */
html, body { overflow-x: clip; }

/* visually hidden, still read by screen readers */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* ─── filter chips ─── */
.hub-filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}
.hub-filter__chip {
  font-family: var(--font-mono, 'DM Mono', monospace);
  font-size: 11px;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--muted, #6B6B65);
  background: transparent;
  border: 1px solid var(--border, #242424);
  padding: 6px 10px;
  cursor: pointer;
  transition: color 0.12s, border-color 0.12s, background 0.12s;
}
.hub-filter__chip.is-active {
  color: var(--text, #EAEAE4);
  background: var(--surface-up, #181818);
  border-color: var(--border-up, #303030);
}
.hub-filter__chip:hover { border-color: var(--border-up, #303030); }
.hub-filter__count { color: var(--muted, #6B6B65); margin-left: 5px; }
.hub-filter__reset {
  font-family: var(--font-mono, 'DM Mono', monospace);
  font-size: 11px;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--muted, #6B6B65);
  background: none;
  border: none;
  margin-left: auto;
  padding: 6px 4px;
  cursor: pointer;
}
.hub-filter__reset:hover { color: var(--text, #EAEAE4); }

/* ─── table ─── */
/* overflow must be 'visible' on the wrapper: overflow-x:auto would make it a scroll
   container and stop the sticky header from tracking the page (it would pin inside
   the wrapper and cover the first row). Set explicitly because older versions of
   main.css put overflow-x:auto here. Narrow screens hide the meta columns instead
   (see the media query at the bottom). */
.hub-table-wrap { border: 1px solid var(--border, #242424); overflow: visible; }
.hub-table { width: 100%; border-collapse: collapse; }
.hub-table thead th {
  position: sticky;
  top: 44px; /* height of the sticky site nav */
  z-index: 5;
  background: var(--surface, #111111);
  text-align: left;
  font-family: var(--font-mono, 'DM Mono', monospace);
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted, #6B6B65);
  padding: 9px 14px;
  border-bottom: 1px solid var(--border-up, #303030);
  white-space: nowrap;
}
.hub-table th.hub-table__col--badge { width: 40px; }
.hub-table td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--border, #242424);
  vertical-align: middle;
}
.hub-table tbody tr { cursor: pointer; transition: background 0.1s; }
.hub-table tbody tr:hover { background: var(--surface, #111111); }
.hub-table tbody tr:last-child td { border-bottom: none; }
.hub-table__name-link {
  font-family: var(--font-display, 'Barlow Condensed', sans-serif);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--text, #EAEAE4);
  text-decoration: none;
}
.hub-table__name-link:hover { text-decoration: underline; }
.hub-table__meta {
  font-family: var(--font-mono, 'DM Mono', monospace);
  font-size: 11px;
  color: var(--muted, #6B6B65);
  white-space: nowrap;
}
.hub-table__empty {
  padding: 32px 14px;
  text-align: center;
  font-family: var(--font-mono, 'DM Mono', monospace);
  font-size: 12px;
  color: var(--muted, #6B6B65);
}

@media (max-width: 900px) {
  .hub-table thead th.hub-table__col--meta,
  .hub-table td.hub-table__col--meta { display: none; }
  .hub-filter__reset { margin-left: 0; width: 100%; order: 99; text-align: center; }
}
'''

HUB_JS = r'''// hub-table.js -- written by build_table.py (re-running the script regenerates it).
// Category filter chips + click-anywhere-in-row navigation for the hub tables.
(function () {
  function initHubFilterTables() {
    document.querySelectorAll('[data-hub-table]').forEach(function (table) {
      var filterId = table.getAttribute('data-hub-table')
      var filterBar = document.querySelector('[data-hub-filter="' + filterId + '"]')
      var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr[data-category]'))
      var emptyRow = table.querySelector('.hub-table__empty-row')

      // Click anywhere in a row (the link itself already navigates on its own).
      rows.forEach(function (row) {
        var link = row.querySelector('a')
        if (!link) return
        row.addEventListener('click', function (e) {
          if (e.target.closest('a')) return
          window.location.href = link.getAttribute('href')
        })
      })

      if (!filterBar) return // single-category hubs have no chips

      var chips = Array.prototype.slice.call(filterBar.querySelectorAll('.hub-filter__chip'))
      var resetBtn = filterBar.querySelector('.hub-filter__reset')

      function applyFilter() {
        var active = {}
        chips.forEach(function (c) {
          var on = c.classList.contains('is-active')
          c.setAttribute('aria-pressed', String(on)) // keep screen readers in step
          if (on) active[c.getAttribute('data-category')] = true
        })
        var visible = 0
        rows.forEach(function (row) {
          var show = !!active[row.getAttribute('data-category')]
          row.style.display = show ? '' : 'none'
          if (show) visible += 1
        })
        if (emptyRow) emptyRow.style.display = visible === 0 ? '' : 'none'
      }

      chips.forEach(function (chip) {
        chip.addEventListener('click', function () {
          chip.classList.toggle('is-active')
          applyFilter()
        })
      })

      if (resetBtn) {
        resetBtn.addEventListener('click', function () {
          chips.forEach(function (c) { c.classList.add('is-active') })
          applyFilter()
        })
      }

      applyFilter()
    })
  }

  // If main.js already defines initHubFilterTables (it calls it on DOMContentLoaded),
  // swap in this version so the chips aren't wired up twice. Otherwise run it ourselves.
  if (typeof window.initHubFilterTables === 'function') {
    window.initHubFilterTables = initHubFilterTables
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHubFilterTables)
  } else {
    initHubFilterTables()
  }
})()
'''

CSS_ANCHOR_RE = re.compile(r'^([ \t]*)<link[^>]*href="([^"]*?)assets/css/main\.css"[^>]*>[ \t]*\n', re.M)
JS_ANCHOR_RE = re.compile(r'^([ \t]*)<script[^>]*src="([^"]*?)assets/js/main\.js"[^>]*></script>[ \t]*\n', re.M)


def write_assets():
    for path, content in ((CSS_PATH, HUB_CSS), (JS_PATH, HUB_JS)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path.relative_to(ROOT)}")


def ensure_links(text):
    """Add <link>/<script> tags for the two asset files right after main.css /
    main.js if the page doesn't reference them yet. Returns (new_text, [what was added])."""
    added = []
    if "hub-table.css" not in text:
        m = CSS_ANCHOR_RE.search(text)
        if m:
            tag = f'{m.group(1)}<link rel="stylesheet" href="{m.group(2)}assets/css/hub-table.css">\n'
            text = text[: m.end()] + tag + text[m.end():]
            added.append("css")
    if "hub-table.js" not in text:
        m = JS_ANCHOR_RE.search(text)
        if m:
            tag = f'{m.group(1)}<script src="{m.group(2)}assets/js/hub-table.js"></script>\n'
            text = text[: m.end()] + tag + text[m.end():]
            added.append("js")
    return text, added


def esc(s):
    return html.escape(s or "", quote=True)


def slugify(text):
    text = text.lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def extract_groups(steps_body):
    """Parse the <details> blocks in the old accordion into a list of
    {category, rows: [{href, diff, diff_label, name, extra_meta, terrain}]}."""
    soup = BeautifulSoup(steps_body, "html.parser")
    groups = []
    for details in soup.select("details.step"):
        title_el = details.select_one(".step__title")
        title_text = title_el.get_text(strip=True) if title_el else "Other"
        category = re.sub(r"\s*—\s*\d+\s+\w+$", "", title_text).strip()

        rows = []
        for a in details.select("a.trick-row"):
            badge = a.select_one(".badge[data-difficulty]")
            diff = badge.get("data-difficulty") if badge else "green"
            diff_label = badge.get("aria-label") if badge else ""
            name_el = a.select_one(".trick-row__name")
            name = name_el.get_text(strip=True) if name_el else ""

            # Trick hubs (post-fold): just .trick-row__realm (terrain).
            # Drills hub: .trick-row__category (level text) AND
            # .trick-row__realm (terrain) both still present.
            cat_el = a.select_one(".trick-row__category")
            realm_el = a.select_one(".trick-row__realm")
            extra = cat_el.get_text(strip=True) if cat_el else None
            terrain = realm_el.get_text(strip=True) if realm_el else "—"

            rows.append({
                "href": a.get("href"),
                "diff": diff,
                "diff_label": diff_label,
                "name": name,
                "extra": extra,
                "terrain": terrain,
            })
        groups.append({"category": category, "rows": rows})
    return groups


def build_markup(groups, table_id, noun, has_extra_col, extra_col_label):
    total = sum(len(g["rows"]) for g in groups)
    multi_category = len(groups) > 1

    filter_html = ""
    if multi_category:
        chips = []
        for g in groups:
            cat_slug = esc(g["category"])
            chips.append(
                f'          <button type="button" class="hub-filter__chip is-active" '
                f'data-category="{cat_slug}" aria-pressed="true">{esc(g["category"])}'
                f'<span class="hub-filter__count">{len(g["rows"])}</span></button>'
            )
        chips_html = "\n".join(chips)
        filter_html = (
            f'      <div class="hub-filter" data-hub-filter="{table_id}" role="group" aria-label="Filter by category">\n'
            f'{chips_html}\n'
            f'          <button type="button" class="hub-filter__reset">Show all</button>\n'
            f'      </div>\n\n'
        )

    extra_th = f'\n            <th scope="col" class="hub-table__col--meta">{esc(extra_col_label)}</th>' if has_extra_col else ""
    category_th = '            <th scope="col" class="hub-table__col--meta">Category</th>\n' if multi_category else ""
    header = (
        '      <div class="hub-table-wrap">\n'
        f'        <table class="hub-table" data-hub-table="{table_id}">\n'
        '          <thead>\n'
        '            <tr>\n'
        '            <th scope="col" class="hub-table__col--badge"><span class="sr-only">Difficulty</span></th>\n'
        '            <th scope="col">Name</th>'
        f'{extra_th}\n'
        f'{category_th}'
        '            <th scope="col" class="hub-table__col--meta">Terrain</th>\n'
        '            </tr>\n'
        '          </thead>\n'
        '          <tbody>\n'
    )

    rows_html = []
    for g in groups:
        cat = esc(g["category"])
        for r in g["rows"]:
            extra_td = f'\n            <td class="hub-table__col--meta hub-table__meta">{esc(r["extra"])}</td>' if has_extra_col else ""
            category_td = f'            <td class="hub-table__col--meta hub-table__meta">{cat}</td>\n' if multi_category else ""
            rows_html.append(
                '            <tr data-category="' + cat + '">\n'
                f'            <td><span class="badge" data-difficulty="{r["diff"]}" data-size="14" aria-label="{esc(r["diff_label"])}"></span></td>\n'
                f'            <td><a class="hub-table__name-link" href="{esc(r["href"])}">{esc(r["name"])}</a></td>'
                f'{extra_td}\n'
                f'{category_td}'
                f'            <td class="hub-table__col--meta hub-table__meta">{esc(r["terrain"])}</td>\n'
                '            </tr>'
            )

    colspan = 3 + int(has_extra_col) + int(multi_category)  # badge, name, terrain (+ level, + category)
    empty_row = (
        f'            <tr class="hub-table__empty-row" style="display:none">\n'
        f'            <td colspan="{colspan}" class="hub-table__empty">No {esc(noun)} match the selected categories.</td>\n'
        '            </tr>\n'
    )

    footer = '          </tbody>\n        </table>\n      </div>\n'

    body = filter_html + header + "\n".join(rows_html) + "\n" + empty_row + footer
    return total, body


HOME_FILE = "index.html"


def update_counts(text):
    """Recount the table rows on a hub page and rewrite every number derived from
    them. Returns (new_text, total_rows)."""
    cats = re.findall(r'<tr data-category="([^"]*)"', text)
    total, n_cats = len(cats), len(set(cats))
    per_cat = Counter(cats)
    meta = r'(<meta name="description" content="[^"]*?'

    # eyebrow: "Realm · 245 Tricks" / "AASI Drill Reference · 69 Drills"
    text = re.sub(r'(<p class="essentials-eyebrow">[^<]*?)\b\d+(\s+(?:Tricks|Drills)\s*</p>)',
                  lambda m: f"{m.group(1)}{total}{m.group(2)}", text, count=1, flags=re.I)
    # meta description: "... — 245 tricks across 8 categories." / "... 69 drills across 8 groups."
    text = re.sub(meta + r')\b\d+(\s+(?:tricks|drills)\b)',
                  lambda m: f"{m.group(1)}{total}{m.group(2)}", text, count=1)
    text = re.sub(meta + r'\bacross\s+)\d+(\s+(?:categories|groups)\b)',
                  lambda m: f"{m.group(1)}{n_cats}{m.group(2)}", text, count=1)
    # per-category chip counts
    text = re.sub(r'(data-category="([^"]*)"[^>]*>[^<]*<span class="hub-filter__count">)\d+(</span>)',
                  lambda m: f"{m.group(1)}{per_cat.get(m.group(2), 0)}{m.group(3)}", text)
    return text, total


def update_home(counts):
    """counts: {"freestyle": 245, ..., "drills": 69}. Refreshes the realm cards,
    the By-the-Numbers rows and the Total on the home page."""
    path = ROOT / HOME_FILE
    if not path.exists():
        return
    text = orig = path.read_text(encoding="utf-8")
    for slug, n in counts.items():
        noun = "drills" if slug == "drills" else "tricks"
        card = rf'(<a class="realm-card" href="{slug}/index\.html">(?:(?!</a>).)*?<p class="realm-card__count">)\d+(\s+{noun}\b)'
        text = re.sub(card, lambda m: f"{m.group(1)}{n}{m.group(2)}", text, count=1, flags=re.S)
        row = rf'(<a href="{slug}/index\.html">)\d+(\s+{noun}</a>)'
        text = re.sub(row, lambda m: f"{m.group(1)}{n}{m.group(2)}", text, count=1)
    if len(counts) == len(HUB_FILES):
        total = sum(counts.values())
        text = re.sub(r'(<div class="meta-row__label">Total</div>\s*<div class="meta-row__value">)\d+(\s+entries)',
                      lambda m: f"{m.group(1)}{total}{m.group(2)}", text, count=1)
        note = f"Total {total}"
    else:
        note = "Total left alone (not every hub was counted)"
    if text != orig:
        path.write_text(text, encoding="utf-8")
        print(f"  {HOME_FILE}: counts updated ({note})")
    else:
        print(f"  {HOME_FILE}: counts already up to date ({note})")


def process(rel_path, noun):
    path = ROOT / rel_path
    text = path.read_text(encoding="utf-8")

    m = STEPS_BLOCK_RE.search(text)
    if m:
        groups = extract_groups(m.group("body"))
        has_extra_col = any(r["extra"] is not None for g in groups for r in g["rows"])
        extra_col_label = "Level" if noun == "drills" else "Variation"
        table_id = slugify(rel_path.split("/")[0]) or "hub"

        total, new_body = build_markup(groups, table_id, noun, has_extra_col, extra_col_label)
        new_text = text[: m.start()] + new_body + text[m.end():]  # new_body carries its own indentation
        status = f"{len(groups)} categories, {total} {noun}"
    elif "data-hub-table=" in text:
        new_text, status = text, "already converted"
    else:
        print(f"  ! could not find <div class=\"steps\"> block in {rel_path}, skipping")
        return None

    before_counts = new_text
    new_text, total_rows = update_counts(new_text)
    if new_text != before_counts:
        status += ", counts refreshed"

    new_text, added = ensure_links(new_text)
    if added:
        status += f" (linked hub-table {' + '.join(added)})"
    elif "hub-table.css" not in new_text or "hub-table.js" not in new_text:
        status += " (! couldn't find the main.css / main.js tags to link the assets after)"

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    print(f"  {rel_path}: {status}")
    return total_rows


def main():
    print("Rebuilding hub tables:")
    write_assets()
    counts = {}
    for rel_path, noun in HUB_FILES:
        n = process(rel_path, noun)
        if n is not None:
            counts[rel_path.split("/")[0]] = n
    update_home(counts)


if __name__ == "__main__":
    main()