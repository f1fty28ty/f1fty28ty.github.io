#!/usr/bin/env python3
"""
merge_tricks.py  --  collapse duplicate / redundant trick entries in one go.

Put this file in the Snowboard-Compendium root (next to tricks.csv) and run:

    python3 merge_tricks.py --dry-run     # preview only: nothing in your folder is touched
    python3 merge_tricks.py               # shows the plan, asks "Apply? [y/N]", then does it
    python3 merge_tricks.py --yes         # same, no question

WHAT IT DOES
------------
1. FS / BS variants get merged into one entry
     Boardslide + Boardslide FS + Boardslide BS          ->  Boardslide
     FS Boardslide Pull Back + BS Boardslide Pull Back   ->  Boardslide Pull Back
   * In every category in DIRECTION_MERGE_ALL_CATEGORIES (Rails / Boxes) every
     FS/BS pair or triplet is merged.
   * In every OTHER category only the clear triplets are merged (a plain entry
     sitting next to its FS and BS copies: Handplant, Shifty, Air ...).
     Plain FS/BS *pairs* elsewhere (Nose Roll, Revert ...) are left alone and
     listed in the report -- you may have them as deliberate progression steps.

2. ALIASES: an entry that is really just another entry with a stance prefix
   ("Half Cab" is a switch FS 180, "Switch Backside 360" is a BS 360) is
   removed and its name is added to the real entry's "Also Known As". That makes
   it show up as a tag on the real page and findable in the site search.

3. MERGES: hand-picked "these two are the same thing" merges (see MERGES).

4. NAMES: an FS/BS that is written as a suffix goes in front of the name
     Nose Roll — FS  ->  FS Nose Roll          Revert — BS  ->  BS Revert
   and a "— Backside" / "— Frontside" that only repeats a BS/FS name is dropped
     BS 180 — Backside  ->  BS 180
   Hub rows also stop appending the rotation ("BS 180 — 180", "... — 90") or the
   long grip text ("Indy — Rear hand toeside ...") -- the hub now shows exactly the
   page title. The rotation stays in the CSV and shows as a tag on the page.

5. Everything downstream is kept in step, so nothing is left dangling:
     * tricks.csv                 rewritten (backup: tricks.csv.bak, first run only)
     * Builds From / Leads To     old names rewritten to the surviving name,
                                  duplicates and self-references dropped
     * trick pages                merged-away pages deleted; pages whose content
                                  or links changed are regenerated (through
                                  generate_trick_pages.py, so same layout)
     * hub tables                 rows removed / renamed, counts refreshed (build_table.py), home page too
     * search index               rebuilt (build_search_index.py), search widget
                                  re-injected (inject_search_ui.py)
   and it finishes with a consistency check (no stray pages / hub rows, no newly
   broken links).

   It never creates pages or hub rows for entries that have none (so tricks you
   deleted from the site by hand don't come back) -- it just tells you about them.

SAFETY
------
* --dry-run runs the whole pipeline on a throw-away copy and reports exactly which
  files would be added / changed / deleted.
* Pages that no longer carry the generator's "TODO: replace the single Overview"
  marker are treated as hand-written and are NEVER overwritten or deleted --
  they are listed as warnings so you can fix them by hand.
* Re-running is harmless: once merged there is nothing left to merge.
* The site is a git repo, so `git diff` / `git checkout .` is your undo button.

To change what gets merged, edit the CONFIG block right below. Needs: beautifulsoup4.
"""

import argparse
import csv
import hashlib
import html
import importlib
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True   # don't litter the repo with __pycache__

# =============================================================================
# CONFIG -- edit these
# =============================================================================

# Categories where EVERY FS/BS pair or triplet is merged (names use the CSV's
# Category spelling, not the display spelling).
DIRECTION_MERGE_ALL_CATEGORIES = {"Rails / Boxes"}

