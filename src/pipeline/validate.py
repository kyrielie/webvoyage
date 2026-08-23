#!/usr/bin/env python3
"""
AIRPORT — validate.py
Validates pages.json for structural integrity and common authoring errors.

Can be run standalone or imported and called from airport.py.

Usage
─────
  python validate.py [pages_json] [images_dir]

  pages_json  — path to pages.json          (default: pages.json)
  images_dir  — path to images/ directory   (default: images)

Exit codes
──────────
  0  — no errors (warnings may have been printed)
  1  — one or more errors found
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Icon registry (must match icons.js) ───────────────────────────────────────

VALID_ICONS = {
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
}

# ── Valid page types ───────────────────────────────────────────────────────────
# Derived from TYPE_CHECKS (defined further down) instead of a separate
# hardcoded set, so registering a new type in one place (TYPE_CHECKS) is
# enough — no second set to keep in sync with it.

# Must match generate_from_tree.py's IMAGE_EXTS — otherwise any source art
# copied through with one of the "extra" extensions (webp/gif) will be
# reported as a missing image here even though it's on disk.
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")

# ── Result container ───────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def error(self, msg: str) -> None:
        self.errors.append(f"  ✗  {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(f"  ⚠  {msg}")

    def print_all(self) -> None:
        for w in self.warnings:
            print(w)
        for e in self.errors:
            print(e)

    def summary(self) -> str:
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return ", ".join(parts) if parts else "all checks passed"


# ── Checks ─────────────────────────────────────────────────────────────────────

def _check_page_types(pages: list[dict], result: ValidationResult) -> None:
    """Unknown type values."""
    for page in pages:
        t = page.get("type", "standard")
        if t not in VALID_PAGE_TYPES:
            result.error(
                f"Page '{page['id']}': unknown type '{t}'. "
                f"Valid types: {sorted(VALID_PAGE_TYPES)}"
            )


def _check_graph(pages: list[dict], result: ValidationResult) -> None:
    """Broken hrefs, orphaned pages, dead ends, back-only pages."""
    page_ids = {p["id"] for p in pages}

    incoming: dict[str, list[str]] = {p["id"]: [] for p in pages}
    adj:      dict[str, set[str]]  = {p["id"]: set() for p in pages}

    for page in pages:
        pid = page["id"]
        for btn in page.get("buttons", []):
            href = btn.get("href")
            if not href or href in ("back", "#"):
                continue
            if href not in page_ids:
                result.error(
                    f"{pid} › layer-{btn['layer']:02d}: "
                    f"href '{href}' does not match any page id"
                )
            else:
                incoming[href].append(pid)
                adj[pid].add(href)

    # Root detection
    roots = [pid for pid, inc in incoming.items() if not inc]
    if len(roots) == 0:
        result.error("No root page found — every page has an incoming link (circular graph?)")
    elif len(roots) > 1:
        result.warn(
            f"Multiple pages have no incoming links — "
            f"verify these are all intentional entry points: {roots}"
        )

    # Reachability BFS
    reachable: set[str] = set(roots)
    queue = list(roots)
    while queue:
        node = queue.pop(0)
        for nb in adj.get(node, set()):
            if nb not in reachable:
                reachable.add(nb)
                queue.append(nb)

    for pid in sorted(page_ids - reachable):
        result.error(f"Page '{pid}' is unreachable from any entry point")

    # Back-only pages
    for page in pages:
        btns = page.get("buttons", [])
        if btns and all(b.get("href") == "back" for b in btns):
            result.warn(
                f"Page '{page['id']}' has buttons but all go 'back' — "
                f"player cannot progress from here"
            )


def _check_icons(pages: list[dict], result: ValidationResult) -> None:
    """Icon keys that don't exist in icons.js."""
    for page in pages:
        for btn in page.get("buttons", []):
            icon = btn.get("icon", "")
            if icon and icon not in VALID_ICONS:
                result.error(
                    f"{page['id']} › layer-{btn['layer']:02d}: "
                    f"unknown icon '{icon}' — check icons.js for valid keys"
                )


