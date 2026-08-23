#!/usr/bin/env python3
"""
AIRPORT — airport.py
Single entry point for the entire build pipeline.

Commands
────────
  python airport.py build    [build_dir] [repo_dir]
      Full pipeline: tree → pages.json → validate → HTML → graph

  python airport.py tree     [build_dir] [repo_dir]
      Step 1 only: scan build/ tree, write pages.json and copy images

  python airport.py html     [pages_json] [output_dir]
      Step 2 only: render pages.json → HTML files

  python airport.py graph    [pages_json] [output_dir]
      Step 3 only: render pages.json → Obsidian graph/ markdown

  python airport.py validate [pages_json] [images_dir]
      Validate pages.json without writing any files

  python airport.py --help
      Show this message

Pipeline overview
─────────────────
  build/                   ← GUI-organised content tree
      │
      ▼  [tree]
  pages.json               ← canonical data file (edit this by hand)
  images/                  ← flat image directory
      │
      ▼  [validate]
  validation report        ← errors abort the build; warnings are printed
      │
      ▼  [html]
  *.html                   ← one file per page
      │
      ▼  [graph]
  graph/*.md               ← Obsidian vault for visual authoring

Defaults
────────
  build_dir   build/
  repo_dir    .  (pages.json, images/, *.html, graph/ all go here)
  pages_json  pages.json
  images_dir  images/
  output_dir  .
"""

import sys
from pathlib import Path


# ── Helpers ────────────────────────────────────────────────────────────────────

def _divider(label: str) -> None:
    width = 60
    print(f"\n{'─' * width}")
    print(f"  {label}")
    print(f"{'─' * width}\n")


def _abort(message: str, code: int = 1) -> None:
    print(f"\n  ✗  {message}\n")
    sys.exit(code)


# ── Step runners ───────────────────────────────────────────────────────────────

def run_tree(build_dir: Path, repo_dir: Path) -> None:
    """Step 1: scan build/ tree, write pages.json + copy images."""
    from generate_from_tree import main as tree_main

    _divider("Step 1 — Scanning content tree")

    if not build_dir.is_dir():
        _abort(f"build directory not found: {build_dir}")

    # generate_from_tree.main() reads sys.argv, so patch it
    sys.argv = ["generate_from_tree.py", str(build_dir), str(repo_dir)]
    tree_main()


def run_validate(pages_json: Path, images_dir: Path, fatal: bool = True):
    """
    Validate pages.json.

    Parameters
    ----------
    fatal:  If True (pipeline mode), abort on errors.
            If False (standalone), always exit 0 or 1 without raising.

    Returns
    -------
    The ValidationResult, so callers (e.g. cmd_validate) don't need to
    re-read and re-validate pages.json a second time just to get ok/errors.
    """
    import json
    from validate import validate, ValidationResult

    _divider("Validate — checking pages.json integrity")

    if not pages_json.is_file():
        _abort(f"pages.json not found: {pages_json}")

    try:
        data = json.loads(pages_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _abort(f"pages.json is not valid JSON: {e}")

    pages = data.get("pages", [])
    if not pages:
        _abort("pages.json contains no pages")

    print(f"  Validating {len(pages)} page(s) in {pages_json} …\n")

    img_dir = images_dir if images_dir.is_dir() else None
    result: ValidationResult = validate(pages, img_dir)
    result.print_all()

    print(f"\n  {result.summary()}")

    if not result.ok and fatal:
        _abort("Validation errors found — aborting pipeline. Fix pages.json and re-run.")

    return result


def run_html(pages_json: Path, output_dir: Path) -> None:
    """Step 2: render pages.json → HTML files."""
    from generate_html import main as html_main

    _divider("Step 2 — Generating HTML")

    sys.argv = ["generate_html.py", str(pages_json), str(output_dir)]
    html_main()


def run_graph(pages_json: Path, output_dir: Path) -> None:
    """Step 3: render pages.json → Obsidian graph markdown."""
    from create_graph import create_obsidian_library

    _divider("Step 3 — Generating Obsidian graph")

    graph_dir = output_dir / "graph"
    print(f"  Writing graph to {graph_dir.resolve()} …\n")
    create_obsidian_library(str(pages_json), output_dir=str(graph_dir))


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_build(args: list[str]) -> None:
    """Full pipeline: tree → validate → html → graph."""
    build_dir  = Path(args[0]) if len(args) > 0 else Path("build")
    repo_dir   = Path(args[1]) if len(args) > 1 else Path(".")

    pages_json = repo_dir / "pages.json"
    images_dir = repo_dir / "images"

    print(f"\n  AIRPORT build pipeline")
    print(f"  build_dir : {build_dir.resolve()}")
    print(f"  repo_dir  : {repo_dir.resolve()}")

    run_tree(build_dir, repo_dir)
    run_validate(pages_json, images_dir, fatal=True)
    run_html(pages_json, repo_dir)
    run_graph(pages_json, repo_dir)

    _divider("Build complete")
    print(f"  ✓  pages.json written")
    print(f"  ✓  HTML pages generated in {repo_dir.resolve()}/")
    print(f"  ✓  Obsidian graph written to {(repo_dir / 'graph').resolve()}/\n")


def cmd_tree(args: list[str]) -> None:
    build_dir = Path(args[0]) if len(args) > 0 else Path("build")
    repo_dir  = Path(args[1]) if len(args) > 1 else Path(".")
    run_tree(build_dir, repo_dir)


def cmd_html(args: list[str]) -> None:
    pages_json = Path(args[0]) if len(args) > 0 else Path("pages.json")
    output_dir = Path(args[1]) if len(args) > 1 else Path(".")
    run_html(pages_json, output_dir)


def cmd_graph(args: list[str]) -> None:
    pages_json = Path(args[0]) if len(args) > 0 else Path("pages.json")
    output_dir = Path(args[1]) if len(args) > 1 else Path(".")
    run_graph(pages_json, output_dir)


def cmd_validate(args: list[str]) -> None:
    pages_json = Path(args[0]) if len(args) > 0 else Path("pages.json")
    images_dir = Path(args[1]) if len(args) > 1 else Path("images")
    result = run_validate(pages_json, images_dir, fatal=False)
    # Exit code reflects validity (0 = ok, 1 = errors). Reuses the result
    # from run_validate instead of re-parsing and re-validating pages.json
    # a second time (the previous version did the whole pass twice).
    sys.exit(0 if result.ok else 1)


def cmd_help(_args: list[str]) -> None:
    print(__doc__)


# ── Dispatch ───────────────────────────────────────────────────────────────────

COMMANDS: dict[str, object] = {
    "build":    cmd_build,
    "tree":     cmd_tree,
    "html":     cmd_html,
    "graph":    cmd_graph,
    "validate": cmd_validate,
    "--help":   cmd_help,
    "-h":       cmd_help,
    "help":     cmd_help,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        valid = [k for k in COMMANDS if not k.startswith("-") and k != "help"]
        print(
            f"\n  Usage: python airport.py <command> [args]\n"
            f"  Commands: {', '.join(valid)}\n"
            f"  Run 'python airport.py --help' for details.\n"
        )
        sys.exit(1)

    command  = sys.argv[1]
    args     = sys.argv[2:]
    COMMANDS[command](args)


if __name__ == "__main__":
    main()