# Entries that are just another entry seen from a different stance.
# (category, entry to remove, entry it points at, AKA text added on the target)
# Give None as the AKA text to use the removed entry's own name.
ALIASES = [
    ("Jumps", "Half Cab",            "FS 180", "Half Cab (from switch)"),
    ("Jumps", "Switch Backside 180", "BS 180", None),
    ("Jumps", "Switch Backside 360", "BS 360", None),
    ("Jumps", "Switch Backside 540", "BS 540", None),   # its own AKA "Swack 540" is carried over
    ("Jumps", "Switch Backside 720", "BS 720", None),   # ... and "Swack 720"
    # Cab = switch frontside spin, so each Cab just points at its FS spin
    ("Jumps", "Cab",     "FS 360", "Cab (from switch)"),
    ("Jumps", "Cab 540", "FS 540", "Cab 540 (from switch)"),
    ("Jumps", "Cab 720", "FS 720", "Cab 720 (from switch)"),
]

# Hand-picked merges: (category, [(name, variation), ...] to fold away, (name, variation) to keep)
MERGES = [
    ("Rails / Boxes",         [("Transfer", "Rail-to-rail")],                    ("Transfer", "")),
    ("Features / Transition", [("Quarterpipe FS", ""), ("Quarterpipe BS", "")], ("Quarterpipe Air", "")),
]

# Entries to simply kill: (category, name, variation)
DELETE = [
    # you removed these pages from the site, so they leave the CSV too
    ("Flips / Inverted", "Backflip to Fakie",  ""),
    ("Flips / Inverted", "Frontflip to Fakie", ""),
    ("Flips / Inverted", "Ball Grab Backie",   ""),
    # ("Flatground", "Tripod", ""),
]

# =============================================================================
# internals
# =============================================================================

MODULES = ["generate_trick_pages", "build_table", "build_search_index", "inject_search_ui"]
DIRS = ("FS", "BS")
REL_COLS = ("Builds From", "Leads To")
HAND_WRITTEN_MARKER = "TODO: replace the single Overview"   # present in every generator-made page
REALMS = ["freestyle", "freeride", "powder", "carving"]

ROW_BLOCK = re.compile(r'^(?P<ind>[ \t]*)<tr data-category="(?P<cat>[^"]*)">\n.*?^(?P=ind)</tr>\n', re.M | re.S)
HREF_IN_ROW = re.compile(r'href="([^"]+)"')


def norm(s):
    return (s or "").strip()


def lc(s):
    return norm(s).lower()


def name_keys(name, var):
    """All the strings another row's Builds From / Leads To might use to refer to this row."""
    name, var = norm(name), norm(var)
    keys = {name.lower()}
    if var:
        keys |= {f"{name} {var}".lower(), f"{name} ({var})".lower()}
        if var in DIRS:
            keys.add(f"{var} {name}".lower())
    return keys


def split_tokens(cell):
    return [p.strip() for p in (cell or "").split("/") if p.strip()]


def dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    return out


def split_dir(row):
    """('Boardslide', 'FS') for Boardslide|FS or 'FS Boardslide'; (None, None) otherwise."""
    name, var = norm(row["Name"]), norm(row["Variation"])
    if var in DIRS:
        return name, var
    if not var:
        m = re.match(r"^(FS|BS) (.+)$", name)
        if m:
            return m.group(2), m.group(1)
    return None, None


def lvl(row):
    try:
        return float(norm(row.get("Lvl #")) or 0)
    except ValueError:
        return 0.0


VARIATION_LABEL_MAX_LEN = 20   # same rule generate_trick_pages.py uses for page titles


def hub_name(row):
    """Name as it is displayed: 'Name — short variation', or just the name (same as the page title)."""
    var = norm(row.get("Variation"))
    return f'{norm(row["Name"])} — {var}' if var and len(var) <= VARIATION_LABEL_MAX_LEN else norm(row["Name"])


def strip_direction_words(text):
    t = re.sub(r"\b(frontside|backside|FS|BS)\b[ \t]*", "", text, flags=re.I)
    t = re.sub(r"[ \t]{2,}", " ", t).strip()
    return t[:1].upper() + t[1:] if t else t


# -----------------------------------------------------------------------------
# rule engine (pure data: rows in, rows + report out)
# -----------------------------------------------------------------------------

class Plan:
    def __init__(self, rows):
        self.orig = [dict(r) for r in rows]        # untouched snapshot
        self.rows = rows                            # mutated in place
        self.fate = {}                              # orig index -> (kind, survivor index | None)
        self.direction = []                         # report lines
        self.explicit = []
        self.aliases = []
        self.deleted = []
        self.renamed = []
        self.warnings = []
        self.review = []
        self.candidates = []

    def alive(self):
        return [r for r in self.rows if r["_i"] not in self.fate]


