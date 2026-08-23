/* ═══════════════════════════════════════════════════════════
   vn-engine.js — visual-novel typewriter overlay + click intercept

   Unchanged in behavior from the original main.js. Parameterized
   on `hitTest(sx, sy)` instead of reading window.hitLayer, and on
   `scene`/`cfg` instead of closing over module-scoped variables —
   the caller (main.js orchestrator) already has all three.

   CSS lives in style.css. Overlay markup is injected into #scene
   at runtime (clipped to the layer-00 image frame, behind
   scanlines/vignette via z-index 50). The engine always boots
   when cfg.message or any layer.message is present.
═══════════════════════════════════════════════════════════ */

import { playClickSound } from "./audio.js";

export function initVNEngine(scene, cfg, hitTest) {
  const VN_MESSAGES = {};
  (cfg.layers || []).forEach((l) => {
    if (l.message) VN_MESSAGES[l.id] = l.message;
  });

  const hasPageMsg = !!(cfg.message || "").trim();
  const hasLayerMsg = Object.keys(VN_MESSAGES).length > 0;
  if (!hasPageMsg && !hasLayerMsg) return;

  if (!document.getElementById("vn-overlay")) {
    const overlay = document.createElement("div");
    overlay.id = "vn-overlay";
    overlay.className = "vn-overlay";
    overlay.innerHTML =
      '<div class="vn-box">' +
      '<button class="vn-close" aria-label="Close"' +
      " onclick=\"document.getElementById('vn-overlay').classList.remove('active')\">✕</button>" +
      '<div id="vn-text" class="vn-text"></div>' +
      '<span id="vn-caret" class="vn-caret"></span>' +
      '<div id="vn-continue" class="vn-continue">▼ click or press space</div>' +
      "</div>";
    scene.appendChild(overlay);
  }

  const overlay = document.getElementById("vn-overlay");
  const textEl = document.getElementById("vn-text");
  const caretEl = document.getElementById("vn-caret");
  const contEl = document.getElementById("vn-continue");

  let _timer = null;
  let _done = false;
  let _text = "";

  function typeText(text, speed) {
    _text = text;
    _done = false;
    textEl.textContent = "";
    caretEl.classList.remove("hidden");
    contEl.classList.remove("show");
    let i = 0;
    clearInterval(_timer);
    _timer = setInterval(() => {
      if (i < text.length) {
        const char = text[i++];
        textEl.textContent += char;
        if (char !== " " && char !== "\n") {
          playClickSound();
        }
      } else {
        finish();
      }
    }, speed);
  }

  function finish() {
    clearInterval(_timer);
    textEl.textContent = _text;
    _done = true;
    caretEl.classList.add("hidden");
    contEl.classList.add("show");
  }

  function dismiss() {
    overlay.classList.remove("active");
    clearInterval(_timer);
  }

  window.showVNMessage = function (text, speed) {
    overlay.classList.add("active");
    typeText(text, speed || 28);
  };

  overlay.addEventListener("click", () => {
    if (!_done) finish();
    else dismiss();
  });
  document.addEventListener("keydown", (e) => {
    if (!overlay.classList.contains("active")) return;
    if (e.key === " " || e.key === "Enter") {
      if (!_done) finish();
      else dismiss();
    }
    if (e.key === "Escape") dismiss();
  });

  // Only wire the layer click-intercept when there are layer messages.
  // Capture-phase so it fires before the navigation click handler.
  if (Object.keys(VN_MESSAGES).length) {
    scene.addEventListener(
      "click",
      (e) => {
        const rect = scene.getBoundingClientRect();
        const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
        if (!hit) return;
        const msg = VN_MESSAGES[hit.id];
        if (!msg) return;
        e.stopImmediatePropagation();
        window.showVNMessage(msg);
      },
      true,
    );
  }

  // Page-level message (cfg.message) — small delay so the scene image has
  // a moment to appear first.
  if (hasPageMsg) {
    setTimeout(() => window.showVNMessage(cfg.message.trim()), 400);
  }
}
