/* ═══════════════════════════════════════════════════════════
   hit-test.js — pixel-perfect alpha-channel hit testing

   Split out of the original main.js unchanged in behavior for
   mouse users. The one addition is an optional `radius`: when a
   coarse (touch) pointer is driving, main.js passes a small
   radius so a tap slightly outside a thin cutout's alpha region
   still registers, without changing anything for precise mouse
   input (radius 0 = exact behavior as before).
═══════════════════════════════════════════════════════════ */

export const ALPHA_THRESHOLD = 20;

/* Pixel data is extracted once at image load time into a plain
   Uint8ClampedArray. hitLayer() reads directly from that array
   with index arithmetic — no getImageData in the hot path. */
export function buildCanvas(ld) {
  if (!ld.img || !ld.img.naturalWidth) return;
  const c = document.createElement("canvas");
  c.width = ld.img.naturalWidth;
  c.height = ld.img.naturalHeight;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(ld.img, 0, 0);
  ld.canvas = c;
  ld.pixels = ctx.getImageData(0, 0, c.width, c.height).data;
}

function alphaAt(ld, px, py) {
  if (px < 0 || py < 0 || px >= ld.canvas.width || py >= ld.canvas.height) {
    return 0;
  }
  return ld.pixels[(py * ld.canvas.width + px) * 4 + 3];
}

/**
 * scene: the #scene element (for offsetWidth/offsetHeight scaling)
 * layers: array of layer-descriptor objects with .canvas/.pixels set by buildCanvas
 * sx, sy: pointer position in scene-local CSS pixels
 * options.radius: image-space pixel radius to probe around the exact point
 *   if the exact point misses. 0 (default) = original exact-pixel behavior.
 */
export function hitLayer(scene, layers, sx, sy, { radius = 0 } = {}) {
  const sw = scene.offsetWidth;
  const sh = scene.offsetHeight;

  for (const ld of layers) {
    if (!ld.pixels) continue;
    const scaleX = ld.canvas.width / sw;
    const scaleY = ld.canvas.height / sh;
    const baseX = sx * scaleX;
    const baseY = sy * scaleY;

    if (alphaAt(ld, Math.round(baseX), Math.round(baseY)) > ALPHA_THRESHOLD) {
      return ld;
    }

    if (radius > 0) {
      // Small spiral probe outward — cheap (radius is tiny, ~6px) and only
      // runs when the exact point already missed, so desktop mouse users
      // (radius 0) never pay for this.
      for (let r = 1; r <= radius; r++) {
        for (let dx = -r; dx <= r; dx++) {
          for (let dy = -r; dy <= r; dy++) {
            if (Math.abs(dx) !== r && Math.abs(dy) !== r) continue; // ring only
            const px = Math.round(baseX + dx);
            const py = Math.round(baseY + dy);
            if (alphaAt(ld, px, py) > ALPHA_THRESHOLD) return ld;
          }
        }
      }
    }
  }
  return null;
}
