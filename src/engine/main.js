/* ═══════════════════════════════════════════════════════════
   AIRPORT / webvoyage — main.js  (shared across all pages)
   Page-specific config lives in each HTML file as:
     window.PAGE_CONFIG = { name, layers, message? }

   Loaded as a module (<script type="module" src="main.js">).
   Orchestrates the split-out engine pieces:
     hit-test.js, tooltip.js, transit.js, audio.js,
     ambient-pulse.js, vn-engine.js

   Touch/coarse-pointer additions vs the original single-file
   main.js (see webvoyage-framework-plan.md §4):
     - hitLayer gets a small forgiveness radius on coarse pointers
     - tooltip pins to a fixed position instead of following a
       finger that isn't there
     - first tap on a layer previews (hover + tooltip) instead of
       immediately navigating; a second tap on the SAME layer
       commits — hover-to-discover has no touch equivalent, so
       this gives touch users the same "what is this" step mouse
       users get for free from hover.
   Desktop mouse behavior (pointer: fine) is unchanged.
═══════════════════════════════════════════════════════════ */

import { buildCanvas, hitLayer } from "./hit-test.js";
import { createTooltip } from "./tooltip.js";
import { showTransit } from "./transit.js";
import { playClickSound } from "./audio.js";
import { ambientPulse } from "./ambient-pulse.js";
import { initVNEngine } from "./vn-engine.js";

(function () {
  "use strict";

  const cfg = window.PAGE_CONFIG || {};
  const LAYERS = (cfg.layers || []).map((l) => ({ ...l }));

  const scene = document.getElementById("scene");
  const tooltipEl = document.getElementById("tooltip");
  if (!scene || !tooltipEl) return;

  LAYERS.forEach((ld) => {
    ld.img = document.getElementById(ld.id);
    ld.canvas = null;
    ld.pixels = null;
  });

  LAYERS.forEach((ld) => {
    if (!ld.img) return;
    ld.img.addEventListener("load", () => buildCanvas(ld));
    if (ld.img.complete) buildCanvas(ld);
  });

  const isCoarsePointer = window.matchMedia("(pointer: coarse)").matches;
  const HIT_RADIUS = isCoarsePointer ? 6 : 0;

  function hitTest(sx, sy) {
    return hitLayer(scene, LAYERS, sx, sy, { radius: HIT_RADIUS });
  }
  // Kept for backward-compat with any hand-authored page scripts that
  // relied on the old global (the original main.js exposed this too).
  window.hitLayer = hitTest;

  const tooltip = createTooltip(tooltipEl);
  tooltip.setPinned(isCoarsePointer);
  document.documentElement.classList.toggle("coarse-pointer", isCoarsePointer);

  function applyHover(ld) {
    ld.img.classList.add("hovered");
  }
  function removeHover(ld) {
    ld.img.classList.remove("hovered");
  }

  /* ── Pointer move (hover discovery — desktop, and any coarse
     browsers that do fire a pointermove before a tap) ────────*/
  let activeLayer = null;

  scene.addEventListener("pointermove", (e) => {
    tooltip.updatePointer(e.clientX, e.clientY);
    const rect = scene.getBoundingClientRect();
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
    if (hit === activeLayer) return;
    if (activeLayer) removeHover(activeLayer);
    if (hit) {
      applyHover(hit);
      tooltip.show(hit.label);
      scene.classList.add("on-button");
      document.body.style.cursor = "pointer";
    } else {
      tooltip.hide();
      scene.classList.remove("on-button");
      document.body.style.cursor = "";
    }
    activeLayer = hit;
  });

  scene.addEventListener("pointerleave", () => {
    if (activeLayer) {
      removeHover(activeLayer);
      activeLayer = null;
    }
    tooltip.hide();
    scene.classList.remove("on-button");
    document.body.style.cursor = "";
  });

  /* ── Click / tap ─────────────────────────────────────────*/
  let transitActive = false;
  // Coarse-pointer tap-to-preview state: first tap on a layer just shows
  // the hover/tooltip; a second tap on the SAME layer commits to
  // navigation. Reset whenever a different layer is tapped or the
  // pointer leaves.
  let awaitingConfirm = null;

  scene.addEventListener("click", (e) => {
    if (transitActive) return;
    const rect = scene.getBoundingClientRect();
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
    if (!hit) {
      awaitingConfirm = null;
      return;
    }

    if (isCoarsePointer && awaitingConfirm !== hit) {
      awaitingConfirm = hit;
      applyHover(hit);
      tooltip.show(hit.label);
      scene.classList.add("on-button");
      return; // preview only — wait for a second tap to commit
    }
    awaitingConfirm = null;

    // If this layer is VN-only, let the VN intercept handle it — no transit.
    if (hit.vnOnly) return;

    transitActive = true;
    hit.img.classList.add("pressed");
    playClickSound();

    setTimeout(() => {
      hit.img.classList.remove("pressed");
      const imgs = Array.isArray(hit.transitImage)
        ? hit.transitImage
        : [hit.transitImage || ""];
      showTransit(hit.href, imgs);
    }, 320);
  });

  /* ── Back-navigation / bfcache recovery ─────────────────*/
  window.addEventListener("pageshow", (e) => {
    if (!e.persisted) return;
    const leftover = document.getElementById("transit-overlay");
    if (leftover) leftover.remove();
    transitActive = false;
  });

  /* ── Ambient idle glow pulse (opt-in via cfg.pulse) ──────*/
  if (cfg.pulse === true) {
    setTimeout(() => {
      ambientPulse(LAYERS);
      setInterval(() => ambientPulse(LAYERS), 5000);
    }, 2500);
  }

  /* ── Visual novel engine (page + layer messages) ─────────*/
  initVNEngine(scene, cfg, hitTest);
})();
