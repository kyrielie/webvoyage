#!/usr/bin/env python3
"""
AIRPORT — Step 1: Tree → pages.json
Walks a build/ directory tree, extracts page/button structure, writes pages.json,
and copies all images into a flat images/ directory.

Run once after organising your content in a GUI file manager.
After this you can hand-edit pages.json freely and never touch the tree again.

Usage
─────
  python generate_from_tree.py [build_dir] [repo_dir]

  build_dir  — root of the GUI-organised content tree  (default: build)
  repo_dir   — root of your repo where pages.json and images/ will go  (default: .)

Image layout written to repo_dir
──────────────────────────────────
  images/
    {page}-0.png          ← background
    {page}-{N}.png        ← clickable layer N
    {page}-holes.png      ← holes mask (copy manually or skip if absent)
    transit/
      {page}-{N}-{name}   ← transit frames, namespaced to avoid collisions

Sidecar files recognised inside button folders
───────────────────────────────────────────────
  icon.txt    one icon key from AVAILABLE_ICONS  (default: auto-selected from label)
  label.txt   tooltip display text               (default: prettified href/folder name)
  message.txt visual-novel text for leaf buttons (omit for nav buttons)
"""

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

# ── Icon registry ──────────────────────────────────────────────────────────────
AVAILABLE_ICONS = [
    "air-transportation", "arrivingflights", "baggagecheckin", "baggageclaim",
    "baggagelockers", "bar", "barbershop-beautysalon", "barbershop", "beautysalon",
    "bus", "car-rental", "cashier", "coatcheck", "coffee-shop", "currencyexchange",
    "departingflights", "down-arrow", "drinkingfountain", "elevator",
    "escalator-down", "escalator-up", "escalator", "exit", "fireextinguisher",
    "firstaid", "forward-and-left-arrow", "forward-and-right-arrow",
    "forward-andright-arrow", "ground-transportation", "heliport",
    "hotel-information", "information", "left-and-down-arrow", "leftarrow",
    "litter-disposal", "lostandfound", "mail", "no-entry", "no-smoking",
    "nodogs", "noparking", "nursery", "parking", "rail-transportation",
    "restaurant", "right-and-down-arrow", "right-arrow", "shops", "smoking",
    "stairs-down", "stairs-up", "stairs", "taxi", "telephone", "ticketpurchase",
    "toilets-men", "toilets-women", "toilets", "uparrow", "waitingroom",
    "water-transportation",
]

DEFAULT_ICON = "information"
IMAGE_EXTS   = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# ── Icon selection ─────────────────────────────────────────────────────────────

def _tokenize(s: str) -> set[str]:
    """Lowercase words from a hyphen/underscore/space-separated string."""
    return set(re.split(r"[-_ ]+", s.lower()))


def pick_icon(label: str) -> str:
    """Return the AVAILABLE_ICONS entry whose tokens best overlap with label tokens."""
    label_tokens = _tokenize(label)
    best_icon  = DEFAULT_ICON
    best_score = 0
    for icon in AVAILABLE_ICONS:
        score = len(_tokenize(icon) & label_tokens)
        if score > best_score:
            best_score = score
            best_icon  = icon
    return best_icon


# ── File helpers ───────────────────────────────────────────────────────────────

def read_txt(path: Path, default: str = "") -> str:
    return path.read_text(encoding="utf-8").strip() if path.is_file() else default


def read_icon(btn_dir: Path, label: str) -> str:
    """Use icon.txt if present and valid, otherwise pick automatically from label."""
    val = read_txt(btn_dir / "icon.txt")
    if val in AVAILABLE_ICONS:
        return val
    return pick_icon(label)


def read_label(btn_dir: Path, href: Optional[str]) -> str:
    """Use label.txt if present, otherwise prettify the href (or folder name)."""
    explicit = read_txt(btn_dir / "label.txt")
    if explicit:
        return explicit
    base = href if href else btn_dir.name
    return re.sub(r"[-_]+", " ", base).strip().title()


def read_page_message(page_dir: Path) -> Optional[str]:
    """Read message.txt from page directory for leaf pages."""
    msg = read_txt(page_dir / "message.txt")
    return msg if msg else None


