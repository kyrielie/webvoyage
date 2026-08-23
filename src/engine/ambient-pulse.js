/* ═══════════════════════════════════════════════════════════
   ambient-pulse.js — idle glow pulse (opt-in via cfg.pulse)

   Unchanged from the original main.js, parameterized on `layers`
   instead of closing over a module-scoped LAYERS.
═══════════════════════════════════════════════════════════ */

export function ambientPulse(layers) {
  layers.forEach((ld, i) => {
    const col = ld.glow || "#00ffcc";
    setTimeout(() => {
      if (!ld.img) return;
      ld.img.style.transition = "box-shadow 800ms ease, filter 800ms ease";
      ld.img.style.boxShadow = `0 0 12px 3px ${col}55`;
      ld.img.style.filter = "brightness(1.06)";
      setTimeout(() => {
        ld.img.style.boxShadow = "";
        ld.img.style.filter = "";
        ld.img.style.transition = "";
      }, 800);
    }, i * 400);
  });
}
