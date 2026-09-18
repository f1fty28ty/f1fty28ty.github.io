#!/usr/bin/env python3
"""
generate_trick_pages.py

Builds one HTML page per trick for The Snowboard Compendium, using
trick/backside-180.html as the structural template, pulling all data
from tricks.csv (an export of the "Tricks" sheet in
All_Snowboard_Tricks_Drills.xlsx).

Usage:
    python3 generate_trick_pages.py [--csv tricks.csv] [--site .] [--dry-run]

Run this from (or point --site at) the root of the Snowboard-Compendium
folder -- the folder that directly contains index.html, assets/,
freestyle/, carving/, powder/, freeride/, etc.

WHAT IT DOES
------------
For every row in tricks.csv it writes:
    {site}/{realm-slug}/tricks/{category-slug}/{trick-slug}.html

using the exact same slug rules the hub pages (freestyle/index.html,
carving/index.html, powder/index.html, freeride/index.html) were built
with, so every link already sitting in those hubs resolves to a real
file after this script runs.

Each page carries:
    - Realm / Category / Stance / Terrain meta rows
    - A difficulty badge from the Level column
    - Requires / Opens links, built from "Builds From" / "Leads To",
      auto-matched against every other trick in the sheet so they link
      to real pages wherever possible (falling back to plain text when
      a reference doesn't match a known trick, e.g. "Ollie" as a raw
      prerequisite skill rather than a trick row)
    - Tags built from Rotation / short Variation labels / Also Known As
    - An Overview section built from the Description column (and the
      Variation column when it's long-form, e.g. hand-placement detail
      for grabs, rather than a short label)

WHAT IT DOES NOT DO
--------------------
The spreadsheet has no coaching content (step-by-step breakdowns,
common-mistake fixes), so this script does NOT invent any. Generated
pages get a single "Overview" entry instead of the six-step breakdown
you wrote by hand for Backside 180, and skip the Coach's Corner block
entirely. Fill those in by hand later, page by page, the same way
backside-180.html was written -- this script just gets every trick to
a real, linked, correctly-structured page first.

Re-run any time tricks.csv changes; it always overwrites in place.
"""

import argparse
import csv
import html
import os
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# Realm / category mapping -- must match the hub-page generator exactly,
# or slugs (and therefore links) will drift out of sync with the hubs.
# ---------------------------------------------------------------------------

REALM_BY_CATEGORY = {
    "Carving": ("Carving", "carving"),
    "Powder": ("Powder", "powder"),
    "Freeride / Natural Terrain": ("Freeride", "freeride"),
}
DEFAULT_REALM = ("Freestyle", "freestyle")

CAT_SLUG = {
    "Flatground": "flatground",
    "Jumps": "jumps",
    "Grabs": "grabs",
    "Rails / Boxes": "rails-boxes",
    "Pipe / Transition": "pipe-transition",
    "Off-Axis Spins": "off-axis-spins",
    "Flips / Inverted": "flips-inverted",
    "Features / Transition": "features-transition",
    "Carving": "carving",
    "Powder": "powder",
    "Freeride / Natural Terrain": "freeride",
}
CAT_DISPLAY = {
    "Flatground": "Flatground",
    "Jumps": "Jumps",
    "Grabs": "Grabs",
    "Rails / Boxes": "Rails & Boxes",
    "Pipe / Transition": "Pipe & Transition",
    "Off-Axis Spins": "Off-Axis Spins",
    "Flips / Inverted": "Flips & Inverted",
    "Features / Transition": "Features & Transition",
    "Carving": "Carving Technique",
    "Powder": "Powder Technique",
    "Freeride / Natural Terrain": "Freeride & Natural Terrain",
}

DIFF_SLUG = {"Green": "green", "Blue": "blue", "Black": "black", "Double Black": "dblack"}
DIFF_LABEL = {
    "green": "Green Circle",
    "blue": "Blue Square",
    "black": "Black Diamond",
    "dblack": "Double Black Diamond",
}

VARIATION_LABEL_MAX_LEN = 20  # short -> goes in the title; long -> becomes overview text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text):
    text = text.lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def esc(text):
    return html.escape(text or "", quote=True)


