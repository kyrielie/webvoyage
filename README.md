# webvoyage

A point-and-click / visual-novel style static site engine — pixel-perfect
alpha-channel hit testing over hand-drawn PNG layers, a VHS-style transit
overlay between pages, an optional VN typewriter dialog, and a CRT/retro
neocities aesthetic. Build-time generator in Python, a thin shared runtime
in native ES modules — no bundler.

## Structure

```
webvoyage/
├── .github/workflows/deploy.yml   ← builds dist/ and deploys to GitHub Pages
├── src/
│   ├── engine/                    ← main.js + split modules, style.css, icons.js
│   └── pipeline/
│       ├── airport.py             ← single entry point (build/tree/html/graph/validate)
│       ├── generate_from_tree.py  ← build/ → pages.json + images/
│       ├── generate_html.py       ← pages.json → *.html (dispatches to builders/)
│       ├── create_graph.py        ← pages.json → Obsidian graph/*.md + tags
│       ├── validate.py            ← pages.json integrity checks
│       └── builders/              ← one module per page type, registry-dispatched
├── build/                         ← (you add this) GUI-organised source art
├── pages.json                     ← (you add this) canonical page data
├── pages.example.json             ← minimal working example — copy to pages.json to start
├── tests/                         ← pytest (validate.py) + node --test (hit-test.js)
├── docs/PIPELINE.md               ← full pipeline docs, schema, how to add a page type
├── dist/                          ← gitignored — CI writes generated HTML+images here
├── graph/                         ← gitignored — regenerate locally, don't commit
└── .nojekyll
```

## Quick start (no art yet)

```bash
cp pages.example.json pages.json
python src/pipeline/airport.py validate pages.json images
python src/pipeline/airport.py html pages.json dist
cp -r src/engine/* dist/
```

`validate` will report missing images (expected — no art is included in this
repo) but `html` will still render working pages you can open locally once
you drop in placeholder PNGs at `dist/images/<id>-0.png` etc.

## With your own art

1. Organise cutout PNGs in `build/` per `docs/PIPELINE.md`'s folder-in-folder
   model (or hand-write `pages.json` directly).
2. `python src/pipeline/airport.py build` — runs tree → validate → html →
   graph in one pass.
3. Push to `main` — the GitHub Action builds and deploys automatically.
   Enable **Settings → Pages → Source: GitHub Actions** once, first time.

## Design notes

- **Retro fixed-aspect-ratio window, responsive chrome.** The art itself is
  never reflowed or cropped at any viewport size — only the black frame
  around it (and tooltip/tap behavior) adapts. See `src/engine/style.css`'s
  `.scene-wrap`/`.scene` rules and the `@media (prefers-reduced-motion)` /
  small-viewport blocks.
- **Touch is additive, not a second UI.** `hit-test.js`'s `hitLayer()` takes
  an optional forgiveness `radius`, used only behind
  `@media (pointer: coarse)`; desktop mouse hit-testing (`radius: 0`) is
  byte-for-byte the original pixel-perfect behavior.
- **Page types are a registry, not an if/elif.** `generate_html.py`'s
  `BUILDERS` and `validate.py`'s `TYPE_CHECKS` are the JS/Python twins of
  the same pattern — see `docs/PIPELINE.md` → "Adding a new page type".

Full framework/audit writeup (source of the design decisions above) lives in
`webvoyage-framework-plan.md` in the repo history / original planning doc.

## Tests

```bash
pip install pytest && python -m pytest tests/ -v
node --test tests/
```

Both run automatically in CI before every deploy.
