# webvoyage — framework, repo, workflow, and audit (round 2)

Read `analysis.md` (trusted) and the older `webvoyage-documentation.md` (repomix-based,
stale in places — e.g. its "transit-tpl missing" and "dead slideshow code" findings
are both already fixed in the code you gave me: `generate_html.py` emits the template
on every page, and the slideshow builder is fully implemented). This round is based on
reading the **actual source** in `Archive.zip` (`airport.py`, `generate_from_tree.py`,
`generate_html.py`, `create_graph.py`, `validate.py`, `main.js`, `style.css`, `icons.js`)
— not inference from the docs. I did not receive `images/` or `build/`, so nothing here
depends on pixel content.

Attached alongside this doc: **`webvoyage-pipeline-patched.zip`** — your pipeline
scripts with six real bugs fixed (see §4 and its `AUDIT-CHANGELOG.md`). Pure logic
fixes, no art or content touched. Diff and cherry-pick.

---

## 1. Fleshing the pipeline out into a real framework

You already have the right shape: a build-time generator (Python) + a thin shared
runtime (`main.js`). "Framework" here doesn't mean rewriting it — it means making the
two things that are currently monolithic (`main.js`, `generate_html.py`) extensible
without every new feature turning into a bigger single file.

### Split `main.js` into modules

Right now `main.js` is 564 lines doing hit-testing, tooltip, transit/VHS, audio, VN
engine, and ambient pulse in one IIFE. That's fine at this size, but you're about to
add touch support (§4) and possibly new page types — both want to hook into hit-testing
without re-reading the whole file. Split along the seams that already exist as comment
dividers in the file:

```
src/engine/
  hit-test.js      ← buildCanvas(), hitLayer() — exported, already exposed as window.hitLayer
  tooltip.js        ← positionTooltip/showTooltip/hideTooltip
  transit.js        ← showTransit() + VHS noise/band/bar
  vn-engine.js       ← initVN(), initDialog(), showVNMessage
  audio.js           ← playClickSound(), shared AudioContext
  ambient-pulse.js   ← ambientPulse()
  main.js            ← orchestrator: reads PAGE_CONFIG, wires the above together
```

Use native ES modules (`<script type="module" src="engine/main.js">`) rather than a
bundler — you have no build step for JS today and don't need one; native `import`
across 6 small files is free and keeps the "no build tooling beyond Python" property
you already have. One real payoff: `slideshow.js` (currently inlined per-page by
`generate_html.py`, §"page types" below) only needs to load on slideshow pages, so
non-slideshow pages ship less JS — directly serves analysis.md §5's load-time goal.

### Split `generate_html.py`'s builders