def load_existing_pages(pages_json: Path) -> dict[str, dict]:
    """
    Parse an existing pages.json into a two-level lookup:
      { page_id: { "message": <str|None>,
                   "buttons": { layer_num: { "label": ..., "icon": ..., "message": ... } } } }
    Only values that are non-None strings are stored so callers can use
    ``existing.get(key)`` as a truthiness check.
    """
    if not pages_json.is_file():
        return {}
    try:
        data = json.loads(pages_json.read_text(encoding="utf-8"))
    except Exception:
        return {}
    result: dict[str, dict] = {}
    for pg in data.get("pages", []):
        pid = pg.get("id")
        if not pid:
            continue
        btn_map: dict[int, dict] = {}
        for btn in pg.get("buttons", []):
            layer = btn.get("layer")
            if layer is None:
                continue
            btn_map[layer] = {
                k: btn[k]
                for k in ("label", "icon", "message")
                if btn.get(k) is not None
            }
        result[pid] = {
            "message": pg.get("message"),  # may be None
            "buttons": btn_map,
        }
    return result


def find_background(directory: Path) -> Optional[Path]:
    # Prefer the canonical *-0.ext pattern.
    for f in directory.iterdir():
        if f.is_file() and re.match(r".+-0\.(png|jpg|jpeg)$", f.name, re.IGNORECASE):
            return f
    # Fall back: if there is exactly one image in the folder, treat it as the
    # background even if its name does not end in -0.  This handles pages whose
    # content hasn't been fully organised yet.
    sole = [
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    return sole[0] if len(sole) == 1 else None


def find_layer_image(btn_dir: Path, page_id: str) -> Optional[Path]:
    pattern = re.compile(
        rf"^{re.escape(page_id)}-([1-9]\d*)\.(png|jpg|jpeg)$", re.IGNORECASE
    )
    for f in btn_dir.iterdir():
        if f.is_file() and pattern.match(f.name):
            return f
    return None


def layer_number(layer_path: Path) -> int:
    m = re.search(r"-(\d+)\.(png|jpg|jpeg)$", layer_path.name, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def get_transit_images(btn_dir: Path) -> list[Path]:
    transit_dir = btn_dir / "transit"
    if not transit_dir.is_dir():
        return []
    return sorted(
        f for f in transit_dir.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS
    )


def find_nested_page(btn_dir: Path) -> Optional[Path]:
    for item in sorted(btn_dir.iterdir()):
        if item.is_dir() and item.name != "transit" and find_background(item):
            return item
    return None


# ── Discovery ──────────────────────────────────────────────────────────────────

def _is_button_folder(d: Path, parent_name: str) -> bool:
    """True if d contains a layer image belonging to parent_name (i.e. it's a button folder)."""
    pattern = re.compile(
        rf"^{re.escape(parent_name)}-([1-9]\d*)\.(png|jpg|jpeg)$", re.IGNORECASE
    )
    return any(pattern.match(f.name) for f in d.iterdir() if f.is_file())


def collect_all_pages(root: Path) -> dict[str, Path]:
    """Return {page_id: page_dir} for every directory containing a *-0.png.
    Button folders (those containing layer images for their parent page) are
    not descended into, so nested pages with the same folder name as a button
    folder in another page do not cause false duplicate errors."""
    pages: dict[str, Path] = {}

    def walk(d: Path) -> None:
        if find_background(d) is not None:
            if d.name in pages:
                raise ValueError(
                    f"Duplicate page id '{d.name}':\n"
                    f"  {pages[d.name]}\n  {d}\n"
                    f"  Each page folder must have a unique name."
                )
            pages[d.name] = d
        for child in sorted(d.iterdir()):
            if child.is_dir() and not _is_button_folder(child, d.name):
                walk(child)

    walk(root)
    return pages


# ── Image copying ──────────────────────────────────────────────────────────────

def copy_image(src: Path, dest: Path, seen: dict[str, Path], warnings: list[str]) -> None:
    """
    Copy src to dest, warning if a *different source within this run* already
    claimed that destination name (a real collision).

    NOTE: `seen` only tracks names claimed during the current run, so a plain
    `dest.exists()` check would also be true for leftover files from a
    *previous* run — meaning an edited source image would be silently
    skipped (never re-copied) any time `images/` isn't wiped before a
    rebuild. We instead always copy when this run hasn't already claimed the
    name, so edited art always propagates. shutil.copy2 overwrites in place.
    """
    if dest.name in seen:
        if seen[dest.name] != src:
            warnings.append(
                f"  ⚠  Skipped duplicate image name '{dest.name}'\n"
                f"       kept:    {seen[dest.name]}\n"
                f"       skipped: {src}"
            )
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    seen[dest.name] = src


# ── Tree analysis ──────────────────────────────────────────────────────────────

def build_page_record(
    page_dir: Path,
    page_id: str,
    all_pages: dict[str, Path],
    parent_id: Optional[str],
    images_dir: Path,
    transit_dir: Path,
    copy_seen: dict[str, Path],
    warnings: list[str],
    existing_pages: dict[str, dict],
) -> dict:
    """
    Parse one page directory into a JSON-ready dict and copy its images.
    """
    bg = find_background(page_dir)

    # Copy background
    dest_bg = images_dir / f"{page_id}-0{bg.suffix}"
    copy_image(bg, dest_bg, copy_seen, warnings)

    # Copy holes mask if present
    for candidate in page_dir.iterdir():
        if re.match(rf"^{re.escape(page_id)}-holes\.", candidate.name, re.IGNORECASE):
            copy_image(candidate, images_dir / candidate.name, copy_seen, warnings)

    # Collect button subfolders
    raw_buttons: list[tuple[Path, Path]] = []
    for item in sorted(page_dir.iterdir()):
        if not item.is_dir() or item.name == "transit":
            continue
        layer = find_layer_image(item, page_id)
        if layer is None:
            continue
        raw_buttons.append((item, layer))

    raw_buttons.sort(key=lambda x: layer_number(x[1]))

    buttons = []
    for btn_dir, layer in raw_buttons:
        lnum    = layer_number(layer)
        btn_id  = btn_dir.name
        message = read_txt(btn_dir / "message.txt") or None

        # Resolve href first — label and icon depend on it
        if btn_id == "back":
            href = parent_id  # None becomes null in JSON → generator uses "#"
        elif btn_id in all_pages:
            href = btn_id
        else:
            # Any non-transit subfolder inside the button directory is treated
            # as a link target — its name is the page id, whether or not that
            # page has been fully set up yet.
            nested_dirs = [
                d for d in btn_dir.iterdir()
                if d.is_dir() and d.name != "transit"
            ]
            href = nested_dirs[0].name if nested_dirs else None

        label = read_label(btn_dir, href)
        icon  = read_icon(btn_dir, label)

        # Preserve label / icon / message from existing pages.json if present
        existing_btn = existing_pages.get(page_id, {}).get("buttons", {}).get(lnum, {})
        if "label" in existing_btn:
            label = existing_btn["label"]
        if "icon" in existing_btn:
            icon = existing_btn["icon"]
        if "message" in existing_btn:
            message = existing_btn["message"]

        # Copy layer image
        dest_layer = images_dir / f"{page_id}-{lnum}{layer.suffix}"
        copy_image(layer, dest_layer, copy_seen, warnings)

        # Copy transit images — namespaced to avoid cross-page collisions
        transit_filenames = []
        for img in get_transit_images(btn_dir):
            dest_name = f"{page_id}-{lnum}-{img.name}"
            copy_image(img, transit_dir / dest_name, copy_seen, warnings)
            transit_filenames.append(dest_name)

        # Default message only for truly dead-end buttons:
        # no href, no transit frames, and no explicit message.txt
        if href is None and not transit_filenames and message is None:
            message = "nothing to see here!"

        buttons.append({
            "layer":   lnum,
            "icon":    icon,
            "label":   label,
            "href":    href,
            "transit": transit_filenames,
            "message": message,
        })

    # Check if this is a leaf page (no buttons)
    is_leaf = len(buttons) == 0
    page_message = read_page_message(page_dir) if is_leaf else None

    # Preserve page-level message from existing pages.json if already set
    existing_page_msg = existing_pages.get(page_id, {}).get("message")
    if existing_page_msg is not None:
        page_message = existing_page_msg

    return {
        "id":      page_id,
        "title":   f"Airport \u2014 {page_id.replace('-', ' ').title()}",
        "buttons": buttons,
        "message": page_message,  # Only present for leaf pages; None/null for others
    }


# ── Recursive processor ────────────────────────────────────────────────────────

def process_tree(
    page_dir: Path,
    parent_id: Optional[str],
    all_pages: dict[str, Path],
    images_dir: Path,
    transit_dir: Path,
    copy_seen: dict[str, Path],
    warnings: list[str],
    records: list[dict],
    visited: set[str],
    existing_pages: dict[str, dict],
) -> None:
    page_id = page_dir.name
    if page_id in visited:
        return
    visited.add(page_id)

    record = build_page_record(
        page_dir, page_id, all_pages, parent_id,
        images_dir, transit_dir, copy_seen, warnings, existing_pages,
    )
    records.append(record)
    print(f"  ✓  {page_id:<30} {len(record['buttons'])} button(s)" + 
          (" [leaf]" if len(record['buttons']) == 0 else ""))

    # Recurse into nested pages found inside button subfolders
    for item in sorted(page_dir.iterdir()):
        if not item.is_dir() or item.name == "transit":
            continue
        if find_layer_image(item, page_id) is None:
            continue
        nested = find_nested_page(item)
        if nested and nested.name not in visited:
            process_tree(
                nested, page_id, all_pages,
                images_dir, transit_dir, copy_seen, warnings,
                records, visited, existing_pages,
            )


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    build_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build")
    repo_dir  = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")

    if not build_dir.is_dir():
        print(f"✗  build directory not found: {build_dir}")
        sys.exit(1)

    images_dir  = repo_dir / "images"
    transit_dir = images_dir / "transit"
    images_dir.mkdir(parents=True, exist_ok=True)
    transit_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Scanning {build_dir.resolve()} …\n")

    try:
        all_pages = collect_all_pages(build_dir)
    except ValueError as e:
        print(f"✗  {e}")
        sys.exit(1)

    if not all_pages:
        print("  ✗  No pages found. Each page folder must contain a *-0.png file.")
        sys.exit(1)

    print(f"  Found {len(all_pages)} page(s): {', '.join(sorted(all_pages))}\n")

    records:   list[dict]  = []
    visited:   set[str]    = set()
    copy_seen: dict[str, Path] = {}
    warnings:  list[str]   = []

    # Load existing pages.json so hand-edited label/icon/message values are preserved
    out_path = repo_dir / "pages.json"
    existing_pages = load_existing_pages(out_path)
    if existing_pages:
        print(f"  ↺  Preserving existing label/icon/message values from {out_path}\n")

    # Process top-level pages first (establishes root pages with no parent)
    top_level = sorted(
        d for d in build_dir.iterdir()
        if d.is_dir() and find_background(d) is not None
    )

    for page_dir in top_level:
        process_tree(
            page_dir, None, all_pages,
            images_dir, transit_dir, copy_seen, warnings,
            records, visited, existing_pages,
        )

    # Warn about unreachable pages
    unreachable = set(all_pages) - visited
    if unreachable:
        for name in sorted(unreachable):
            warnings.append(f"  ⚠  Page '{name}' was not reachable from any top-level page.")

    # Write pages.json
    # schemaVersion is preserved from an existing file if present, otherwise
    # starts at 1. Costs nothing today; the day the page shape changes (the
    # WebP/alpha-mask split, or a new page type with a required field), a
    # migration script has something to key off instead of guessing from
    # field presence. `tree` never bumps this itself — only a deliberate
    # migration should.
    existing_schema_version = 1
    if out_path.is_file():
        try:
            existing_payload = json.loads(out_path.read_text(encoding="utf-8"))
            existing_schema_version = existing_payload.get("schemaVersion", 1)
        except (json.JSONDecodeError, OSError):
            pass
    payload = {"schemaVersion": existing_schema_version, "pages": records}
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\n  ✓  {out_path}")
    print(f"  ✓  Images copied to {images_dir}/")

    if warnings:
        print()
        for w in warnings:
            print(w)

    print()


if __name__ == "__main__":
    main()