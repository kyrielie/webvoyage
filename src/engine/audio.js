/* ═══════════════════════════════════════════════════════════
   audio.js — shared context + procedural click sound

   Unchanged from the original main.js. Context is created lazily
   on first call — guaranteed to be inside a user gesture (a click
   or the VN typewriter, both only ever run after a click), so no
   suspended-state warning.
═══════════════════════════════════════════════════════════ */

let audioCtx = null;
let lastClickTime = 0;

export function playClickSound() {
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    const now = audioCtx.currentTime;

    // throttle (prevents stacking harshness)
    if (now - lastClickTime < 0.02) return;
    lastClickTime = now;

    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    const filter = audioCtx.createBiquadFilter();

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(audioCtx.destination);

    osc.type = "triangle";

    const baseFreq = 520 + (Math.random() * 40 - 20);
    osc.frequency.setValueAtTime(baseFreq, now);
    osc.frequency.exponentialRampToValueAtTime(180 + Math.random() * 30, now + 0.08);

    filter.type = "lowpass";
    filter.frequency.setValueAtTime(1800, now);
    filter.frequency.exponentialRampToValueAtTime(800, now + 0.08);

    gain.gain.setValueAtTime(0.04, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);

    osc.start(now);
    osc.stop(now + 0.1);
  } catch (_) {
    /* audio is best-effort; never break navigation over it */
  }
}
