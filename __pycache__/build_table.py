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

Needs the .hub-filter / .hub-table / .sr-only rules in assets/css/main.css
and initHubFilterTables() in assets/js/main.js.

Re-running: this converts the accordion, so once a hub has been converted
there is no accordion left to read; that file is reported as "already
converted" and left untouched. To rebuild a hub, restore its accordion
version from git first.
"""
import html
import re
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


def process(rel_path, noun):
    path = ROOT / rel_path
    text = path.read_text(encoding="utf-8")

    m = STEPS_BLOCK_RE.search(text)
    if not m:
        if "data-hub-table=" in text:
            print(f"  {rel_path}: already converted, skipping")
        else:
            print(f"  ! could not find <div class=\"steps\"> block in {rel_path}, skipping")
        return

    groups = extract_groups(m.group("body"))
    has_extra_col = any(r["extra"] not in (None,) for g in groups for r in g["rows"])
    extra_col_label = "Level" if noun == "drills" else "Variation"
    table_id = slugify(rel_path.split("/")[0]) or "hub"

    total, new_body = build_markup(groups, table_id, noun, has_extra_col, extra_col_label)

    new_text = text[: m.start()] + new_body + text[m.end():]  # new_body carries its own indentation
    path.write_text(new_text, encoding="utf-8")
    print(f"  {rel_path}: {len(groups)} categories, {total} {noun}")


def main():
    print("Rebuilding hub tables:")
    for rel_path, noun in HUB_FILES:
        process(rel_path, noun)


if __name__ == "__main__":
    main()