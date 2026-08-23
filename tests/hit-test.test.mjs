// Fixture-based test for src/engine/hit-test.js's hitLayer().
//
// Only hitLayer() is exercised here — buildCanvas() needs a real <canvas>/
// Image and belongs in a browser/DOM test instead. hitLayer() itself is
// pure given a pixel array + coordinates (scene.offsetWidth/offsetHeight
// scaling, then index arithmetic into ld.pixels), so it's fixture-testable
// with a hand-built 4x4 "image" and a stub scene object — no real DOM
// needed. See webvoyage-framework-plan.md §1/§4: this is the regression
// guard for pixel-perfect desktop hit-testing while the coarse-pointer
// forgiveness radius (§4 item 4) evolves.
//
// Run with: node --test tests/

import { test } from "node:test";
import assert from "node:assert/strict";
import { hitLayer } from "../src/engine/hit-test.js";

// 4x4 RGBA fixture. Alpha channel (index 3 of every 4 bytes) is what
// hitLayer reads. Layout (A = opaque >threshold, . = transparent):
//   . . . .
//   . A A .
//   . A A .
//   . . . .
function makeLayer(id, alphaGrid) {
  const w = alphaGrid[0].length;
  const h = alphaGrid.length;
  const pixels = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      pixels[i] = pixels[i + 1] = pixels[i + 2] = 0;
      pixels[i + 3] = alphaGrid[y][x];
    }
  }
  return {
    id,
    img: {},
    canvas: { width: w, height: h },
    pixels,
  };
}

const OPAQUE = 255;
const TRANSPARENT = 0;

function fourByFourLayer(id) {
  return makeLayer(id, [
    [TRANSPARENT, TRANSPARENT, TRANSPARENT, TRANSPARENT],
    [TRANSPARENT, OPAQUE, OPAQUE, TRANSPARENT],
    [TRANSPARENT, OPAQUE, OPAQUE, TRANSPARENT],
    [TRANSPARENT, TRANSPARENT, TRANSPARENT, TRANSPARENT],
  ]);
}

// Stub scene: offsetWidth/offsetHeight equal to the image's natural size,
// so scene-local coordinates map 1:1 to image-space pixels (scale = 1).
const identityScene = { offsetWidth: 4, offsetHeight: 4 };

test("hitLayer returns the layer when the point is on an opaque pixel", () => {
  const layer = fourByFourLayer("center");
  const hit = hitLayer(identityScene, [layer], 1, 1); // opaque cell
  assert.equal(hit, layer);
});

test("hitLayer returns null when the point is on a transparent pixel", () => {
  const layer = fourByFourLayer("corner");
  const hit = hitLayer(identityScene, [layer], 0, 0); // transparent cell
  assert.equal(hit, null);
});

test("hitLayer respects layer order — first matching layer wins", () => {
  const back = fourByFourLayer("back");
  const front = fourByFourLayer("front");
  const hit = hitLayer(identityScene, [front, back], 1, 1);
  assert.equal(hit, front);
});

test("hitLayer scales scene-local coordinates against natural image size", () => {
  const layer = fourByFourLayer("scaled");
  // Scene rendered at 8x8 CSS pixels (2x the natural 4x4 image) — a click
  // at scene-local (2,2) should map to image-space (1,1), an opaque cell.
  const scaledScene = { offsetWidth: 8, offsetHeight: 8 };
  const hit = hitLayer(scaledScene, [layer], 2, 2);
  assert.equal(hit, layer);
});

test("radius 0 (desktop/mouse default) does not probe neighboring pixels", () => {
  const layer = fourByFourLayer("exact");
  // (0,1) is transparent; the nearest opaque pixel is (1,1), one step away.
  const hit = hitLayer(identityScene, [layer], 0, 1, { radius: 0 });
  assert.equal(hit, null);
});

test("radius > 0 (coarse pointer) finds a nearby opaque pixel the exact point misses", () => {
  const layer = fourByFourLayer("forgiving");
  const hit = hitLayer(identityScene, [layer], 0, 1, { radius: 2 });
  assert.equal(hit, layer);
});

test("radius does not reach across a layer that is genuinely far away", () => {
  const layer = fourByFourLayer("far");
  // Top-left corner (0,0) is 1 pixel diagonally from the nearest opaque
  // cell in an all-transparent border case — use a radius too small to
  // reach it and confirm it still misses.
  const hit = hitLayer(identityScene, [layer], 0, 0, { radius: 0 });
  assert.equal(hit, null);
});
