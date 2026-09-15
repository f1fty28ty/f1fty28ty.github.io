# The Snowboard Compendium — Site Kit

## What's in here

```
site/
├── index.html              ← home page (already built, live example)
├── styles.css               ← shared design system — never duplicate this file
└── templates/
    ├── trick-template.html      ← for the 60+ Trick Library pages
    ├── drill-template.html      ← for Drill Vault pages
    ├── essential-template.html  ← for the 6 core curriculum posts
    ├── realm-template.html      ← for the 4 Realm hub pages
    └── reference-template.html  ← for static Reference pages
```

## How to make a new page

1. Copy the right template out of `/templates` into the folder where the live
   page will sit (or straight into `/site` if you're not nesting folders).
2. Rename the file — e.g. `trick-template.html` → `frontside-360.html`.
3. Find-and-replace the bracketed placeholders: `[TRICK NAME]`, `[PREREQ_1_LINK]`,
   etc. Every bracket is something you fill in; nothing else needs to change.
4. Pick the right difficulty badge in the trick template — three are pre-written
   as HTML comments right under the one that's active. Uncomment the one you
   need, delete the rest.
5. Save. Done — no build step, no compiling.

Because every template pulls from the same `styles.css`, changing a color or
font once updates every page site-wide. Never copy CSS into an individual
page.

## The header/nav block

Every page starts with the same `<header class="site-header">...</header>`
block. It's plain HTML, not an include — because this is a flat static site
with no templating engine, you paste it identically into each new page. Two
things to update per page:
- Fix the relative path in each `href` (`index.html` vs `../index.html`)
  depending on how deep the file sits in your folder structure.
- Add `aria-current="page"` to whichever nav link matches the section you're
  in (this is what puts the orange underline under "Tricks" while you're on a
  trick page).

If this ever becomes annoying to maintain by hand across 100+ pages, that's
the point where it's worth moving to a static site generator (like Eleventy
or Hugo) that injects the header from one file automatically. Nothing here
locks you out of that later — the HTML and CSS both carry over directly.

## The difficulty system

Badges use the actual resort trail-rating shapes rather than a generic
"Easy/Medium/Hard" label:

| Level | Shape | Color |
|---|---|---|
| Beginner | ● circle | green |
| Intermediate | ■ square | blue |
| Advanced | ◆ diamond | black |
| Expert | ◆◆ double diamond | black |

The SVG shapes are inline in the trick template so there's no image file to
manage. Copy the whole `<span class="difficulty ...">` block, don't rebuild
it from scratch.

## Free hosting

This is a static site — no server, no database. Any of these host it for
free:
- **GitHub Pages** — push the `site/` folder to a repo, turn on Pages in
  settings. Best if you're already comfortable with git.
- **Netlify** or **Cloudflare Pages** — drag-and-drop the folder in their
  dashboard, no git required, get a live URL immediately.

## Content rules carried over from the brief

- No fluff — every line teaches or points somewhere.
- Bold key terms, use bullet lists over paragraphs where possible.
- Long enumerated lists (terminology, risk types) go in `<details>`
  accordions — native HTML, no JavaScript needed, works everywhere.
- Coach's Corner callouts use the same orange-accent card every time —
  don't invent a new callout style per page.
- Tags aren't wired up yet (matches the original plan) — when you're ready,
  the cleanest free-tier approach is a simple JSON file of tags per page plus
  a bit of vanilla JS to filter the Skill Level and Realm listing pages.
