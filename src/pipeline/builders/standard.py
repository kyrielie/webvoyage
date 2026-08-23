"""builders/standard.py — the original point-and-click page template."""

from . import _shared


def build(page: dict) -> str:
    """Standard point-and-click page."""
    page_id   = page["id"]
    buttons   = page.get("buttons", [])
    head      = _shared.build_head(page)
    imgs_html = _shared.build_imgs_html(page_id, buttons)
    body_top  = _shared.build_body_common_top()
    transit_tpl = _shared.build_transit_template()

    return f'''<!doctype html>
<html lang="en" style="background:#000">
{head}
  <body>
{body_top}

    <main class="scene-wrap">
      <div class="scene" id="scene">
{imgs_html}
      </div>
    </main>

{transit_tpl}

    <!-- VN overlay markup + engine + click intercept are all handled by main.js.
         No per-page VN scripts needed — edit main.js or style.css to change VN behaviour. -->
    <script type="module" src="main.js"></script>
  </body>
</html>
'''
