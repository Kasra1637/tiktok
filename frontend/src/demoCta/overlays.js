/**
 * Native Product Demo + CTA canvas overlays.
 *
 * Ported faithfully from the standalone app: opening hook punch-in and closing
 * lead-gen end card, both laid out inside TikTok's safe area (right icon rail
 * plus bottom caption strip), with draggable repositioning via offsets.
 *
 * The one deliberate carry-over worth naming: `getEndCardBounds` applies the
 * vertical offset against the canvas *width*, matching the standalone app's
 * hit-test exactly. It looks like a units bug and it is one, but the drag
 * bounds are part of the behavior contract, so it stays until both apps change
 * together.
 */

export const SAFE_X = 0.09;
export const SAFE_RIGHT = 0.22;
export const SAFE_BOTTOM = 0.24;

export const HOOK_FONT = '"Anton", "Arial Black", sans-serif';

function clamp01(t) {
  return t < 0 ? 0 : t > 1 ? 1 : t;
}

/**
 * One entrance style as a pure function of overlay-local video time.
 *
 * `style` names one of OVERLAY_ANIMS; `time` counts from the overlay's first
 * visible frame and `duration` is its whole on-screen window, so the same
 * call with the same frame renders the same pixels in preview and in the
 * captured export. Wall-clock (`performance.now`, `Date.now`) must never
 * reach here — that is what would make the file differ from the preview.
 *
 * Returns motion in caller-scaled units: dxEm/dyEm multiply the overlay's own
 * font size, rise01 multiplies ch*0.05 (the end card's historical lift), and
 * reveal01/underline01 are 0..1 progress values. `punch` and `rise`
 * reproduce the two behaviours that shipped before this table existed,
 * formula for formula, so the defaults change nothing already made.
 */
export function overlayIntro(style, time, duration, inDur = 0.32, outDur = 0.28) {
  const s = String(style || "punch");
  const inT = clamp01(time / Math.max(0.01, inDur));
  const eased = easeOutCubic(inT);
  const outStart = Math.max(0.1, duration - outDur);
  const outT = time > outStart ? clamp01((time - outStart) / Math.max(0.01, outDur)) : 0;
  const fadeOut = 1 - outT;
  // The underline rides under globalAlpha, which already carries the out
  // fade — multiplying it here too would fade it twice as fast.
  const underline = Math.min(1, easeOutCubic(Math.min(1, time / 0.6)));
  const base = { alpha: 1, scale: 1, dxEm: 0, dyEm: 0, rise01: 0, reveal01: 1, underline, glow01: 0, wobble: 0 };

  switch (s) {
    case "fade":
      return { ...base, alpha: eased * fadeOut };
    case "rise":
      return { ...base, alpha: eased * fadeOut, rise01: 1 - eased };
    case "slide":
      return { ...base, alpha: Math.min(1, inT * 1.6) * fadeOut, dxEm: (1 - eased) * 2.5 };
    case "pop": {
      const p = 0.6 + 0.4 * easeOutBack(inT);
      return { ...base, alpha: Math.min(1, inT * 1.5) * fadeOut, scale: p - outT * 0.06 };
    }
    case "typewriter":
      return { ...base, alpha: fadeOut, reveal01: clamp01(time / Math.max(0.3, duration * 0.7)) };
    case "glow":
      return { ...base, alpha: Math.min(1, inT * 1.3) * fadeOut, glow01: (1 - eased) * fadeOut };
    case "underline":
      return { ...base, alpha: Math.min(1, inT * 2) * fadeOut, underline: easeOutCubic(clamp01(time / Math.max(0.3, duration * 0.8))) };
    case "drop": {
      const e = easeOutBack(inT);
      return { ...base, alpha: Math.min(1, inT * 1.5) * fadeOut, dyEm: (e - 1) * 1.5 };
    }
    case "steady":
      return { ...base, alpha: fadeOut };
    case "punch":
    default: {
      const scale = 1.24 - 0.24 * easeOutBack(inT) - outT * 0.06;
      const alpha = Math.min(1, inT * 1.4) * (1 - outT);
      const wobble = inT >= 1 ? Math.sin((time - 0.32) * 9) * 0.004 * Math.max(0, 1 - (time - 0.32) * 1.6) : 0;
      return { ...base, alpha, scale, wobble };
    }
  }
}

/**
 * Progressive character reveal for the typewriter style. Walks wrapped lines
 * in order so word wrapping never changes mid-reveal: later lines simply have
 * nothing visible yet.
 */