def find_rows(plan, cat, name, var=None):
    return [r for r in plan.alive()
            if r["Category"] == cat and lc(r["Name"]) == name.lower()
            and (var is None or lc(r["Variation"]) == var.lower())]


def fold_relations(surv, other):
    for col in REL_COLS:
        surv[col] = " / ".join(dedupe(split_tokens(surv[col]) + split_tokens(other[col])))


def add_aka(surv, *names):
    have = [a.strip() for a in norm(surv["Also Known As"]).split(",") if a.strip()]
    for n in names:
        n = norm(n)
        if n and n.lower() not in [h.lower() for h in have]:
            have.append(n)
    surv["Also Known As"] = ", ".join(have)


def combine_descriptions(plan, surv, members, had_generic):
    descs = dedupe([norm(m["Description"]) for m in members if norm(m["Description"])])
    label = f'{surv["Category"]} / {surv["Name"]}'
    if had_generic:
        keep = norm(surv["Description"]) or (descs[0] if descs else "")
    elif len(descs) <= 1:
        keep = descs[0] if descs else ""
    elif len({strip_direction_words(d).lower() for d in descs}) == 1:
        keep = strip_direction_words(descs[0])
        plan.review.append(f"{label}: FS/BS descriptions only differed by direction words -> direction words removed")
    else:
        keep = " ".join(descs)
        plan.review.append(f"{label}: FS and BS descriptions were different -> joined together, please tidy by hand")
    surv["Description"] = keep


def merge_group(plan, surv, others, *, had_generic=False, combine=True, kind="merge"):
    """Fold `others` into `surv` (relations unioned, AKA unioned, blanks filled)."""
    members = [surv] + others
    for o in others:
        fold_relations(surv, o)
        add_aka(surv, *[a for a in norm(o["Also Known As"]).split(",")])
        for col in ("Terrain / Feature", "Rotation", "Review", "Terrain"):
            if not norm(surv[col]) and norm(o[col]):
                surv[col] = o[col]
        if norm(o["Level"]) != norm(surv["Level"]):
            plan.warnings.append(
                f'{surv["Category"]} / {norm(surv["Name"])}: merged "{hub_name(o)}" was {o["Level"]} but the kept entry is {surv["Level"]} -- kept {surv["Level"]}')
        plan.fate[o["_i"]] = (kind, surv["_i"])
    if combine:
        combine_descriptions(plan, surv, members, had_generic)


def direction_merges(plan):
    alive = plan.alive()
    directional = defaultdict(list)
    generic = {}
    for r in alive:
        base, d = split_dir(r)
        if d:
            directional[(r["Category"], base.lower())].append(r)
        elif not norm(r["Variation"]):
            generic.setdefault((r["Category"], lc(r["Name"])), r)

    for key, dirs in directional.items():
        cat = key[0]
        gen = generic.get(key)
        members = ([gen] if gen else []) + dirs
        if len(members) < 2:
            continue
        if not gen and cat not in DIRECTION_MERGE_ALL_CATEGORIES:
            # only flag pairs built the same way as the rail duplicates (FS/BS in the Variation column);
            # "BS Cork 540" / "FS Cork 540" style pairs are separately named tricks, so they aren't flagged
            if any(norm(m["Variation"]) in DIRS for m in dirs):
                plan.candidates.append(f"[{cat}] " + ", ".join(hub_name(m) for m in dirs)
                                       + "   (FS/BS pair, no plain entry -- left alone)")
            continue
        base_name = split_dir(dirs[0])[0]
        surv = gen or min(dirs, key=lambda r: (lvl(r), r["_i"]))
        others = [m for m in members if m is not surv]
        before = hub_name(surv)
        merge_group(plan, surv, others, had_generic=bool(gen))
        surv["Name"], surv["Variation"] = base_name, ""
        plan.direction.append(f'[{cat}] {hub_name(surv)}   <=   ' + ", ".join(hub_name(o) for o in others)
                              + ("" if gen else f'   (kept "{before}" row, renamed)'))


