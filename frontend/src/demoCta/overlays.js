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
 */
export function drawHookOverlay(ctx, cw, ch, time, { text, duration, accent, offsetX = 0, offsetY = 0 }) {
  if (!String(text || "").trim() || time > duration) return;

  const inT = Math.min(1, time / 0.32);
  const outStart = Math.max(0.1, duration - 0.28);
  const outT = time > outStart ? Math.min(1, (time - outStart) / 0.28) : 0;

  const scale = 1.24 - 0.24 * easeOutBack(inT) - outT * 0.06;
  const alpha = Math.min(1, inT * 1.4) * (1 - outT);
  const wobble = inT >= 1 ? Math.sin((time - 0.32) * 9) * 0.004 * Math.max(0, 1 - (time - 0.32) * 1.6) : 0;

  const maxWidth = cw * (1 - SAFE_X * 2 - 0.02);
  const fontSize = Math.round(cw * 0.108);
  ctx.save();
  ctx.font = `${fontSize}px ${HOOK_FONT}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  const lines = wrap(ctx, String(text).toUpperCase(), maxWidth);
  const lineH = fontSize * 1.16;
  const padX = fontSize * 0.3;
  const padY = fontSize * 0.16;
  const blockH = lines.length * lineH;
  const top = ch * 0.13 + offsetY * ch;

  ctx.globalAlpha = alpha;
  ctx.translate(cw / 2 + offsetX * cw, top + blockH / 2);
  ctx.scale(scale + wobble, scale + wobble);
  ctx.translate(-(cw / 2 + offsetX * cw), -(top + blockH / 2));

  lines.forEach((ln, i) => {
    const cy = top + i * lineH + lineH / 2;
    const tw = ctx.measureText(ln).width;
    const bx = cw / 2 - tw / 2 - padX;
    const by = cy - lineH / 2 - padY + lineH * 0.06;
    const bw = tw + padX * 2;
    const bh = lineH + padY * 2 - lineH * 0.12;

    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.45)";
    ctx.shadowBlur = fontSize * 0.28;
    ctx.shadowOffsetY = fontSize * 0.06;
    ctx.fillStyle = "rgba(9,9,12,0.86)";
    pill(ctx, bx, by, bw, bh, bh * 0.24);
    ctx.fill();
    ctx.restore();

    // Accent underline on the last line for a beat of motion.
    if (i === lines.length - 1) {
      ctx.fillStyle = accent;
      const uw = bw * Math.min(1, easeOutCubic(Math.min(1, time / 0.6)));
      pill(ctx, bx, by + bh - fontSize * 0.09, uw, fontSize * 0.09, fontSize * 0.045);
      ctx.fill();
    }

    ctx.fillStyle = "#ffffff";
    ctx.fillText(ln, cw / 2, cy);
  });

  ctx.restore();
}

/**
 * Lead-gen end card: sits above TikTok's caption strip, clear of the icon rail,
 * with an arrow that pumps toward the bio link.
 */
export function drawEndCard(ctx, cw, ch, timeLeft, { headline, handle, duration, accent, offsetX = 0, offsetY = 0 }) {
  if (timeLeft > duration || timeLeft < 0) return;
  const elapsed = duration - timeLeft;
  const inT = Math.min(1, elapsed / 0.4);
  const alpha = easeOutCubic(inT);
  const rise = (1 - easeOutCubic(inT)) * ch * 0.05;

  const boxW = cw * (1 - SAFE_X - SAFE_RIGHT);
  const headFont = Math.round(cw * 0.082);
  const subFont = Math.round(cw * 0.046);

  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";

  ctx.font = `${headFont}px ${HOOK_FONT}`;
  const lines = wrap(ctx, String(headline || "").toUpperCase(), boxW - headFont * 0.6);
  const lineH = headFont * 1.14;
  const blockH = lines.length * lineH + subFont * 2.6;
  const x = cw * SAFE_X + offsetX * cw;
  const bottom = ch * (1 - SAFE_BOTTOM) + offsetY * ch;
  const top = bottom - blockH + rise;

  lines.forEach((ln, i) => {
    const cy = top + i * lineH + lineH / 2;
    const tw = ctx.measureText(ln).width;
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.5)";
    ctx.shadowBlur = headFont * 0.3;
    ctx.fillStyle = "rgba(9,9,12,0.86)";
    pill(ctx, x - headFont * 0.24, cy - lineH * 0.46, tw + headFont * 0.48, lineH * 0.92, lineH * 0.22);
    ctx.fill();
    ctx.restore();
    ctx.fillStyle = "#ffffff";
    ctx.fillText(ln, x, cy);
  });

  // Handle chip + pumping arrow pointing at the bio link.
  const chipY = top + lines.length * lineH + subFont * 0.9;
  ctx.font = `${subFont}px ${HOOK_FONT}`;
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
export function getHookBounds(cw, ch, text, offsetX, offsetY) {
  if (!String(text || "").trim()) return null;
  const fontSize = Math.round(cw * 0.108);
  const maxWidth = cw * (1 - SAFE_X * 2 - 0.02);
  const canvas = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(1, 1) : null;
  if (!canvas) return null;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.font = `${fontSize}px ${HOOK_FONT}`;
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
export function getEndCardBounds(cw, ch, headline, handle, offsetX, offsetY) {
  void handle;
  if (!String(headline || "").trim()) return null;
  const headFont = Math.round(cw * 0.082);
  const subFont = Math.round(cw * 0.046);
  const boxW = cw * (1 - SAFE_X - SAFE_RIGHT);
  const canvas = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(1, 1) : null;
  if (!canvas) return null;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.font = `${headFont}px ${HOOK_FONT}`;
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
