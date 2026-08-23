# PIPELINE.md

How content flows through webvoyage, from hand-organised art to a deployed
site.

```
build/                   ← GUI-organised content tree (source of truth for art)
    │
    ▼  python src/pipeline/airport.py tree
pages.json                ← canonical data file — hand-editable, git-tracked
images/                    ← flat image directory, copied from build/
    │
    ▼  python src/pipeline/airport.py validate
validation report          ← errors abort the build; warnings are printed
    │
    ▼  python src/pipeline/airport.py html
dist/*.html                ← one file per page (gitignored, CI-only)
    │
    ▼  python src/pipeline/airport.py graph
graph/*.md + *.canvas      ← Obsidian vault for visual authoring (gitignored)
```

`python src/pipeline/airport.py build` runs all four steps in order.

## Commands

```
python src/pipeline/airport.py build    [build_dir] [repo_dir]
python src/pipeline/airport.py tree     [build_dir] [repo_dir]
python src/pipeline/airport.py html     [pages_json] [output_dir]
python src/pipeline/airport.py graph    [pages_json] [output_dir]
python src/pipeline/airport.py validate [pages_json] [images_dir]
```

Defaults: `build_dir=build/`, `repo_dir=.`, `pages_json=pages.json`,
`images_dir=images/`, `output_dir=.`.

## What's committed vs. generated

| Path | Committed? | Why |
|---|---|---|
| `build/` | Yes | Hand-organised source art — this *is* the content |
| `pages.json` | Yes | Canonical, hand-editable data file |
| `src/` | Yes | Engine + pipeline source |
| `dist/*.html`, `dist/images/` | **No** | CI output from `airport.py build`; committing it recreates "which copy is live" ambiguity |
| `graph/` | **No** | Generated Obsidian vault — `graph/.obsidian/` is per-author workspace state, not project content |

CI (`.github/workflows/deploy.yml`) builds `dist/` fresh on every push and
uploads it directly as the GitHub Pages artifact — `dist/` never needs to
touch the repo.

**Git LFS**: turn it on for `build/**/*.png` (and `.webp` once source art
moves to WebP) from the very first commit. Hand-drawn PNG cutouts don't
diff-compress the way text does, and retrofitting LFS onto history later
requires a rewrite.

## `pages.json` schema

```jsonc
{
  "schemaVersion": 1,
  "pages": [
    {
      "id": "mainhall",              // filename, image prefix, link target
      "title": "Airport — Main Hall",
      "message": "You are in the hall.",  // optional: auto-plays VN typewriter on load
      "pulse": false,                // optional: ambient layer glow pulse
      "buttons": [
        {
          "layer": 1,                 // integer -> layer-01, images/mainhall-1.png
          "icon": "departingflights", // key from icons.js ICONS object
          "label": "Departures",
          "href": "gate",             // page id, "back", or null
          "transit": ["mainhall-1-frame1.png"],  // filenames in images/transit/
          "message": null             // VN text, or null for a nav button
        }
      ]
    }
  ]
}
```

Slideshow pages (`"type": "slideshow"`) add a `slideshow` block — see the
docstring at the top of `src/pipeline/generate_html.py` for the full shape,
or `pages.example.json` in the repo root for a minimal working example.

`schemaVersion` is written by `generate_from_tree.py` and preserved across
re-runs of `tree`. Bump it by hand only as part of a deliberate migration
(e.g. the WebP/alpha-mask split, or a new page type with a required field) —
`tree` itself never bumps it automatically.

## Adding a new page type

1. Add `src/pipeline/builders/<type>.py` with a `build(page: dict) -> str`
   function. Use `builders/_shared.py`'s helpers (`build_head`,
   `build_imgs_html`, `build_body_common_top`, `build_transit_template`) for
   the parts every page type needs.
2. Register it in `src/pipeline/builders/__init__.py`'s `BUILDERS` dict.
3. Add a `_check_<type>_type(page, result)` function to
   `src/pipeline/validate.py` and register it in `TYPE_CHECKS`.

That's the whole surface area — `generate_html.py` and `validate.py`'s
`validate()` function never need to change for a new type; only their
registries grow.

## One rough edge worth knowing about

`generate_from_tree.py`'s `build_page_record()` resolves a button's `href`
by checking whether the button id matches a known page id, falling back to
treating a nested subfolder as an implicit link target. `tree` only
preserves hand-edited `label`/`icon`/`message` values across re-runs —
**not** `href`. If you hand-edit an `href` in `pages.json` and then
rearrange `build/`, the next `tree` run can silently change that link
target back to whatever the folder structure implies. If a link ever
changes unexpectedly after a `tree` run, this is why.

## Tests

```
pip install pytest
python -m pytest tests/ -v      # validate.py checks
node --test tests/               # hit-test.js fixture test
```
