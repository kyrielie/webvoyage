# Patched-pipeline changelog

This folder is your `daytime/generate` pipeline (from `Archive.zip`) with six
bugs fixed — found by reading the actual source, not inferred from
`PIPELINE.md`. Nothing here touches art, `pages.json` content, or the visual
design; it's pure logic fixes. Diff these against your originals and cherry-pick.

Full writeup with reasoning for each is in the main report
(`webvoyage-framework-plan.md`), §4. Short version:

1. **`generate_from_tree.py` — `copy_image()`**
   Checked `dest.exists()` on disk, which is also true for leftovers from a
   *previous* run. Result: if you edit a source PNG in `build/` and re-run
   `tree` without first deleting `images/`, the edited art is silently
   **not** copied — the stale file just sits there and `tree` reports
   nothing wrong. Now compares against this run's own `seen` map instead,
   so edits always propagate.

2. **`validate.py` — `_check_images()`**
   Only checked for `.png`/`.jpg` on background and layer images, even
   though `generate_from_tree.py` happily copies `.webp`/`.gif` source art
   (`IMAGE_EXTS` includes them). Any page authored with WebP source images
   — which is exactly what `analysis.md` §5 recommends for load time — would
   fail validation with false "missing image" errors. Now checks all four
   extensions.

3. **`airport.py` — `cmd_validate()`**
   Called `run_validate()`, then re-read and re-validated `pages.json` a
   second time from scratch just to get an exit code. Wasteful, and a
   theoretical TOCTOU if the file changes between the two reads. Now
   `run_validate()` returns its `ValidationResult` and `cmd_validate()`
   reuses it.

4. **`generate_html.py` — `_build_layers_js()` label escaping**
   `label` is interpolated into a JS template literal (backtick string).
   Only backticks were escaped — a `label.txt` containing `${...}` would be
   evaluated as a live JS expression at page load instead of rendered as
   text. Now escapes backslashes, backticks, *and* `${`.

5. **`main.js` — `showTransit()` prefetch**
   "Back" buttons render as `href: "javascript:history.back()"`. The
   prefetch guard only excluded `"#"`, so every back-button click fired a
   `fetch("javascript:history.back()")` that always rejects — harmless, but
   it spams a console error on every single back click. Now also excludes
   `javascript:` hrefs from the prefetch.

6. **`create_graph.py`** — larger pass, see the report for the full
   rationale:
   - Defensive `.get()` everywhere instead of `page['title']` /
     `button['label']` — a hand-authored `pages.json` entry missing a field
     (which `PIPELINE.md` explicitly says is allowed) used to raise
     `KeyError` and abort the *entire* graph step, not just that page.
   - `href: "back"` buttons were silently dropped from the note entirely;
     a page whose only exits are "back" rendered identically to a page with
     no buttons at all. Now shown as `↩ (back)`.
   - Broken hrefs (already caught by `validate.py`) now also show inline in
     the graph note as `⚠ broken href`, so it's visible without switching
     to the terminal.
   - Added YAML frontmatter (`type`, `incoming-links`, `button-count`,
     `tags: [root, dead-end, back-only, type/…]`) so Obsidian's Graph View
     can filter/color by tag instead of every node looking identical.