def explicit_merges(plan):
    for cat, froms, (into_name, into_var) in MERGES:
        targets = find_rows(plan, cat, into_name, into_var)
        srcs = [r for nv in froms for r in find_rows(plan, cat, nv[0], nv[1])]
        if not srcs:
            continue                                    # already applied
        if len(targets) != 1:
            plan.warnings.append(f"MERGES: could not find exactly one [{cat}] {into_name} {into_var} to merge into -- skipped")
            continue
        surv = targets[0]
        merge_group(plan, surv, srcs, had_generic=True)
        plan.explicit.append(f'[{cat}] {hub_name(surv)}   <=   ' + ", ".join(hub_name(s) for s in srcs))


def alias_merges(plan):
    for cat, alias, target, aka in ALIASES:
        srcs = find_rows(plan, cat, alias)
        if not srcs:
            continue
        tgts = find_rows(plan, cat, target)
        if len(tgts) != 1:
            plan.warnings.append(f"ALIASES: '{alias}' -> could not find exactly one [{cat}] '{target}' -- skipped")
            continue
        surv = tgts[0]
        for s in srcs:
            add_aka(surv, aka or norm(s["Name"]), *[a for a in norm(s["Also Known As"]).split(",")])
            plan.fate[s["_i"]] = ("alias", surv["_i"])
            plan.aliases.append((cat, hub_name(s), surv, aka or norm(s["Name"])))
            if norm(s["Description"]):
                plan.review.append(f'dropped description of alias "{norm(s["Name"])}": {norm(s["Description"])[:140]}')


def deletions(plan):
    for cat, name, var in DELETE:
        for r in find_rows(plan, cat, name, var):
            plan.fate[r["_i"]] = ("deleted", None)
            plan.deleted.append(f"[{cat}] {hub_name(r)}")


def normalise_names(plan):
    """FS/BS goes in front of the name; a '— Backside/Frontside' that repeats a BS/FS name is dropped."""
    for r in plan.alive():
        n, v = norm(r["Name"]), norm(r["Variation"])
        before = hub_name(r)
        if v in DIRS and not re.match(r"^(FS|BS) ", n):
            r["Name"], r["Variation"] = f"{v} {n}", ""
        elif (v, n[:3]) in (("Backside", "BS "), ("Frontside", "FS ")):
            r["Variation"] = ""
        else:
            continue
        plan.renamed.append(f'[{r["Category"]}] {before}   ->   {hub_name(r)}')


def rewrite_references(plan):
    """Builds From / Leads To: point old names at the surviving entry, drop dupes + self references."""
    alive = plan.alive()
    alive_keys = set()
    for r in alive:
        alive_keys |= name_keys(r["Name"], r["Variation"])

    by_i = {r["_i"]: r for r in plan.rows}
    cands = defaultdict(list)          # old reference text -> [(new name, prefer?)]
    drop = set()                       # references to deleted entries
    for i, old in enumerate(plan.orig):
        kind, surv_i = plan.fate.get(i, ("kept", i))
        keys = {k for k in name_keys(old["Name"], old["Variation"]) if k not in alive_keys}
        if surv_i is None:
            drop |= keys
            continue
        final = norm(by_i[surv_i]["Name"])
        if kind == "kept" and (old["Name"], old["Variation"]) == (by_i[i]["Name"], by_i[i]["Variation"]):
            continue
        prefer = norm(old["Variation"]) == "FS" or norm(old["Name"]).startswith("FS ")
        for k in keys:
            cands[k].append((final, prefer))
    rename = {}
    for k, options in cands.items():
        # if one old name now belongs to several entries (e.g. "Nose Roll" -> FS / BS), send it to the FS one
        rename[k] = next((n for n, pref in options if pref), options[0][0])
    drop -= set(rename)

    changed = 0
    for r in alive:
        own = name_keys(r["Name"], r["Variation"])
        for col in REL_COLS:
            toks = split_tokens(r[col])
            new = dedupe([rename.get(t.lower(), t) for t in toks if t.lower() not in drop])
            new = [t for t in new if t.lower() not in own]
            if new != toks:
                r[col] = " / ".join(new)
                changed += 1
    return changed


