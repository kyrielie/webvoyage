#!/usr/bin/env python3
"""
AIRPORT — Step 2: pages.json → HTML files
Pure template renderer. Reads pages.json, writes one .html per page.

This is the script you re-run whenever pages.json changes.
It has no knowledge of the build/ folder tree — pages.json is the only input.

Usage
─────
  python generate_html.py [pages_json] [output_dir]

  pages_json  — path to pages.json              (default: pages.json)
  output_dir  — where .html files are written   (default: .)

pages.json schema
──────────────────
Standard page:

  {
    "id":      "mainhall",              // used as filename, image prefix, link target
    "title":   "Airport — Main Hall",  // browser <title> and OG tag
    "message": "You are in the hall.", // optional: auto-plays VN typewriter on load
    "pulse":   false,                  // optional: enable ambient layer glow pulse
    "buttons": [
      {
        "layer":   1,                   // integer → layer-01, images/mainhall-1.png
        "icon":    "departingflights",  // key from icons.js ICONS object
        "label":   "Departures",        // tooltip text alongside the icon
        "href":    "gate",              // page id to navigate to (or null)
        "transit": ["mainhall-1-frame1.png"],  // filenames inside images/transit/
        "message": null                 // VN text string, or null for nav buttons
      }
    ]
  }

Slideshow page (type: "slideshow"):

  {
    "id":    "airplane",
    "type":  "slideshow",
    "title": "Airport — On the plane",
    "message": "The engines hum.",
    "slideshow": {
      "images":       ["airplane-sky-1.png", "airplane-clouds.png"],
      "interval":     4000,       // ms between crossfades
      "fadeDuration": 1200,       // ms for the opacity transition
      "loop":         true,       // restart after last image
      "drift":        true        // slow horizontal pan (images should be ~120% wide)
    },
    "buttons": [ ... ]            // same schema as standard buttons
  }

  Slideshow images live in images/slideshow/.
  Buttons on a slideshow page work identically to standard pages —
  main.js handles hit-testing and navigation; the inline slideshow
  script only touches #slide-a and #slide-b.

Notes
─────
  • href: null renders as href="#" (clickable but goes nowhere).
  • message: non-null overrides navigation — clicking shows the VN text box instead.
    main.js reads message from PAGE_CONFIG layers and sets vnOnly automatically.
  • VN CSS lives in style.css; VN engine + intercept live in main.js.
    No per-page VN scripts or styles are injected by this generator.
  • layer-00 / *-0.png is the base background image.
  • pulse: true in a page entry enables the ambient glow pulse (off by default).

Page-type builders live in builders/ (one module per type, dispatched by a
registry — see builders/__init__.py). This file is deliberately just the
dispatcher + CLI now; adding a new page type shouldn't require editing it.
"""

import json
import sys
from pathlib import Path

from builders import BUILDERS


def build_html(page: dict) -> str:
    """Dispatch to the registered builder for this page's type."""
    page_type = page.get("type", "standard")
    builder = BUILDERS.get(page_type)
    if builder is None:
        raise ValueError(
            f"No builder registered for page type '{page_type}' "
            f"(page '{page.get('id')}'). Registered types: {sorted(BUILDERS)}"
        )
    return builder(page)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    json_path  = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pages.json")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")

    if not json_path.is_file():
        print(f"✗  pages.json not found: {json_path}")
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    pages = data.get("pages", [])

    if not pages:
        print("✗  pages.json contains no pages.")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Generating {len(pages)} page(s) → {output_dir.resolve()}/\n")

    for page in pages:
        html     = build_html(page)
        out_path = output_dir / f"{page['id']}.html"
        out_path.write_text(html, encoding="utf-8")

        page_type    = page.get("type", "standard")
        vn_count     = sum(1 for b in page.get("buttons", []) if b.get("message"))
        has_page_msg = bool(page.get("message"))
        type_tag     = f"  [{page_type}]" if page_type != "standard" else ""

        print(
            f"  ✓  {page['id'] + '.html':<35}"
            f"{len(page.get('buttons', []))} button(s)"
            + type_tag
            + (f"  [page message]" if has_page_msg else "")
            + (f"  [{vn_count} VN]" if vn_count else "")
        )

    print(f"\n  Done.\n")


if __name__ == "__main__":
    main()
