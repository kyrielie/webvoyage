# Using webvoyage

Instructions for the repo as it currently stands (`webvoyage.zip`, unzipped into
your GitHub repo). This covers setup, the day-to-day authoring loop, testing,
and deployment. It does **not** cover the geospatial zone/grid map model —
that's still in design (see the note at the bottom).

---

## 1. One-time setup

```bash
# from the repo root
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install pytest

# confirm the pipeline runs before you touch anything
python src/pipeline/airport.py validate pages.example.json images
```

That last command will report missing-image errors — expected, since no art
ships in the repo. It confirms the Python side is wired up correctly.

**GitHub Pages, one-time toggle:** in your repo's GitHub settings, go to
**Settings → Pages → Source: GitHub Actions**. `.github/workflows/deploy.yml`
handles everything else automatically on every push to `main`.

**Git LFS, one-time, before your first art commit:**
```bash
git lfs install
git lfs track "build/**/*.png" "build/**/*.webp"
git add .gitattributes
```
Do this *before* committing any art. Retrofitting LFS onto history later
requires a rewrite — see `docs/PIPELINE.md` for why.

---

## 2. The two ways to author content

### A. Hand-edit `pages.json` directly
Fastest for small edits or if you don't want to organize a `build/` folder.
Copy `pages.example.json` to `pages.json` and edit it — see §3 for the schema.

### B. Organize a `build/` folder, let the tool generate `pages.json`
Better once you have real art. Create a `build/` folder where each page is a
subfolder containing:
- a background image (`bg.png`/`.jpg`/`.webp`/`.gif`)
- layer images for each clickable hotspot
- `label.txt` / `icon.txt` / `message.txt` per button (optional)
- nested subfolders = implied link targets (see the gotcha in §6)

Then run:
```bash
python src/pipeline/airport.py tree build .
```
This scans `build/`, writes `pages.json`, and copies images into `images/`.
**Re-running `tree` preserves any hand-edited `label`/`icon`/`message` values**
in the existing `pages.json` — it won't clobber text you've already tweaked.
It does **not** preserve hand-edited `href` values (see §6).

---

## 3. `pages.json` schema (quick reference)

```jsonc
{
  "schemaVersion": 1,
  "pages": [
    {
      "id": "mainhall",
      "title": "Airport — Main Hall",
      "message": "You are in the hall.",   // optional, auto-plays VN typewriter on load
      "pulse": false,                       // optional, ambient layer glow
      "buttons": [
        {
          "layer": 1,                        // -> images/mainhall-1.png
          "icon": "departingflights",        // must be a key in icons.js
          "label": "Departures",
          "href": "gate",                    // page id, "back", or null
          "transit": ["mainhall-1-frame1.png"],  // images/transit/*, optional
          "message": null                    // VN text, or null for a nav button
        }
      ]
    }
  ]
}
```

Slideshow pages add `"type": "slideshow"` and a `slideshow` block — see the
docstring at the top of `src/pipeline/generate_html.py` for the full shape.

Full schema notes, including the third-page-type extension pattern, are in
`docs/PIPELINE.md`.

---

## 4. Building and previewing locally

```bash
# validate first — catches broken links, missing images, bad icons, etc.
python src/pipeline/airport.py validate pages.json images

# render HTML
python src/pipeline/airport.py html pages.json dist

# copy the engine (JS/CSS) alongside the generated HTML
cp -r src/engine/* dist/

# also copy your art and sprite sheet if you have them
cp -r images dist/images
cp sprite.svg dist/sprite.svg

# serve locally to preview in a browser
cd dist && python3 -m http.server 8000
# open http://localhost:8000/mainhall.html
```

Or run the whole pipeline (tree → validate → html → graph) in one call:
```bash
python src/pipeline/airport.py build build .
```

---

## 5. The Obsidian authoring tools

```bash
python src/pipeline/airport.py graph pages.json .
```

This writes `graph/*.md` (one note per page, with YAML frontmatter for
Graph View filtering — try `tag:#root`, `tag:#dead-end`, `tag:#type/slideshow`)
**and** `graph/webvoyage.canvas`.

Open the `graph/` folder as an Obsidian vault:
- **Graph View** — for exploring structure. Node positions here are *not*
  saved; every reopen re-runs the physics simulation.
- **Canvas** (open `webvoyage.canvas` inside the vault) — for arranging and
  keeping. Drag cards around; positions persist. Re-running
  `airport.py graph` preserves any position you've dragged — it only adds
  cards for genuinely new pages.

---

## 6. Known gotcha: `href` isn't preserved across `tree` re-runs

If you hand-edit a button's `href` in `pages.json` and then rearrange
folders in `build/` before re-running `tree`, the link target can silently
revert to whatever the new folder nesting implies. `label`/`icon`/`message`
survive re-runs; `href` currently doesn't. If a link ever changes
unexpectedly right after running `tree`, this is why. (No fix is shipped
for this yet — noted here so it doesn't cost you an afternoon.)

---

## 7. Testing

```bash
# Python — validate.py's checks (broken hrefs, unreachable pages, duplicate
# layers, icon names, slideshow config, the page-type registry)
python -m pytest tests/ -v

# JS — hitLayer()'s pixel-alpha hit testing, including the coarse-pointer
# forgiveness radius
node --test tests/
```

Both run automatically in CI before every deploy — a broken test blocks the
build from going live.

---

## 8. Deploying

Push to `main`. `.github/workflows/deploy.yml` will:
1. Run both test suites
2. Build `dist/` via `airport.py build`
3. Copy the engine + your `images/`/`sprite.svg` in
4. Deploy `dist/` to GitHub Pages

`dist/` and `graph/` are gitignored on purpose — never commit them, CI
regenerates both from `pages.json`/`build/` on every push. See
`docs/PIPELINE.md`'s "what's committed vs. generated" table if you're ever
unsure whether something belongs in git.

---

## 9. Adding a new page type

1. Add `src/pipeline/builders/<type>.py` with `build(page: dict) -> str`,
   using `builders/_shared.py`'s helpers for the parts every page needs.
2. Register it in `src/pipeline/builders/__init__.py`'s `BUILDERS` dict.
3. Add a matching `_check_<type>_type(page, result)` function to
   `src/pipeline/validate.py` and register it in `TYPE_CHECKS`.

Neither `generate_html.py` nor `validate()` itself needs to change — only
the two registries grow.

---

## What's not in these instructions yet

The geospatial zone/grid map model (train station → airport 1 → flight →
airport 2, rooms positioned on a per-zone grid, `create_canvas.py` laying
out Canvas cards by that grid instead of free-form x/y) is still being
designed — schema and `validate.py` adjacency checks aren't built yet.
Current `create_canvas.py` behavior: BFS auto-layout for new pages, with an
optional `"map": {"x", "y"}` free-form override per page if you want to
hand-position something today. This section will get rewritten once the
zone/grid schema is finalized.