def similar_leftovers(plan):
    """Things that still look like duplicates after the rules ran (report only)."""
    alive = plan.alive()
    buckets = defaultdict(list)
    for r in alive:
        if norm(r["Variation"]) or split_dir(r)[1]:
            continue
        buckets[re.sub(r"[^a-z0-9]", "", lc(r["Name"]))].append(r)
    for k, rs in buckets.items():
        if len(rs) > 1:
            plan.candidates.append("Same name in several places: " + ", ".join(f'[{r["Category"]}] {r["Name"]}' for r in rs))
    seen = set()
    for r in alive:
        key = (r["Category"], lc(r["Name"]), lc(r["Variation"]))
        if key in seen:
            plan.warnings.append(f'duplicate entry remains: [{r["Category"]}] {hub_name(r)}')
        seen.add(key)


def run_rules(rows):
    plan = Plan(rows)
    direction_merges(plan)
    explicit_merges(plan)
    alias_merges(plan)
    deletions(plan)
    normalise_names(plan)
    plan.ref_changes = rewrite_references(plan)
    similar_leftovers(plan)
    return plan


def print_plan(plan, n_before, n_after):
    def section(title, lines):
        if lines:
            print(f"\n{title}")
            for ln in lines:
                print("  " + ln)
    print(f"tricks.csv: {n_before} entries -> {n_after} entries  ({n_before - n_after} removed)")
    section(f"FS/BS MERGES ({len(plan.direction)})", plan.direction)
    section(f"EXPLICIT MERGES ({len(plan.explicit)})", plan.explicit)
    section(f"ALIASES -> removed, kept as 'Also Known As' + searchable ({len(plan.aliases)})",
            [f'[{c}] {src}   ->   {hub_name(surv)}   (AKA "{aka}")' for c, src, surv, aka in plan.aliases])
    section(f"DELETED ({len(plan.deleted)})", plan.deleted)
    section(f"RENAMED: FS/BS in front, redundant suffix dropped ({len(plan.renamed)})", plan.renamed)
    if plan.ref_changes:
        print(f"\nBuilds From / Leads To cells rewritten: {plan.ref_changes}")
    section("PLEASE REVIEW", plan.review)
    section("WARNINGS", plan.warnings)
    section("LOOKS SIMILAR, NOT TOUCHED (add to the CONFIG block if you want them merged)", plan.candidates)


# -----------------------------------------------------------------------------
# csv io
# -----------------------------------------------------------------------------

def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        rows = [dict(r) for r in reader]
    for i, r in enumerate(rows):
        for k in fields:
            r[k] = r.get(k) or ""
        r["_i"] = i
    return fields, rows


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\r\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def clean(rows):
    """Copies shaped like generate_trick_pages.read_tricks() output, plus _i."""
    out = []
    for r in rows:
        c = {k: (v or "").strip() for k, v in r.items() if k != "_i"}
        c["_i"] = r["_i"]
        if c.get("Category") and c.get("Name"):
            out.append(c)
    return out


# -----------------------------------------------------------------------------
# site io helpers
# -----------------------------------------------------------------------------

def load_modules(root):
    for name in MODULES:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(root))
    try:
        return {n: importlib.import_module(n) for n in MODULES}
    except ImportError as e:
        sys.exit(f"Could not import a site script ({e}). Run this from the Snowboard-Compendium folder; "
                 f"beautifulsoup4 is also needed:  pip install beautifulsoup4")
    finally:
        sys.path.pop(0)


def render(gen, rec, name_index):
    """generate_trick_pages' page + 'Also known as' appended to the meta description (feeds site search)."""
    page = gen.build_page(rec, name_index)
    aka = rec["row"].get("Also Known As", "")
    if aka:
        page = re.sub(r'(<meta name="description" content="[^"]*?)(">)',
                      lambda m: f'{m.group(1)} Also known as: {gen.esc(aka)}.{m.group(2)}', page, count=1)
    return page


def page_path(root, rec):
    return root / rec["realm_slug"] / "tricks" / rec["cat_slug"] / f'{rec["slug"]}.html'


def hub_href(rec):
    return f'tricks/{rec["cat_slug"]}/{rec["slug"]}.html'


def is_hand_written(path):
    return path.exists() and HAND_WRITTEN_MARKER not in path.read_text(encoding="utf-8")