def read_tricks(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if not row.get("Category") or not row.get("Name"):
                continue
            row = {k: (v or "").strip() for k, v in row.items()}
            rows.append(row)
        return rows


def realm_for(category):
    return REALM_BY_CATEGORY.get(category, DEFAULT_REALM)


def trick_title(row):
    variation = row.get("Variation", "")
    if variation and len(variation) <= VARIATION_LABEL_MAX_LEN:
        return f'{row["Name"]} — {variation}'
    return row["Name"]


def build_index(rows):
    """
    Assign each row its final slug/realm/category using the exact same
    ordering + collision rule the hub generator used, then index every
    row by name (and name+variation) so Requires/Opens can be resolved
    to real pages.
    """
    by_category = defaultdict(list)
    for row in rows:
        by_category[row["Category"]].append(row)

    assigned = []  # list of dicts with slug/realm/etc, same order as rows won't matter
    name_index = {}  # lowercase key -> assigned record

    for category, cat_rows in by_category.items():
        cat_rows_sorted = sorted(
            cat_rows,
            key=lambda r: (float(r["Lvl #"] or 0), r["Name"], r.get("Variation", "")),
        )
        seen_slugs = set()
        for row in cat_rows_sorted:
            base = slugify(row["Name"] + (" " + row["Variation"] if row.get("Variation") else ""))
            slug, i = base, 2
            while slug in seen_slugs:
                slug = f"{base}-{i}"
                i += 1
            seen_slugs.add(slug)

            realm_title, realm_slug = realm_for(category)
            diff = DIFF_SLUG.get(row["Level"], "green")
            record = {
                "row": row,
                "category": category,
                "cat_slug": CAT_SLUG[category],
                "cat_display": CAT_DISPLAY[category],
                "realm_title": realm_title,
                "realm_slug": realm_slug,
                "slug": slug,
                "diff": diff,
                "title": trick_title(row),
            }
            assigned.append(record)

            # Index under a few keys so loose references in Builds
            # From / Leads To have a decent chance of matching.
            name_index.setdefault(row["Name"].lower(), record)
            if row.get("Variation"):
                combo = f'{row["Name"]} {row["Variation"]}'.lower()
                name_index.setdefault(combo, record)

    return assigned, name_index


def resolve_refs(text, name_index):
    """Split a Builds From / Leads To cell into individual (label, record|None) pairs."""
    if not text:
        return []
    parts = [p.strip() for p in text.split("/") if p.strip()]
    out = []
    for part in parts:
        rec = name_index.get(part.lower())
        out.append((part, rec))
    return out


def rel_path(record):
    """Path from this trick's own file up to site root, e.g. '../../../'."""
    return "../../../"


def rel_to_other_trick(record, other):
    """Link from `record`'s page to `other`'s page."""
    if other["realm_slug"] == record["realm_slug"]:
        return f'../{other["cat_slug"]}/{other["slug"]}.html'
    return f'../../../{other["realm_slug"]}/tricks/{other["cat_slug"]}/{other["slug"]}.html'


def meta_link_html(label, rec, record):
    if rec is None:
        return f'            <span class="meta-link meta-link--unlinked">{esc(label)}</span>'
    diff = rec["diff"]
    href = rel_to_other_trick(record, rec)
    return (
        f'            <a class="meta-link" href="{href}">\n'
        f'              <span class="badge" data-difficulty="{diff}" data-size="12" '
        f'aria-label="{DIFF_LABEL[diff]}"></span>\n'
        f'              {esc(rec["title"])}\n'
        f'            </a>'
    )


NAV_REALMS = [("Freestyle", "freestyle"), ("Freeride", "freeride"), ("Powder", "powder"), ("Carving", "carving")]


def nav_html(active_realm_slug, root):
    items = []
    for label, slug in NAV_REALMS:
        cur = ' aria-current="page"' if slug == active_realm_slug else ""
        items.append(f'          <li><a href="{root}{slug}/index.html"{cur}>{label}</a></li>')
    items.append(f'          <li><a href="{root}essentials/index.html">Essentials</a></li>')
    items.append(f'          <li><a href="{root}drills/index.html">Drills</a></li>')
    return "\n".join(items)


PAGE_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — The Snowboard Compendium</title>
  <meta name="description" content="{meta_desc}">
  <link rel="stylesheet" href="{root}assets/css/main.css">
</head>
<body>

  <!-- Site nav -->
  <nav class="site-nav" aria-label="Primary navigation">
    <div class="container">
      <div class="site-nav__inner">
        <a class="site-nav__logo" href="{root}index.html">The Snowboard Compendium</a>
        <button class="site-nav__toggle" aria-label="Menu" aria-expanded="false">
          <span class="site-nav__toggle-icon"></span>
        </button>
        <ul class="site-nav__links" role="list">
{nav}
        </ul>
      </div>
    </div>
  </nav>

  <!-- Breadcrumb -->
  <div class="breadcrumb" aria-label="Breadcrumb">
    <div class="breadcrumb__inner">
      <a class="breadcrumb__item" href="{root}index.html">Home</a>
      <span class="breadcrumb__sep">›</span>
      <a class="breadcrumb__item" href="{root}{realm_slug}/index.html">{realm_title}</a>
      <span class="breadcrumb__sep">›</span>
      <span class="breadcrumb__item">{cat_display}</span>
      <span class="breadcrumb__sep">›</span>
      <span class="breadcrumb__item breadcrumb__item--current">{title}</span>
    </div>
  </div>

  <!-- Progression rail -->
  <div class="progression-rail" aria-label="Trick progression">
    <div class="progression-rail__inner">
      <span class="progression-rail__label">PROGRESSION ›</span>
{prev_html}
      <div class="progression-rail__line">
        <span class="progression-rail__current">{title}</span>
      </div>
{next_html}
    </div>
  </div>

  <!-- Trick page content -->
  <main class="trick-page">
    <div class="container">
      <div class="trick-layout">

        <!-- Left metadata rail -->
        <aside class="meta-rail" aria-label="Trick metadata">
          <div class="meta-rail__badge">
            <span class="badge" data-difficulty="{diff}" data-size="32" data-label="true" aria-label="{diff_label} — difficulty"></span>
          </div>

          <div class="meta-row">
            <div class="meta-row__label">Realm</div>
            <div class="meta-row__value">{realm_title}</div>
          </div>
          <div class="meta-row">
            <div class="meta-row__label">Category</div>
            <div class="meta-row__value">{cat_display}</div>
          </div>
          <div class="meta-row">
            <div class="meta-row__label">Stance</div>
            <div class="meta-row__value">Regular &amp; Goofy</div>
          </div>
          <div class="meta-row">
            <div class="meta-row__label">Terrain</div>
            <div class="meta-row__value">{terrain}</div>
          </div>

          <div class="meta-section">
            <div class="meta-section__title">Requires</div>
{requires_html}
          </div>

          <div class="meta-section">
            <div class="meta-section__title">Opens</div>
{opens_html}
          </div>
        </aside>

        <!-- Main content -->
        <div>

          <h1 class="trick-title">{title}</h1>
          <div class="trick-tags">
{tags_html}
          </div>

          <!-- Video slots -->
          <div class="video-row">
            <div class="video-slot" role="button" tabindex="0" aria-label="Play regular stance reference video">
              <span class="video-slot__icon">▶</span>
              <span class="video-slot__label">Regular Stance</span>
            </div>
            <div class="video-slot" role="button" tabindex="0" aria-label="Play goofy stance reference video">
              <span class="video-slot__icon">▶</span>
              <span class="video-slot__label">Goofy Stance</span>
            </div>
          </div>

          <!-- Steps -->
          <p class="section-header">Step-by-Step Execution</p>
          <div class="steps" role="list">

            <details class="step" open role="listitem">
              <summary>
                <span class="step__num">01</span>
                <span class="step__title">Overview</span>
                <span class="step__toggle" aria-hidden="true">+</span>
              </summary>
              <div class="step__body">
                {overview}
              </div>
            </details>

          </div>
          <!-- TODO: replace the single Overview step above with a full
               step-by-step breakdown, the way trick/backside-180.html
               has one -- this script only pulls what's in the sheet. -->

        </div><!-- /main content -->
      </div><!-- /trick-layout -->
    </div>
  </main>

  <script src="{root}assets/js/main.js"></script>
</body>
</html>
"""


def build_page(record, name_index):
    row = record["row"]
    root = rel_path(record)

    requires = resolve_refs(row.get("Builds From", ""), name_index)
    opens = resolve_refs(row.get("Leads To", ""), name_index)

    requires_html = "\n".join(meta_link_html(l, r, record) for l, r in requires) or \
        '            <span class="meta-link meta-link--unlinked">—</span>'
    opens_html = "\n".join(meta_link_html(l, r, record) for l, r in opens) or \
        '            <span class="meta-link meta-link--unlinked">—</span>'

    # Progression rail: first "builds from" match as prev, first "leads to" match as next.
    prev_label, prev_rec = requires[0] if requires else (None, None)
    next_label, next_rec = opens[0] if opens else (None, None)

    if prev_rec:
        prev_html = (
            f'      <a class="progression-rail__prev" href="{rel_to_other_trick(record, prev_rec)}">\n'
            f'        <span class="badge" data-difficulty="{prev_rec["diff"]}" data-size="11" '
            f'aria-label="{DIFF_LABEL[prev_rec["diff"]]}"></span>\n'
            f'        <span>‹ {esc(prev_rec["title"])}</span>\n'
            f'      </a>'
        )
    elif prev_label:
        prev_html = f'      <span class="progression-rail__prev">\n        <span>‹ {esc(prev_label)}</span>\n      </span>'
    else:
        prev_html = '      <span class="progression-rail__prev"></span>'

    if next_rec:
        next_html = (
            f'      <a class="progression-rail__next" href="{rel_to_other_trick(record, next_rec)}">\n'
            f'        <span>{esc(next_rec["title"])} ›</span>\n'
            f'        <span class="badge" data-difficulty="{next_rec["diff"]}" data-size="11" '
            f'aria-label="{DIFF_LABEL[next_rec["diff"]]}"></span>\n'
            f'      </a>'
        )
    elif next_label:
        next_html = f'      <span class="progression-rail__next">\n        <span>{esc(next_label)} ›</span>\n      </span>'
    else:
        next_html = '      <span class="progression-rail__next"></span>'

    # Tags: short variation label, rotation, "AKA: ..."
    tags = []
    variation = row.get("Variation", "")
    if variation and len(variation) <= VARIATION_LABEL_MAX_LEN:
        tags.append(variation)
    if row.get("Rotation"):
        tags.append(row["Rotation"])
    if row.get("Also Known As"):
        tags.append(f'AKA: {row["Also Known As"]}')
    if not tags:
        tags.append(record["cat_display"])
    tags_html = "\n".join(f'            <span class="trick-tag">{esc(t)}</span>' for t in tags)

    # Overview text: Description, plus long-form Variation detail when present.
    overview_bits = []
    if variation and len(variation) > VARIATION_LABEL_MAX_LEN:
        overview_bits.append(f"<strong>Grip / detail:</strong> {esc(variation)}.")
    if row.get("Description"):
        overview_bits.append(esc(row["Description"]))
    if row.get("Review"):
        overview_bits.append(f'<em>{esc(row["Review"])}</em>')
    if not overview_bits:
        overview_bits.append("Full write-up coming soon.")
    overview = " ".join(overview_bits)

    diff = record["diff"]
    html_out = PAGE_TMPL.format(
        title=esc(record["title"]),
        meta_desc=esc(f'{record["title"]} — {DIFF_LABEL[diff]}. {record["realm_title"]} {record["cat_display"]} trick.'),
        root=root,
        nav=nav_html(record["realm_slug"], root),
        realm_slug=record["realm_slug"],
        realm_title=esc(record["realm_title"]),
        cat_display=esc(record["cat_display"]),
        prev_html=prev_html,
        next_html=next_html,
        diff=diff,
        diff_label=DIFF_LABEL[diff],
        terrain=esc(row.get("Terrain / Feature") or "—"),
        requires_html=requires_html,
        opens_html=opens_html,
        tags_html=tags_html,
        overview=overview,
    )
    return html_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="tricks.csv", help="Path to tricks.csv")
    ap.add_argument("--site", default=".", help="Path to the site root (contains index.html, assets/, etc.)")
    ap.add_argument("--dry-run", action="store_true", help="Report what would be written without writing files")
    args = ap.parse_args()

    rows = read_tricks(args.csv)
    if not rows:
        print(f"No rows found in {args.csv}", file=sys.stderr)
        sys.exit(1)

    assigned, name_index = build_index(rows)

    written = 0
    for record in assigned:
        page_html = build_page(record, name_index)
        out_path = os.path.join(
            args.site, record["realm_slug"], "tricks", record["cat_slug"], f'{record["slug"]}.html'
        )
        if args.dry_run:
            print(out_path)
            continue
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page_html)
        written += 1

    if not args.dry_run:
        print(f"Wrote {written} trick pages under {args.site}/<realm>/tricks/<category>/")


if __name__ == "__main__":
    main()
