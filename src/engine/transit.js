/* ═══════════════════════════════════════════════════════════
   transit.js — VHS-style loading transition between pages

   Extracted from the original main.js unchanged, with the
   prefetch fix from the audit (javascript: hrefs, i.e. "back"
   buttons, are no longer fetch()'d).
═══════════════════════════════════════════════════════════ */

export function showTransit(href, transitImgs) {
  if (!Array.isArray(transitImgs)) transitImgs = [transitImgs];

  /* ── Prefetch destination page images ──────────────────── */
  // "back" buttons render href as "javascript:history.back()" (see
  // generate_html.py). That's not a real page to prefetch — fetch()-ing
  // it always rejects and just spams the console on every back click.
  const isRealHref = href && href !== "#" && !href.startsWith("javascript:");
  if (isRealHref) {
    fetch(href)
      .then((r) => r.text())
      .then((html) => {
        const doc = new DOMParser().parseFromString(html, "text/html");
        doc.querySelectorAll("#scene img.layer[src]").forEach((img) => {
          new Image().src = new URL(img.getAttribute("src"), href).href;
        });
      })
      .catch(() => {});
  }

  // Clone the inert <template> from the HTML shell — avoids innerHTML and
  // keeps the overlay markup inspectable in DevTools without triggering a nav.
  const tpl = document.getElementById("transit-tpl");
  const overlay = tpl.content.cloneNode(true).firstElementChild;
  document.body.appendChild(overlay);

  // Set the dynamic first-slide src after appending (avoids a double request).
  const photoEl = overlay.querySelector("#transit-photo");
  photoEl.src = transitImgs[0] || "";
  photoEl.style.transition = "opacity 120ms ease";

  requestAnimationFrame(() =>
    requestAnimationFrame(() => overlay.classList.add("transit-visible")),
  );

  /* ── Slideshow ──────────────────────────────────────── */
  const totalSlides = transitImgs.length;
  let currentSlide = 0;

  function advanceSlide(pct) {
    if (totalSlides < 2) return;
    const target = Math.min(
      Math.floor((pct / 100) * totalSlides),
      totalSlides - 1,
    );
    if (target === currentSlide) return;
    currentSlide = target;
    photoEl.style.opacity = "0";
    setTimeout(() => {
      photoEl.src = transitImgs[currentSlide];
      photoEl.style.opacity = "1";
    }, 120);
  }

  /* ── VHS noise canvas ───────────────────────────────── */
  const noiseCanvas = overlay.querySelector("#transit-noise");
  const nCtx = noiseCanvas.getContext("2d");
  const NW = 320,
    NH = 180;
  noiseCanvas.width = NW;
  noiseCanvas.height = NH;

  let noiseRaf = null;
  let noiseFrame = 0;
  let trackY = -1;
  let trackTTL = 0;

  function drawNoise() {
    noiseFrame++;
    if (noiseFrame % 2 === 0) {
      const imgData = nCtx.createImageData(NW, NH);
      const d = imgData.data;

      if (trackTTL <= 0 && Math.random() < 0.05) {
        trackY = Math.floor(Math.random() * NH);
        trackTTL = Math.floor(Math.random() * 7) + 3;
      }
      if (trackTTL > 0) trackTTL--;

      for (let y = 0; y < NH; y++) {
        const inBand = trackTTL > 0 && Math.abs(y - trackY) < 9;
        const density = inBand ? 0.6 : 0.07;
        for (let x = 0; x < NW; x++) {
          const i = (y * NW + x) * 4;
          if (Math.random() < density) {
            const v =
              Math.random() < 0.65
                ? Math.floor(Math.random() * 80 + 175)
                : Math.floor(Math.random() * 55);
            const a = inBand
              ? Math.floor(Math.random() * 190 + 55)
              : Math.floor(Math.random() * 110 + 25);
            d[i] = d[i + 1] = d[i + 2] = v;
            d[i + 3] = a;
          } else if (Math.random() < 0.003) {
            d[i] = Math.random() < 0.5 ? 255 : 0;
            d[i + 1] = 0;
            d[i + 2] = Math.random() < 0.5 ? 255 : 0;
            d[i + 3] = 110;
          }
        }
      }
      nCtx.putImageData(imgData, 0, 0);

      if (Math.random() < 0.07) {
        const ly = Math.floor(Math.random() * NH);
        nCtx.fillStyle = `rgba(255,255,255,${(Math.random() * 0.35 + 0.1).toFixed(2)})`;
        nCtx.fillRect(0, ly, NW, Math.ceil(Math.random() * 2));
      }
    }
    noiseRaf = requestAnimationFrame(drawNoise);
  }
  noiseRaf = requestAnimationFrame(drawNoise);

  /* ── Tracking band ──────────────────────────────────── */
  const bandEl = overlay.querySelector("#transit-tracking-band");
  const bandInterval = setInterval(() => {
    if (Math.random() < 0.28) {
      bandEl.style.top = Math.random() * 78 + 8 + "%";
      bandEl.style.height = Math.random() * 14 + 4 + "px";
      bandEl.style.opacity = "1";
      setTimeout(
        () => {
          bandEl.style.opacity = "0";
        },
        70 + Math.random() * 130,
      );
    }
  }, 180);

  /* ── Animated ellipsis ──────────────────────────────── */
  const ellEl = overlay.querySelector("#transit-ellipsis");
  let dotCount = 0;
  const dotInterval = setInterval(() => {
    dotCount = (dotCount + 1) % 4;
    ellEl.textContent = ".".repeat(dotCount);
  }, 340);

  /* ── Stochastic loading bar ─────────────────────────── */
  const barEl = overlay.querySelector("#transit-bar");
  const pctEl = overlay.querySelector("#transit-pct");
  const startTime = Date.now();
  let progress = 0;
  let stallTicks = 0;
  const TARGET_MS = 1820;

  const barInterval = setInterval(() => {
    if (stallTicks > 0) {
      stallTicks--;
      return;
    }
    const t = Math.min((Date.now() - startTime) / TARGET_MS, 1);
    const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    const target = eased * 97;
    if (Math.random() < 0.09 && progress > 8 && progress < 88) {
      stallTicks = Math.floor(Math.random() * 6) + 2;
      return;
    }
    const delta = Math.max(0, target - progress) * 0.28 + Math.random() * 1.8;
    progress = Math.min(progress + delta, 97);
    barEl.style.width = progress + "%";
    pctEl.textContent = Math.floor(progress) + "%";
    advanceSlide(progress);
  }, 48);

  /* ── Completion ─────────────────────────────────────── */
  setTimeout(() => {
    barEl.style.transition = "width 100ms steps(5, end)";
    barEl.style.width = "100%";
    pctEl.textContent = "100%";
    setTimeout(() => {
      overlay.classList.add("transit-flash");
      setTimeout(() => {
        cancelAnimationFrame(noiseRaf);
        clearInterval(bandInterval);
        clearInterval(dotInterval);
        clearInterval(barInterval);
        if (href && href !== "#") window.location.href = href;
      }, 130);
    }, 160);
  }, 2000);
}