def local_broken_links(root):
    broken = set()
    for p in root.rglob("*.html"):
        if any(part in (".git", "__pycache__") for part in p.parts):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        for h in re.findall(r'href="([^"#?]+)"', t):
            if re.match(r"^(https?:|mailto:|javascript:|tel:)", h):
                continue
            if not (p.parent / h).resolve().exists():
                broken.add((p.relative_to(root).as_posix(), h))
    return broken


def prune_empty_dirs(root):
    for realm in REALMS:
        base = root / realm / "tricks"
        if base.exists():
            for d in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
                if not any(d.iterdir()):
                    d.rmdir()


# -----------------------------------------------------------------------------
# hub tables
# -----------------------------------------------------------------------------

def render_hub_row(ind, multi, rec, name):
    row = rec["row"]
    diff = rec["diff"]
    gen_label = {"green": "Green Circle", "blue": "Blue Square", "black": "Black Diamond", "dblack": "Double Black Diamond"}[diff]
    esc = lambda s: html.escape(s, quote=True)
    cat_td = f'{ind}<td class="hub-table__col--meta hub-table__meta">{esc(rec["cat_display"])}</td>\n' if multi else ""
    return (
        f'{ind}<tr data-category="{esc(rec["cat_display"])}">\n'
        f'{ind}<td><span class="badge" data-difficulty="{diff}" data-size="14" aria-label="{gen_label}"></span></td>\n'
        f'{ind}<td><a class="hub-table__name-link" href="{hub_href(rec)}">{esc(name)}</a></td>\n'
        f'{cat_td}'
        f'{ind}<td class="hub-table__col--meta hub-table__meta">{esc(row.get("Terrain / Feature") or "—")}</td>\n'
        f'{ind}</tr>\n'
    )


def sync_hub(root, realm, old_rec_by_i, new_rec_by_i, alive_ids, stats, warnings):
    path = root / realm / "index.html"
    text = path.read_text(encoding="utf-8")
    blocks = list(ROW_BLOCK.finditer(text))
    if not blocks:
        warnings.append(f"{realm}/index.html: no table rows found, hub left alone")
        return
    for a, b in zip(blocks, blocks[1:]):
        if a.end() != b.start():
            warnings.append(f"{realm}/index.html: rows are not contiguous, hub left alone")
            return
    multi = ">Category</th>" in text

    old_href_to_i = {f'{r["realm_slug"]}/{hub_href(r)}': i for i, r in old_rec_by_i.items() if r["realm_slug"] == realm}

    out, emitted = [], set()
    for m in blocks:
        block = m.group(0)
        href = HREF_IN_ROW.search(block).group(1)
        i = old_href_to_i.get(f"{realm}/{href}")
        if i is None:
            out.append(block)
            warnings.append(f"{realm}/index.html: row for {href} isn't in tricks.csv (left as is)")
        elif i not in alive_ids:
            stats["hub_removed"] += 1
        else:
            rec = new_rec_by_i[i]
            emitted.add(i)
            terr = rec["row"].get("Terrain / Feature") or "—"
            cells = re.findall(r'<td class="hub-table__col--meta hub-table__meta">([^<]*)</td>', block)
            cur_name = html.unescape(re.search(r'name-link" href="[^"]*">([^<]*)</a>', block).group(1))
            cur_diff = re.search(r'data-difficulty="([^"]*)"', block).group(1)
            up_to_date = (hub_href(rec) == href and cur_name == rec["title"]
                          and cur_diff == rec["diff"] and html.unescape(cells[-1]) == terr)
            if up_to_date:
                out.append(block)
            else:
                out.append(render_hub_row(m.group("ind"), multi, rec, rec["title"]))
                stats["hub_renamed"] += 1

    for i, rec in sorted(new_rec_by_i.items()):
        if rec["realm_slug"] == realm and i not in emitted:
            warnings.append(f'{realm}/index.html: "{rec["title"]}" is in tricks.csv but has no hub row (not added)')

    new_text = text[:blocks[0].start()] + "".join(out) + text[blocks[-1].end():]
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")


# -----------------------------------------------------------------------------
# the pipeline (used for the real run AND for the dry-run on a temp copy)
# -----------------------------------------------------------------------------