export function revealLines(lines, reveal01) {
  if (reveal01 >= 1) return lines;
  const total = lines.reduce((n, ln) => n + ln.length, 0);
  if (total <= 0) return lines;
  let visible = Math.floor(reveal01 * total);
  return lines.map((ln) => {
    if (visible <= 0) return "";
    const take = Math.min(ln.length, visible);
    visible -= take;
    return ln.slice(0, take);
  });
}

function easeOutBack(t) {
  const c = 1.9;
  const p = t - 1;
  return 1 + (c + 1) * p * p * p + c * p * p;
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function wrap(ctx, text, maxWidth) {
  const words = String(text || "").split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function pill(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

/**
 * Punch-in hook, on screen from frame 0. Scale overshoots then settles, then fades out.
 *
 * `font` is a canvas font stack from OVERLAY_FONTS, `anim` names an
 * OVERLAY_ANIMS style, and `scale` multiplies the cw-derived size. Defaults
 * reproduce the long-standing look exactly (see overlayIntro).
 */
export function drawHookOverlay(ctx, cw, ch, time, { text, duration, accent, offsetX = 0, offsetY = 0, font = HOOK_FONT, anim = "punch", scale = 1 }) {
  if (!String(text || "").trim() || time > duration) return;

  const m = overlayIntro(anim, time, duration, 0.32, 0.28);

  const maxWidth = cw * (1 - SAFE_X * 2 - 0.02);
  const fontSize = Math.round(cw * 0.108 * scale);
  ctx.save();
  ctx.font = `${fontSize}px ${font}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  // Layout from the full wrap so later lines do not shift the block as a
  // typewriter reveal fills in; only revealed text is painted, in place.
  const fullLines = wrap(ctx, String(text).toUpperCase(), maxWidth);
  const shown = revealLines(fullLines, m.reveal01);
  const lineH = fontSize * 1.16;
  const padX = fontSize * 0.3;
  const padY = fontSize * 0.16;
  const blockH = fullLines.length * lineH;
  const top = ch * 0.13 + offsetY * ch;

  ctx.globalAlpha = m.alpha;
  ctx.translate(cw / 2 + offsetX * cw + m.dxEm * fontSize, top + blockH / 2 + m.dyEm * fontSize);
  ctx.scale(m.scale + m.wobble, m.scale + m.wobble);
  ctx.translate(-(cw / 2 + offsetX * cw), -(top + blockH / 2));

  fullLines.forEach((ln, i) => {
    const line = shown[i];
    if (!line) return;
    const cy = top + i * lineH + lineH / 2;
    const tw = ctx.measureText(line).width;
    const bx = cw / 2 - tw / 2 - padX;
    const by = cy - lineH / 2 - padY + lineH * 0.06;
    const bw = tw + padX * 2;
    const bh = lineH + padY * 2 - lineH * 0.12;

    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.45)";
    ctx.shadowBlur = fontSize * (0.28 + m.glow01 * 0.9);
    ctx.shadowOffsetY = fontSize * 0.06;
    ctx.fillStyle = "rgba(9,9,12,0.86)";
    pill(ctx, bx, by, bw, bh, bh * 0.24);
    ctx.fill();
    ctx.restore();

    // Accent underline on the last line for a beat of motion.
    if (i === fullLines.length - 1) {
      ctx.fillStyle = accent;
      const uw = bw * m.underline;
      pill(ctx, bx, by + bh - fontSize * 0.09, uw, fontSize * 0.09, fontSize * 0.045);
      ctx.fill();
    }

    ctx.fillStyle = "#ffffff";
    ctx.fillText(line, cw / 2, cy);
  });

  ctx.restore();
}

/**
 * Lead-gen end card: sits above TikTok's caption strip, clear of the icon rail,
 * with an arrow that pumps toward the bio link.
 *
 * Same font/anim/scale contract as the hook above. The default style here is
 * `rise` — the fade-plus-lift this card always had — and the arrow pump is
 * untouched: it is driven by elapsed video time, so it records exactly as it
 * previews. There is no out fade on this card by design; it persists to the
 * end of its window, and the caller guards the window itself.
 */
export function drawEndCard(ctx, cw, ch, timeLeft, { headline, handle, duration, accent, offsetX = 0, offsetY = 0, font = HOOK_FONT, anim = "rise", scale = 1 }) {
  if (timeLeft > duration || timeLeft < 0) return;
  const elapsed = duration - timeLeft;
  const m = overlayIntro(anim, elapsed, duration, 0.4, 0);

  const boxW = cw * (1 - SAFE_X - SAFE_RIGHT);
  const headFont = Math.round(cw * 0.082 * scale);
  const subFont = Math.round(cw * 0.046 * scale);

  ctx.save();
  ctx.globalAlpha = m.alpha;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";

  ctx.font = `${headFont}px ${font}`;
  const fullLines = wrap(ctx, String(headline || "").toUpperCase(), boxW - headFont * 0.6);
  const shown = revealLines(fullLines, m.reveal01);
  const lineH = headFont * 1.14;
  const blockH = fullLines.length * lineH + subFont * 2.6;
  const x = cw * SAFE_X + offsetX * cw + m.dxEm * headFont;
  const bottom = ch * (1 - SAFE_BOTTOM) + offsetY * ch;
  const top = bottom - blockH + m.rise01 * ch * 0.05 + m.dyEm * headFont;

  fullLines.forEach((ln, i) => {
    const line = shown[i];
    if (!line) return;
    const cy = top + i * lineH + lineH / 2;
    const tw = ctx.measureText(line).width;
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.5)";
    ctx.shadowBlur = headFont * (0.3 + m.glow01 * 0.9);
    ctx.fillStyle = "rgba(9,9,12,0.86)";
    pill(ctx, x - headFont * 0.24, cy - lineH * 0.46, tw + headFont * 0.48, lineH * 0.92, lineH * 0.22);
    ctx.fill();
    ctx.restore();
    ctx.fillStyle = "#ffffff";
    ctx.fillText(line, x, cy);
  });

  // Handle chip + pumping arrow pointing at the bio link.
  const chipY = top + fullLines.length * lineH + subFont * 0.9;
  ctx.font = `${subFont}px ${font}`;
  const handleText = String(handle || "").trim() || "@yourhandle";
  const hw = ctx.measureText(handleText.toUpperCase()).width;
  const chipH = subFont * 1.9;
  ctx.fillStyle = accent;
  pill(ctx, x, chipY - chipH / 2, hw + subFont * 2.6, chipH, chipH / 2);
  ctx.fill();
  ctx.fillStyle = "#0a0a0c";
  ctx.fillText(handleText.toUpperCase(), x + subFont * 0.8, chipY + subFont * 0.04);

  const pump = Math.sin(elapsed * 7) * subFont * 0.16;
  const ax = x + hw + subFont * 1.9 + pump;
  ctx.strokeStyle = "#0a0a0c";
  ctx.lineWidth = subFont * 0.16;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(ax - subFont * 0.34, chipY - subFont * 0.34);
  ctx.lineTo(ax + subFont * 0.1, chipY);
  ctx.lineTo(ax - subFont * 0.34, chipY + subFont * 0.34);
  ctx.stroke();

  ctx.restore();
}

/** Returns bounding box (in canvas coords) for the hook text overlay. */
export function getHookBounds(cw, ch, text, offsetX, offsetY, font = HOOK_FONT, scale = 1) {
  if (!String(text || "").trim()) return null;
  const fontSize = Math.round(cw * 0.108 * scale);
  const maxWidth = cw * (1 - SAFE_X * 2 - 0.02);
  const canvas = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(1, 1) : null;
  if (!canvas) return null;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.font = `${fontSize}px ${font}`;
  const lines = wrap(ctx, String(text).toUpperCase(), maxWidth);
  const lineH = fontSize * 1.16;
  const padX = fontSize * 0.3;
  const padY = fontSize * 0.16;
  const blockH = lines.length * lineH;
  const blockW = Math.min(maxWidth, Math.max(...lines.map((l) => ctx.measureText(l).width))) + padX * 2;
  const top = ch * 0.13 + offsetY * ch;
  const left = cw / 2 - blockW / 2 + offsetX * cw;
  return { x: left, y: top - padY, w: blockW, h: blockH + padY * 2 };
}

/** Returns bounding box (in canvas coords) for the end card overlay. */
export function getEndCardBounds(cw, ch, headline, handle, offsetX, offsetY, font = HOOK_FONT, scale = 1) {
  void handle;
  if (!String(headline || "").trim()) return null;
  const headFont = Math.round(cw * 0.082 * scale);
  const subFont = Math.round(cw * 0.046 * scale);
  const boxW = cw * (1 - SAFE_X - SAFE_RIGHT);
  const canvas = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(1, 1) : null;
  if (!canvas) return null;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.font = `${headFont}px ${font}`;
  const lines = wrap(ctx, String(headline).toUpperCase(), boxW - headFont * 0.6);
  const lineH = headFont * 1.14;
  const blockH = lines.length * lineH + subFont * 2.6;
  const x = cw * SAFE_X + offsetX * cw;
  // Ported exactly: the standalone app's hit-test applies the vertical offset
  // against the canvas width here. See the module docstring.
  const bottom = ch * (1 - SAFE_BOTTOM) + offsetY * cw;
  const top = bottom - blockH;
  return { x, y: top, w: boxW, h: blockH };
}