def _check_layers(pages: list[dict], result: ValidationResult) -> None:
    """Duplicate layer numbers and missing layer field."""
    for page in pages:
        seen: set[int] = set()
        for btn in page.get("buttons", []):
            layer = btn.get("layer")
            if layer is None:
                result.error(
                    f"{page['id']}: button with label '{btn.get('label')}' "
                    f"has no 'layer' field"
                )
                continue
            if layer in seen:
                result.error(
                    f"{page['id']}: duplicate layer number {layer} "
                    f"(appears at least twice)"
                )
            seen.add(layer)


def _check_messages(pages: list[dict], result: ValidationResult) -> None:
    """Buttons with both href and message (message wins, href is silently dead)."""
    for page in pages:
        for btn in page.get("buttons", []):
            if btn.get("href") and btn.get("message"):
                result.warn(
                    f"{page['id']} › layer-{btn['layer']:02d}: "
                    f"has both href '{btn['href']}' and a message — "
                    f"message takes priority; href will never be followed"
                )


def _check_stray_type_blocks(pages: list[dict], result: ValidationResult) -> None:
    """
    Generic, type-agnostic pass: a page carries a `<type>` config block (e.g.
    'slideshow') but its own `type` field doesn't match, so the block will be
    silently ignored by the builder. Runs once for every registered type key
    that also happens to be a page's own dict key — currently just
    'slideshow', but stays generic on purpose so a new page type with its own
    top-level config block (e.g. a future 'hotspotGrid' block) gets this
    check for free without editing this function.
    """
    for page in pages:
        pid = page["id"]
        page_type = page.get("type", "standard")
        for block_key in TYPE_CHECKS:
            if block_key == "standard":
                continue
            if block_key in page and page_type != block_key:
                result.warn(
                    f"Page '{pid}': has a '{block_key}' block but type is "
                    f"'{page_type}'. The block will be ignored. Did you mean "
                    f'to set "type": "{block_key}"?'
                )


def _check_standard_type(page: dict, result: ValidationResult) -> None:
    """No extra config block for standard pages — nothing to check."""
    return


def _check_slideshow_type(page: dict, result: ValidationResult) -> None:
    """
    Slideshow config checks for a single page. Called once per page whose
    `type` is "slideshow" (see _check_by_type / TYPE_CHECKS below) — the
    generic "block present on the wrong type" case is handled once for all
    types by _check_stray_type_blocks, not duplicated per type here.

    Rules
    ─────
    • Pages with type == "slideshow" must have a non-empty 'slideshow.images' list.
    • Numeric fields (interval, fadeDuration) must be positive integers when present.
    """
    pid = page["id"]

    if "slideshow" not in page:
        result.error(
            f"Page '{pid}': type is 'slideshow' but no 'slideshow' config block found"
        )
        return

    ss = page["slideshow"]

    images = ss.get("images")
    if not images:
        result.error(
            f"Page '{pid}': slideshow.images is empty or missing — "
            f"at least one image is required"
        )
    elif not isinstance(images, list):
        result.error(
            f"Page '{pid}': slideshow.images must be a list, got {type(images).__name__}"
        )

    for field_name in ("interval", "fadeDuration"):
        val = ss.get(field_name)
        if val is not None:
            if not isinstance(val, (int, float)) or val <= 0:
                result.error(
                    f"Page '{pid}': slideshow.{field_name} must be a positive number, "
                    f"got {val!r}"
                )

    interval = ss.get("interval", 4000)
    fade     = ss.get("fadeDuration", 1200)
    if isinstance(interval, (int, float)) and isinstance(fade, (int, float)):
        if fade >= interval:
            result.warn(
                f"Page '{pid}': slideshow.fadeDuration ({fade}ms) is >= "
                f"interval ({interval}ms) — slides will overlap before the "
                f"previous one has fully faded"
            )


# Dispatch table for type-specific config-block checks. To support a new
# page type: add its `_check_<type>_type(page, result)` function above and
# register it here + in VALID_PAGE_TYPES. generate_html.py's BUILDERS
# registry is the JS-side twin of this — see webvoyage-framework-plan.md §1.
TYPE_CHECKS = {
    "standard":  _check_standard_type,
    "slideshow": _check_slideshow_type,
}