def apply_to_site(root, plan, fields, quiet=False):
    mods = load_modules(root)
    gen, btable, bsearch, inject = (mods[n] for n in MODULES)
    csv_path = root / "tricks.csv"
    stats = defaultdict(int)
    warnings = []
    baseline_broken = local_broken_links(root)

    # --- old / new page indexes ------------------------------------------------
    old_clean = clean(plan.orig)
    old_assigned, old_index = gen.build_index(old_clean)
    old_rec_by_i = {r["row"]["_i"]: r for r in old_assigned}

    new_rows = plan.alive()
    new_clean = clean(new_rows)
    new_assigned, new_index = gen.build_index(new_clean)
    new_rec_by_i = {r["row"]["_i"]: r for r in new_assigned}
    alive_ids = set(new_rec_by_i)

    # --- tricks.csv ---------------------------------------------------------------
    bak = root / "tricks.csv.bak"
    if not bak.exists():
        shutil.copy2(csv_path, bak)
    write_csv(csv_path, fields, new_rows)

    # --- trick pages -------------------------------------------------------------
    new_paths = {page_path(root, r) for r in new_assigned}
    for i, rec in new_rec_by_i.items():
        p_new = page_path(root, rec)
        new_html = render(gen, rec, new_index)
        old_rec = old_rec_by_i.get(i)
        p_old = page_path(root, old_rec) if old_rec else None
        old_html = render(gen, old_rec, old_index) if old_rec else None

        if p_new.exists() and is_hand_written(p_new):
            if new_html != old_html:
                warnings.append(f"hand-written page NOT touched (its content/links may need updating): {p_new.relative_to(root)}")
            continue
        if not p_new.exists():
            if not (p_old and p_old.exists()):
                warnings.append(f'"{rec["title"]}" is in tricks.csv but has no page (not created)')
                continue
            if is_hand_written(p_old):
                warnings.append(f"hand-written page needs renaming by hand: {p_old.relative_to(root)} -> {p_new.relative_to(root)}")
                continue
        if p_new.exists() and p_old == p_new and new_html == old_html:
            continue                                   # nothing about this page changed
        p_new.parent.mkdir(parents=True, exist_ok=True)
        existed = p_new.exists()
        p_new.write_text(new_html, encoding="utf-8")
        inject.process(p_new)
        stats["pages_rewritten" if existed else "pages_added"] += 1

    # pages whose entry is gone (or moved to a new slug)
    for i, rec in old_rec_by_i.items():
        p_old = page_path(root, rec)
        if p_old in new_paths or not p_old.exists():
            continue
        if is_hand_written(p_old):
            warnings.append(f"hand-written page for a removed entry NOT deleted: {p_old.relative_to(root)}")
            continue
        p_old.unlink()
        stats["pages_removed"] += 1
    prune_empty_dirs(root)

    # 'Also known as' in the meta description of every generated page that has an AKA (search)
    for rec in new_assigned:
        aka = rec["row"].get("Also Known As", "")
        p = page_path(root, rec)
        if not aka or not p.exists() or is_hand_written(p):
            continue
        t = p.read_text(encoding="utf-8")
        if "Also known as:" not in t:
            t2 = re.sub(r'(<meta name="description" content="[^"]*?)(">)',
                        lambda m: f'{m.group(1)} Also known as: {gen.esc(aka)}.{m.group(2)}', t, count=1)
            if t2 != t:
                p.write_text(t2, encoding="utf-8")
                stats["aka_meta_patched"] += 1

    # --- hub tables + counts -----------------------------------------------------
    for realm in REALMS:
        sync_hub(root, realm, old_rec_by_i, new_rec_by_i, alive_ids, stats, warnings)
    counts = {}
    _stdout = sys.stdout
    if quiet:
        sys.stdout = open(os.devnull, "w")
    try:
        for rel, noun in btable.HUB_FILES:
            n = btable.process(rel, noun)
            if n is not None:
                counts[rel.split("/")[0]] = n
        btable.update_home(counts)
        bsearch.main()
    finally:
        if quiet:
            sys.stdout.close()
            sys.stdout = _stdout

    # --- consistency check -----------------------------------------------------------
    problems = []
    for realm in REALMS:
        text = (root / realm / "index.html").read_text(encoding="utf-8")
        hub = set(HREF_IN_ROW.findall("".join(m.group(0) for m in ROW_BLOCK.finditer(text))))
        want = {hub_href(r) for r in new_assigned if r["realm_slug"] == realm}
        for h in sorted(hub - want):
            problems.append(f"{realm} hub row not in CSV: {h}")
    for realm in REALMS:
        base = root / realm / "tricks"
        for p in base.rglob("*.html") if base.exists() else []:
            if p not in new_paths:
                problems.append(f"page not in CSV (left in place): {p.relative_to(root)}")
    for page, href in sorted(local_broken_links(root) - baseline_broken):
        problems.append(f"NEW broken link in {page}: {href}")

    return stats, warnings, problems, baseline_broken


