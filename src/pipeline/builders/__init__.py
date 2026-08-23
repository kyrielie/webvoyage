"""
builders — one module per page `type`, dispatched by a registry.

To add a new page type:
  1. Add a sibling module here (e.g. hotspot_grid.py) with a build(page) -> str
     function, using builders/_shared.py's helpers for the parts every page
     type needs (head, imgs, transit template, common body top).
  2. Register it in BUILDERS below.
  3. Add its config-shape checks to validate.py's TYPE_CHECKS registry
     (see validate.py) and its name to VALID_PAGE_TYPES there.

That's the whole surface area — generate_html.py itself never needs to
change again for a new type.
"""

from . import standard
from . import slideshow

BUILDERS = {
    "standard":  standard.build,
    "slideshow": slideshow.build,
}
