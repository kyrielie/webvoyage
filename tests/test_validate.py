# pytest suite for src/pipeline/validate.py
#
# validate()'s check functions are pure (list[dict] -> ValidationResult, no
# I/O), so these fixtures build minimal in-memory pages.json shapes rather
# than fixture files on disk. See webvoyage-framework-plan.md §1.
#
# Run from the repo root:
#   pip install pytest
#   python -m pytest tests/ -v

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "pipeline"))

import validate as v  # noqa: E402


def page(id, buttons=None, **extra):
    p = {"id": id, "buttons": buttons or []}
    p.update(extra)
    return p


def btn(layer, href=None, icon="information", label="btn", **extra):
    b = {"layer": layer, "href": href, "icon": icon, "label": label}
    b.update(extra)
    return b


# ── graph checks ────────────────────────────────────────────────────────────

def test_broken_href_is_an_error():
    pages = [page("root", [btn(1, href="nowhere")])]
    result = v.validate(pages)
    assert not result.ok
    assert any("nowhere" in e for e in result.errors)


def test_valid_href_is_not_an_error():
    pages = [page("root", [btn(1, href="second")]), page("second")]
    result = v.validate(pages)
    assert result.ok


def test_unreachable_page_is_an_error():
    # "unreachable" means: has an incoming link (so it's not flagged as an
    # extra root), but that link only comes from a subgraph the BFS from
    # the real root(s) never reaches. A small disconnected 2-cycle does
    # this cleanly — orphan_a and orphan_b each have an incoming link (from
    # each other), so neither looks like a root, but neither is reachable
    # from "root" either.
    pages = [
        page("root", [btn(1, href="hall")]),
        page("hall"),
        page("orphan_a", [btn(1, href="orphan_b")]),
        page("orphan_b", [btn(1, href="orphan_a")]),
    ]
    result = v.validate(pages)
    assert not result.ok
    assert any("orphan_a" in e and "unreachable" in e for e in result.errors)
    assert any("orphan_b" in e and "unreachable" in e for e in result.errors)


def test_back_only_page_is_a_warning_not_an_error():
    pages = [
        page("root", [btn(1, href="dead")]),
        page("dead", [btn(1, href="back")]),
    ]
    result = v.validate(pages)
    assert result.ok  # back-only is a warning, not fatal
    assert any("dead" in w and "back" in w for w in result.warnings)


def test_no_root_page_is_an_error():
    # every page has an incoming link -> circular, no entry point
    pages = [
        page("a", [btn(1, href="b")]),
        page("b", [btn(1, href="a")]),
    ]
    result = v.validate(pages)
    assert not result.ok
    assert any("root" in e.lower() for e in result.errors)


# ── layer checks ─────────────────────────────────────────────────────────────

def test_duplicate_layer_is_an_error():
    pages = [page("root", [btn(1, href=None), btn(1, href=None)])]
    result = v.validate(pages)
    assert not result.ok
    assert any("duplicate layer" in e for e in result.errors)


def test_missing_layer_field_is_an_error():
    pages = [page("root", [{"href": None, "icon": "information", "label": "x"}])]
    result = v.validate(pages)
    assert not result.ok
    assert any("no 'layer' field" in e for e in result.errors)


# ── icon checks ──────────────────────────────────────────────────────────────

def test_unknown_icon_is_an_error():
    pages = [page("root", [btn(1, href=None, icon="totally-not-a-real-icon")])]
    result = v.validate(pages)
    assert not result.ok
    assert any("unknown icon" in e for e in result.errors)


def test_known_icon_is_fine():
    pages = [page("root", [btn(1, href=None, icon="departingflights")])]
    result = v.validate(pages)
    assert result.ok


# ── message/href interaction ─────────────────────────────────────────────────

def test_href_and_message_together_is_a_warning():
    pages = [page("root", [btn(1, href="somewhere", message="hi")]), page("somewhere")]
    result = v.validate(pages)
    assert result.ok
    assert any("message takes priority" in w for w in result.warnings)


# ── page type registry / slideshow checks ────────────────────────────────────

def test_unknown_page_type_is_an_error():
    pages = [page("root", type="not-a-real-type")]
    result = v.validate(pages)
    assert not result.ok
    assert any("unknown type" in e for e in result.errors)


def test_slideshow_page_without_block_is_an_error():
    pages = [page("root", type="slideshow")]
    result = v.validate(pages)
    assert not result.ok
    assert any("no 'slideshow' config block" in e for e in result.errors)


def test_slideshow_page_with_empty_images_is_an_error():
    pages = [page("root", type="slideshow", slideshow={"images": []})]
    result = v.validate(pages)
    assert not result.ok
    assert any("slideshow.images is empty" in e for e in result.errors)


def test_valid_slideshow_page_passes():
    pages = [
        page(
            "root",
            type="slideshow",
            slideshow={"images": ["a.png", "b.png"], "interval": 4000, "fadeDuration": 1200},
        )
    ]
    result = v.validate(pages)
    assert result.ok


def test_fade_duration_gte_interval_is_a_warning():
    pages = [
        page(
            "root",
            type="slideshow",
            slideshow={"images": ["a.png"], "interval": 1000, "fadeDuration": 1000},
        )
    ]
    result = v.validate(pages)
    assert result.ok
    assert any("fadeDuration" in w for w in result.warnings)


def test_slideshow_block_on_standard_page_is_a_warning():
    # type-agnostic stray-block check (_check_stray_type_blocks) — a
    # 'slideshow' block sitting on a page whose type is still "standard".
    pages = [page("root", slideshow={"images": ["a.png"]})]
    result = v.validate(pages)
    assert result.ok
    assert any("block will be ignored" in w for w in result.warnings)


def test_type_checks_registry_matches_valid_page_types():
    # VALID_PAGE_TYPES is derived from TYPE_CHECKS — this just guards
    # against someone editing one without the other in the future.
    assert v.VALID_PAGE_TYPES == set(v.TYPE_CHECKS)
    assert "standard" in v.TYPE_CHECKS
    assert "slideshow" in v.TYPE_CHECKS