def tree_hashes(root):
    out = {}
    for p in root.rglob("*"):
        if p.is_file() and not any(part in (".git", "__pycache__") for part in p.parts):
            out[p.relative_to(root).as_posix()] = hashlib.md5(p.read_bytes()).hexdigest()
    return out


def main():
    ap = argparse.ArgumentParser(description="Merge duplicate trick entries and keep the site in sync.")
    ap.add_argument("--site", default=str(Path(__file__).resolve().parent), help="site root (default: this script's folder)")
    ap.add_argument("--dry-run", action="store_true", help="preview on a temporary copy; change nothing")
    ap.add_argument("--yes", "-y", action="store_true", help="don't ask for confirmation")
    args = ap.parse_args()

    root = Path(args.site).resolve()
    if not (root / "tricks.csv").exists() or not (root / "generate_trick_pages.py").exists():
        sys.exit(f"{root} doesn't look like the Snowboard-Compendium folder (no tricks.csv / generate_trick_pages.py).")

    fields, rows = read_csv(root / "tricks.csv")
    n_before = len(rows)
    plan = run_rules(rows)
    n_after = len(plan.alive())

    print_plan(plan, n_before, n_after)
    nothing_to_do = n_after == n_before and not plan.ref_changes
    if nothing_to_do:
        print("\nNothing left to merge -- the CSV is already clean. (Will still make sure pages/hubs/search match the CSV.)")

    if args.dry_run:
        tmp = Path(tempfile.mkdtemp(prefix="compendium-dryrun-"))
        try:
            shutil.copytree(root, tmp / "site", ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))
            before = tree_hashes(tmp / "site")
            stats, warnings, problems, _ = apply_to_site(tmp / "site", plan, fields, quiet=True)
            after = tree_hashes(tmp / "site")
        finally:
            for n in MODULES:
                sys.modules.pop(n, None)
            shutil.rmtree(tmp, ignore_errors=True)
        added = sorted(k for k in after if k not in before)
        removed = sorted(k for k in before if k not in after)
        changed = sorted(k for k in after if k in before and after[k] != before[k])
        print("\n--- DRY RUN: nothing was changed in your folder ---")
        print(f"would delete {len(removed)} file(s), add {len(added)}, modify {len(changed)}")
        for label, lst in (("DELETE", removed), ("ADD", added)):
            for k in lst:
                print(f"  {label}  {k}")
        for k in changed:
            print(f"  MODIFY  {k}")
        report(stats, warnings, problems)
        return

    if not args.yes:
        if input("\nApply? Your folder will be modified (git diff shows everything) [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled, nothing changed.")
            return

    stats, warnings, problems, _ = apply_to_site(root, plan, fields)
    print("\n--- DONE ---")
    report(stats, warnings, problems)
    print("\nNext: open the site locally, then `git status` / `git diff --stat` to review, and commit.")


def report(stats, warnings, problems):
    print(f"pages: {stats['pages_removed']} removed, {stats['pages_rewritten']} regenerated, {stats['pages_added']} added"
          f" | hub rows: {stats['hub_removed']} removed, {stats['hub_renamed']} renamed/updated, {stats['hub_added']} added"
          f" | 'also known as' search text added to {stats['aka_meta_patched']} more page(s)")
    if warnings:
        print("\nWARNINGS")
        for w in warnings:
            print("  " + w)
    if problems:
        print("\nCONSISTENCY PROBLEMS")
        for p in problems:
            print("  " + p)
    else:
        print("consistency check: OK (no stray pages or hub rows, no newly broken links)")


if __name__ == "__main__":
    main()
