/* ═══════════════════════════════════════════════════════════
   tooltip.js — hover tooltip

   Behavior for mouse is unchanged from the original main.js.
   New: setPinned(true) switches to a fixed on-screen position
   (styled via .tooltip.pinned in style.css) instead of following
   clientX/clientY — on touch, a cursor-following tooltip ends up
   hidden under the finger that triggered it.
═══════════════════════════════════════════════════════════ */

export function createTooltip(tooltipEl) {
  let mx = 0;
  let my = 0;
  let pinned = false;

  function setPinned(value) {
    pinned = value;
    tooltipEl.classList.toggle("pinned", pinned);
  }

  function position() {
    if (pinned) return; // CSS positions it (see .tooltip.pinned)
    const PAD = 18;
    const TW = tooltipEl.offsetWidth;
    const TH = tooltipEl.offsetHeight;
    const VW = window.innerWidth;
    const VH = window.innerHeight;
    let x = mx + PAD;
    let y = my + PAD;
    if (x + TW > VW - 8) x = mx - TW - PAD;
    if (y + TH > VH - 8) y = my - TH - PAD;
    tooltipEl.style.left = x + "px";
    tooltipEl.style.top = y + "px";
  }

  function updatePointer(clientX, clientY) {
    mx = clientX;
    my = clientY;
    position();
  }

  function show(labelHtml) {
    tooltipEl.innerHTML = labelHtml;
    tooltipEl.classList.add("visible");
    position();
  }

  function hide() {
    tooltipEl.classList.remove("visible");
  }

  return { updatePointer, show, hide, setPinned };
}