`_build_html_standard` / `_build_html_slideshow` are dispatched by `page_type` today.
That's the right pattern — formalize it as a registry instead of an `if/elif` so a
third page type (you'll likely want one — see below) is additive, not a bigger
function:

```python
# builders/__init__.py
BUILDERS = {
    "standard":  standard.build,
    "slideshow": slideshow.build,
}
# generate_html.py
def build_html(page):
    builder = BUILDERS.get(page.get("type", "standard"))
    if builder is None:
        raise ValueError(f"no builder registered for type '{page['type']}'")
    return builder(page)
```

`validate.py`'s `_check_slideshow` should become `_check_by_type`, dispatched the same
way, so adding a page type means touching one registry in two files, not grep-ing for
every place `"slideshow"` is hardcoded (currently: `generate_html.py` ×3,
`validate.py` ×1, `VALID_PAGE_TYPES` ×1 — five places today for one type).

A likely third type worth designing room for now: a **hotspot-grid / directory page**
(e.g. an airport terminal map, gate list) that's mostly text/icon links rather than
art layers — useful for accessibility too (see §4), since a real page of `<a>` tags
gives you free keyboard nav on at least some pages without touching the pixel engine.

### Schema versioning

Add `"schemaVersion": 1` to the top of `pages.json`. Costs nothing today; the moment
you do the WebP/alpha-mask split from analysis.md §5, or add a page type, you'll want
a migration script to know what shape it's reading instead of guessing from field
presence.

### Tests

`validate.py`'s check functions are pure (`list[dict] → ValidationResult`, no I/O) —
they're already unit-test-shaped. A ~150-line `pytest` file covering broken hrefs,
unreachable pages, duplicate layers, the slideshow checks, and the icon check would
catch regressions for free and is a natural first thing to add to CI alongside the
GitHub Action from analysis.md §2. `main.js`'s `hitLayer()` is also pure given a pixel
array + coordinates — worth a tiny fixture-based test (a 4×4 known-alpha PNG) once
you're doing the touch-hitbox-dilation work in §4, so you don't regress pixel-perfect
desktop hit-testing while adding touch forgiveness.

---

## 2. Repo design for a fresh `github.com/kyrielie/webvoyage`

The older doc's biggest finding was **three parallel, divergent engine copies** in the
current repo (root, `website/`, `daytime/generate/`) with no clear live version. The
single most valuable thing about starting fresh is: **don't bring that forward.** Only
the `daytime/generate` engine (what's in `Archive.zip`) goes into the new repo. If you
want the older two-page root site preserved for nostalgia, put it in a separate
`webvoyage-archive` repo or an orphan `legacy` branch — not in `main`.

```
webvoyage/
├── .github/
│   └── workflows/
│       └── deploy.yml              ← from analysis.md §2, unchanged
├── src/
│   ├── engine/                     ← §1 split: main.js modules, style.css, icons.js, sprite.svg
│   └── pipeline/
│       ├── airport.py
│       ├── generate_from_tree.py
│       ├── generate_html.py
│       ├── create_graph.py
│       ├── validate.py
│       └── builders/                ← §1 registry: standard.py, slideshow.py
├── build/                          ← GUI-organised content tree (source of truth for art)
├── pages.json                      ← canonical data, hand-editable
├── tests/
│   └── test_validate.py
├── docs/
│   └── PIPELINE.md
├── dist/                           ← gitignored — CI writes generated HTML+images here
├── graph/                          ← gitignored — regenerate locally, don't commit
├── .gitignore
├── .nojekyll                       ← flagged by the older doc, still worth adding day 1
└── README.md
```

**What's committed vs. generated**, since this is the thing that bit the old repo:

| Path | Committed? | Why |
|---|---|---|
| `build/` | Yes | Hand-organised source art — this *is* the content |
| `pages.json` | Yes | Canonical, hand-editable data file |
| `src/` | Yes | Engine + pipeline source |
| `dist/*.html`, `dist/images/` | **No** | CI output from `airport.py build`; committing it re-creates the "which copy is live" ambiguity the moment someone forgets to rebuild before pushing |
| `graph/` | **No** | Generated Obsidian vault. Also: `graph/.obsidian/` holds your personal Obsidian workspace state (open panes, plugin config) — that's per-author machine state, not project content; committing it is how repos end up with the kind of stray non-deployed weight the older doc flagged in §6 |

One practical wrinkle with `dist/` being gitignored: GitHub Pages needs *something* to
serve. The `deploy.yml` from analysis.md §2 already handles this correctly — it builds
in the Action and uploads `dist/` as the Pages artifact directly, so `dist/` never
needs to touch the repo at all. That's strictly better than committing generated
output; keep that design.

**Git LFS**: hand-drawn PNG cutout art for 50+ pages, each potentially several layers,
adds up fast in git's object store (PNGs don't diff-compress the way text does — every
edit is effectively a new blob). Turn on LFS for `build/**/*.png` (and `.webp` once you
do the analysis.md §5 split) from the very first commit of the fresh repo — retrofitting
LFS onto history later requires a history rewrite, so this is a one-time decision that's
much cheaper to make now than in six months.

---

## 3. Improving the folder-in-folder + Obsidian-graph workflow

Two separate problems here, worth naming separately: **authoring** (organizing
`build/`) and **visualizing** (understanding the resulting graph). You said the
drag-and-drop folder model itself is fine, the Obsidian graph is fine for *seeing*
structure, but you want to move blocks around and currently can't — that's specifically
an Obsidian-graph limitation, not a `build/` limitation, so the fix belongs there.

### Why Obsidian's Graph View can't do what you want

`create_graph.py` currently writes one Markdown note per page with `[[wikilinks]]`
between them. Obsidian's **Graph View** renders these as a force-directed graph —
nodes settle wherever the physics simulation puts them, and while you *can* drag a
node in Graph View, that position **isn't saved**; reopening the vault re-runs the
simulation and everything moves again. That's the actual reason it feels
un-arrangeable — it's not a bug in your generator, it's what Graph View is for
(exploration, not layout).

### Fix: emit an Obsidian Canvas alongside the graph notes

Obsidian has a second, different feature for this: **Canvas** (`.canvas` files,
JSON-based, built into modern Obsidian — no plugin needed). Canvas nodes have
explicit, persistent `x`/`y`/`width`/`height` — you drag a card, close Obsidian,
reopen it, and it's still where you put it. That's exactly "move blocks around and
have it stick."

Concretely: have `create_graph.py` (or a new sibling script) additionally write
`graph/webvoyage.canvas`, with one card per page (linking to that page's `.md` note
via a `file` node, or embedding the message text directly via a `text` node) and one
edge per `href`. Auto-layout it once on generation (a simple layered/tree layout by
BFS depth from root pages is enough — you don't need anything fancy, just non-overlapping
starting positions), then **never overwrite positions on regeneration** — only add
new-page nodes and new-edge connections, leaving existing node positions untouched, the
same "preserve hand-edits" philosophy `generate_from_tree.py` already uses for
labels/icons/messages. That reuse of an existing pattern (additive, never clobbers
manual work) is the important part — it's the same trust model you already rely on for
`build/` → `pages.json`.

This gives you: Graph View for "explore the shape," Canvas for "arrange and keep."

### Improving the graph notes themselves

Independent of Canvas, the current per-page notes are thin — I strengthened
`create_graph.py` in the patched zip (§4/`AUDIT-CHANGELOG.md` item 6) to add:
- YAML frontmatter (`type`, `incoming-links`, `button-count`, `tags`) so Graph View
  can **color/filter by tag** (`root`, `dead-end`, `back-only`, `type/slideshow`) —
  right now every node is visually identical regardless of role
- `back` buttons shown instead of silently dropped, so a hub page's "everything loops
  back here" structure is actually visible in the graph instead of looking like a set
  of dead ends
- broken hrefs surfaced inline in the note (`⚠ broken href`), not just in `validate`'s
  terminal output

### On the folder-in-folder model itself

Re-reading `generate_from_tree.py` with the actual code in hand, I'd narrow
analysis.md §3's suggestion. The meta.yaml consolidation is still reasonable *if* you
personally are the one filling in `build/` and find `label.txt`/`icon.txt`/`message.txt`
tedious. But I'd hold off unless that's actually the friction — the code has a
real, unrelated rough edge that matters more regardless of which format you pick:

`build_page_record()` resolves a button's `href` by checking `btn_id in all_pages`,
and falls back to treating a nested subfolder as an implicit link target. That's clever
for the common case, but it means **a button folder's `href` is inferred from folder
structure with no explicit field to override it** unless you hand-edit `pages.json`
afterward and then never re-run `tree` (since tree preserves hand-edits only for
`label`/`icon`/`message`, *not* `href` — rearranging `build/` can silently change link
targets on the next `tree` run in a way the "preserves hand-edits" guarantee doesn't
protect you from). If folder rearrangement ever produces a surprising link change, this
inference is why — worth being aware of before consolidating fields, since a
meta.yaml/json could also just let you *pin* an explicit `href` per button folder,
which the current per-file format has no clean place for either.

---

## 4. Python/JS audit + responsive & touch design

### Bugs found (patched zip attached)

Read every script end to end rather than skimming for the specific things
analysis.md flagged as "risk areas." Six real bugs, all fixed in
`webvoyage-pipeline-patched.zip` (full reasoning in its `AUDIT-CHANGELOG.md`):

1. **`generate_from_tree.py` — stale-image bug.** `copy_image()` checks
   `dest.exists()` against the filesystem, which is also true for leftovers from a
   *previous* run of `tree`. Practical effect: if you edit a PNG in `build/` and
   re-run `python airport.py tree` **without first deleting `images/`**, the edited
   art is silently *not* copied — `tree` reports nothing wrong, and you'd only notice
   because the live page looks unchanged. This is the one I'd fix first; it's the kind
   of bug that costs you an afternoon of "why isn't my edit showing up."
2. **`validate.py` — extension gap.** Only checks `.png`/`.jpg` for background/layer
   images, but `generate_from_tree.py` happily accepts `.webp`/`.gif` source art too.
   This directly undermines analysis.md §5's WebP recommendation — the moment you
   switch source art to WebP, `validate` starts reporting false "missing image" errors
   on every page.
3. **`airport.py` — `cmd_validate` does the validation pass twice** (once via
   `run_validate`, then re-parses and re-validates from scratch again just for the exit
   code). Not wrong, just wasteful and a needless second file read.
4. **`generate_html.py` — label escaping gap.** Button `label` text is interpolated
   into a JS template literal; only backticks were escaped, not `${`. A `label.txt`
   containing `${...}` gets evaluated as a live JS expression at page load instead of
   rendered as text. Low real-world risk since you author your own labels, but it's a
   correctness bug in the template renderer either way, and worth fixing before this
   becomes a "framework" other people might author content for.
5. **`main.js` — noisy back-button prefetch.** `href: "back"` renders as
   `"javascript:history.back()"`; the prefetch guard only excludes `"#"`, so every
   back-button click fires `fetch("javascript:history.back()")`, which always rejects.
   Harmless (caught by `.catch(()=>{})`) but spams a console error on the single most
   common navigation action in the game.
6. **`create_graph.py`** — direct `page['title']`/`button['label']` indexing means a
   hand-authored `pages.json` entry missing a field (which `PIPELINE.md` explicitly
   allows — "add the page object to the `pages` array" without going through `tree`)
   throws `KeyError` and **aborts the entire graph step**, not just that one page. Also
   folded in the graph-quality improvements from §3 while I was in this file.

### Responsive design + touch, keeping the retro fixed-aspect-ratio look

The good news from reading `main.js` closely: **hit-testing is already
resolution-independent.** `hitLayer()` scales the pointer position by
`scene.offsetWidth`/`offsetHeight` against the image's *natural* pixel dimensions —
it doesn't assume any particular CSS size. That means responsive layout work doesn't
require touching the hit-testing math at all, only the CSS around `.scene` and the
interaction model in `main.js`. Concretely, and in priority order:

1. **Fix the viewport-clipping bug first** — it's the one actual rendering bug in the
   current CSS, not just a missing feature. `.scene` has `max-width: var(--scene-max)`
   but no matching height constraint, while `.scene-wrap` is `100vh` with `overflow:
   hidden` on `<body>`. On a short/landscape viewport where the scaled scene is taller
   than the window, the bottom — potentially including a button — clips off with no
   way to reach it. Fix: constrain `.scene-wrap` height explicitly and let `.scene`
   respect `max-height: 100vh` alongside its existing `max-width`, so the whole retro
   frame **letterboxes** (shrinks to fit, pillarboxed/letterboxed with your existing
   black background) rather than clipping. This is also exactly how you keep "the old
   retro single aspect ratio design" on every device: the art itself is never
   reflowed or cropped, only the black frame around it resizes. No new design work,
   just making the existing intent (a fixed-AR window centered in the viewport) hold
   at every viewport size instead of only the ones you happened to test.
2. **Tap-to-preview interaction**, gated behind `@media (pointer: coarse)`. The pieces
   for this already exist and are decoupled from mouse specifically — `applyHover()`
   and `showTooltip()` are driven by generic pointer coordinates, not `mousemove`.
   Adding a `pointerdown` listener that, on a coarse pointer, shows hover+tooltip on
   first tap of a *new* layer and only fires the existing click/navigate path on a
   second tap of the *same* layer (or after a short "confirm" tooltip state) is wiring
   work on top of what's there, not new hit-testing logic.
3. **Reposition the tooltip on touch.** It currently follows `clientX/clientY`, which
   on touch means it appears under the finger that triggered it. Behind the same
   `pointer: coarse` query, pin `.tooltip` to a fixed on-screen location (a bottom bar)
   instead of cursor-following.
4. **Forgiving tap targets without touching the art.** You can't resize hand-drawn
   alpha cutouts, but `hitLayer()` can be extended to try a small spiral of nearby
   pixels (±6px, say) when the initiating pointer event is coarse, before giving up —
   purely additive to the existing function, invisible to mouse users, no visual
   change, and directly addresses the WCAG/iOS ~44px tap-target guidance the older doc
   flagged without needing to touch a single PNG.
5. **`touch-action: manipulation` on `.scene`** — stops the browser's own
   pinch/double-tap-zoom from intercepting a tap meant for the game, one line of CSS.
6. **`prefers-reduced-motion: reduce`** around the scanline/flicker/VHS-noise
   animations and the per-character typewriter sound. Also a one-block CSS/JS change
   and fixes a real accessibility gap (currently zero `@media` queries exist in
   `style.css` at all — confirmed by grep, matching what the older doc found and
   nothing in the current build has changed that since).

None of this requires a second "mobile" version of the art or layout — the retro
window stays exactly as designed at every breakpoint; only the chrome around it
(frame sizing, tooltip position, tap forgiveness) adapts. That's the throughline for
all six items above.
