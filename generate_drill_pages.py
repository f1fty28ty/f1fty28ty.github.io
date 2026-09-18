#!/usr/bin/env python3
"""
generate_drill_pages.py

Builds one HTML page per drill for The Snowboard Compendium, using
trick/backside-180.html as the structural template, pulling all data
from drills.csv.

Usage:
    python3 generate_drill_pages.py [--csv drills.csv] [--site .] [--dry-run]

Run this from (or point --site at) the root of the Snowboard-Compendium
folder -- the folder that directly contains index.html, assets/,
drills/, etc.

WHAT IT DOES
------------
For every row in drills.csv it writes:
    {site}/drills/{drill-slug}.html

using the exact same slug rule drills/index.html already links with
(slugify the drill name -- no folders, flat under drills/), so every
link already sitting in that hub resolves to a real file after this
script runs.

drills.csv has these columns:
    Category     fine-grained group from the AASI table (e.g. "Carved Turns")
    Group        the broad group drills/index.html sorts it under
                 (e.g. "Turns — Skidded & Carved") -- this is what
                 shows in the breadcrumb / meta rail as "Category"
    Drill        the drill's name
    Difficulty   display level range, e.g. "L1–L2"
    Level Min    1/2/3, drives the difficulty badge (1=green, 2=blue, 3=black)
    Level Max    1/2/3
    Terrain      where it's practiced (e.g. "Carves", "Bumps", "All")
    Description  full write-up -- goes straight into the Overview step

Drills don't have a "Builds From" / "Leads To" chain the way tricks do,
so generated pages skip the Requires/Opens meta-sections and the
progression rail is left empty (structure kept for visual consistency
with trick pages, just with nothing plugged into prev/next).

Re-run any time drills.csv changes; it always overwrites in place.
"""

import argparse
import csv
import html
import os
import re
import sys

DIFF_BY_LEVEL_MIN = {"1": "green", "2": "blue", "3": "black"}
DIFF_LABEL = {
    "green": "Green Circle",
    "blue": "Blue Square",
    "black": "Black Diamond",
    "dblack": "Double Black Diamond",
}


def slugify(text):
    text = text.lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def esc(text):
    return html.escape(text or "", quote=True)


def read_drills(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if not row.get("Drill"):
                continue
            rows.append({k: (v or "").strip() for k, v in row.items()})
        return rows


NAV_REALMS = [("Freestyle", "freestyle"), ("Freeride", "freeride"), ("Powder", "powder"), ("Carving", "carving")]


def nav_html(root, active_drills=True):
    items = []
    for label, slug in NAV_REALMS:
        items.append(f'          <li><a href="{root}{slug}/index.html">{label}</a></li>')
    items.append(f'          <li><a href="{root}essentials/index.html">Essentials</a></li>')
    cur = ' aria-current="page"' if active_drills else ""
    items.append(f'          <li><a href="{root}drills/index.html"{cur}>Drills</a></li>')
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
      <a class="breadcrumb__item" href="{root}drills/index.html">Drills</a>
      <span class="breadcrumb__sep">›</span>
      <span class="breadcrumb__item">{group}</span>
      <span class="breadcrumb__sep">›</span>
      <span class="breadcrumb__item breadcrumb__item--current">{title}</span>
    </div>
  </div>

  <!-- Progression rail -->
  <div class="progression-rail" aria-label="Trick progression">
    <div class="progression-rail__inner">
      <span class="progression-rail__label">PROGRESSION ›</span>
      <span class="progression-rail__prev"></span>
      <div class="progression-rail__line">
        <span class="progression-rail__current">{title}</span>
      </div>
      <span class="progression-rail__next"></span>
    </div>
  </div>

  <!-- Trick page content -->
  <main class="trick-page">
    <div class="container">
      <div class="trick-layout">

        <!-- Left metadata rail -->
        <aside class="meta-rail" aria-label="Drill metadata">
          <div class="meta-rail__badge">
            <span class="badge" data-difficulty="{diff}" data-size="32" data-label="true" aria-label="{diff_label} — difficulty"></span>
          </div>

          <div class="meta-row">
            <div class="meta-row__label">Realm</div>
            <div class="meta-row__value">Drills</div>
          </div>
          <div class="meta-row">
            <div class="meta-row__label">Category</div>
            <div class="meta-row__value">{group}</div>
          </div>
          <div class="meta-row">
            <div class="meta-row__label">Level</div>
            <div class="meta-row__value">{difficulty}</div>
          </div>
          <div class="meta-row">
            <div class="meta-row__label">Terrain</div>
            <div class="meta-row__value">{terrain}</div>
          </div>
        </aside>

        <!-- Main content -->
        <div>

          <h1 class="trick-title">{title}</h1>
          <div class="trick-tags">
            <span class="trick-tag">{difficulty}</span>
            <span class="trick-tag">{category}</span>
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


def build_page(row):
    root = "../"
    diff = DIFF_BY_LEVEL_MIN.get(row.get("Level Min", "1"), "green")
    title = row["Drill"]
    group = row.get("Group") or row.get("Category") or "Drills"
    html_out = PAGE_TMPL.format(
        title=esc(title),
        meta_desc=esc(f'{title} — {row.get("Difficulty","")}. {group} drill.'),
        root=root,
        nav=nav_html(root),
        group=esc(group),
        diff=diff,
        diff_label=DIFF_LABEL[diff],
        difficulty=esc(row.get("Difficulty") or "—"),
        terrain=esc(row.get("Terrain") or "—"),
        category=esc(row.get("Category") or group),
        overview=esc(row.get("Description") or "Full write-up coming soon."),
    )
    return html_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="drills.csv", help="Path to drills.csv")
    ap.add_argument("--site", default=".", help="Path to the site root (contains index.html, assets/, etc.)")
    ap.add_argument("--dry-run", action="store_true", help="Report what would be written without writing files")
    args = ap.parse_args()

    rows = read_drills(args.csv)
    if not rows:
        print(f"No rows found in {args.csv}", file=sys.stderr)
        sys.exit(1)

    written = 0
    for row in rows:
        slug = slugify(row["Drill"])
        out_path = os.path.join(args.site, "drills", f"{slug}.html")
        page_html = build_page(row)
        if args.dry_run:
            print(out_path)
            continue
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page_html)
        written += 1

    if not args.dry_run:
        print(f"Wrote {written} drill pages under {args.site}/drills/")


if __name__ == "__main__":
    main()