VALID_PAGE_TYPES = set(TYPE_CHECKS)


def _check_by_type(pages: list[dict], result: ValidationResult) -> None:
    """Dispatch each page to its registered type-specific check, then run
    the generic stray-block pass once across all pages."""
    for page in pages:
        page_type = page.get("type", "standard")
        check_fn = TYPE_CHECKS.get(page_type)
        if check_fn is not None:
            check_fn(page, result)
    _check_stray_type_blocks(pages, result)


def _check_images(
    pages: list[dict],
    images_dir: Path,
    result: ValidationResult,
) -> None:
    """Missing background/layer images, missing slideshow images, orphaned transit files."""
    if not images_dir.is_dir():
        result.warn(
            f"images/ directory not found at '{images_dir}' — "
            f"skipping image checks"
        )
        return

    transit_dir = images_dir / "transit"
    transit_on_disk: set[str] = set()
    if transit_dir.is_dir():
        transit_on_disk = {f.name for f in transit_dir.iterdir() if f.is_file()}

    slideshow_dir = images_dir / "slideshow"

    transit_referenced: set[str] = set()

    for page in pages:
        pid = page["id"]

        # Background image — check every extension the pipeline can produce,
        # not just .png/.jpg (generate_from_tree.py also accepts .webp/.gif).
        if not any((images_dir / f"{pid}-0{ext}").exists() for ext in IMAGE_EXTS):
            result.error(f"Missing background image: images/{pid}-0.*")

        # Layer images
        for btn in page.get("buttons", []):
            lnum = btn.get("layer")
            if lnum is None:
                continue
            if not any((images_dir / f"{pid}-{lnum}{ext}").exists() for ext in IMAGE_EXTS):
                result.error(
                    f"Missing layer image: images/{pid}-{lnum}.* "
                    f"(referenced by {pid} › layer-{lnum:02d})"
                )

            for t in btn.get("transit", []):
                transit_referenced.add(t)
                if transit_on_disk and t not in transit_on_disk:
                    result.error(
                        f"Missing transit image: images/transit/{t} "
                        f"(referenced by {pid} › layer-{lnum:02d})"
                    )

        # Slideshow images
        if page.get("type") == "slideshow":
            ss_images = page.get("slideshow", {}).get("images", [])
            if not slideshow_dir.is_dir():
                if ss_images:
                    result.error(
                        f"Page '{pid}': images/slideshow/ directory not found "
                        f"but {len(ss_images)} slideshow image(s) are referenced"
                    )
            else:
                for img in ss_images:
                    if not (slideshow_dir / img).exists():
                        result.error(
                            f"Page '{pid}': missing slideshow image: "
                            f"images/slideshow/{img}"
                        )

    # Orphaned transit files
    for name in sorted(transit_on_disk - transit_referenced):
        result.warn(
            f"Orphaned transit image not referenced in pages.json: "
            f"images/transit/{name}"
        )


# ── Public API ─────────────────────────────────────────────────────────────────

def validate(
    pages: list[dict],
    images_dir: Path | None = None,
) -> ValidationResult:
    """
    Run all checks and return a ValidationResult.

    Parameters
    ----------
    pages:      The list from pages.json["pages"].
    images_dir: Path to the images/ directory. Pass None to skip image checks.
    """
    result = ValidationResult()
    _check_page_types(pages, result)
    _check_graph(pages, result)
    _check_icons(pages, result)
    _check_layers(pages, result)
    _check_messages(pages, result)
    _check_by_type(pages, result)
    if images_dir is not None:
        _check_images(pages, images_dir, result)
    return result


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    json_path  = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pages.json")
    images_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("images")

    if not json_path.is_file():
        print(f"✗  pages.json not found: {json_path}")
        sys.exit(1)

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"✗  pages.json is not valid JSON: {e}")
        sys.exit(1)

    pages = data.get("pages", [])
    if not pages:
        print("✗  pages.json contains no pages")
        sys.exit(1)

    print(f"\n  Validating {len(pages)} page(s) in {json_path} …\n")

    result = validate(pages, images_dir if images_dir.is_dir() else None)
    result.print_all()

    print(f"\n  {result.summary()}\n")
    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
