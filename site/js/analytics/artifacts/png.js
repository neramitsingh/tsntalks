/* The guest card as a PNG, drawn on a canvas.
 *
 * Square, 1080px, which is what both LINE and Instagram want — LINE's share
 * image and an Instagram feed post are both square at that size, so one file
 * serves both rather than two that are almost the same.
 *
 * Drawn by hand rather than by rasterising the DOM. html2canvas would be a
 * third CDN dependency on a page that has two, it reimplements a layout engine
 * badly, and the card is nine shapes and six strings. Hand-drawing also means
 * the PNG cannot silently drift when the print stylesheet changes.
 *
 * THE PNG IS DARK AND THE PDF IS NOT, and that is deliberate. The PDF is ink on
 * A4: a dark ground there is four millilitres of toner and unreadable on a
 * train. The PNG is posted to a phone screen, where PRODUCT.md is explicit —
 * the brand is dark and saffron, and cream grounds are on the anti-reference
 * list. Same numbers, same words, the ground each medium actually wants.
 */

import { full, compact, PLATFORM_NAME } from '../format.js';

/** Square, and the same square for both platforms. */
export const PNG_SIZE = 1080;

const BG = '#0D0706';
const CREAM = '#F2E4CC';
const CREAM_DIM = '#C4A880';
const MUTED = '#A08468';
const GOLD = '#E0B040';
const SAFFRON = '#E8621A';

const PLATFORM_COLOUR = {
  youtube: '#E8621A',
  instagram: '#7C6BF0',
  tiktok: '#2EA6A0',
};

const DISPLAY = '"Bodoni Moda", Georgia, serif';
const TEXT = '"Hanken Grotesk", system-ui, sans-serif';

/**
 * Shrink the font until the string fits, rather than letting it run off the
 * card. Guest names run from "Sam Lee" to "Mr. Deepak Sajnani", and a card that
 * clips the guest's own name is not a card you send the guest.
 */
function fitText(ctx, text, maxWidth, { weight = 500, family = DISPLAY, start, min }) {
  let size = start;
  do {
    ctx.font = `${weight} ${size}px ${family}`;
    if (ctx.measureText(text).width <= maxWidth) break;
    size -= 2;
  } while (size > min);
  return size;
}

function wrap(ctx, text, maxWidth, maxLines) {
  const words = String(text ?? '').split(/\s+/).filter(Boolean);
  const lines = [];
  let line = '';
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > maxWidth && line) {
      lines.push(line);
      line = word;
      if (lines.length === maxLines) break;
    } else {
      line = next;
    }
  }
  if (lines.length < maxLines && line) lines.push(line);
  if (lines.length === maxLines && words.join(' ') !== lines.join(' ')) {
    lines[maxLines - 1] = `${lines[maxLines - 1].replace(/[\s,.;:]+$/, '')}…`;
  }
  return lines;
}

/**
 * Draw the card.
 *
 * @param {object} spec
 * @param {object} spec.episode   the row from episode_rollup
 * @param {object} [spec.topClip] the clip that travelled furthest
 * @param {string} spec.shareUrl
 * @param {number} [spec.size]
 * @returns {Promise<Blob>}
 */
export async function renderGuestCard({ episode, topClip, shareUrl, size = PNG_SIZE }) {
  /* Without this the first paint uses a fallback face and the card ships with
     the wrong typography — canvas does not re-render when a webfont arrives. */
  if (document.fonts?.ready) await document.fonts.ready;

  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  const u = size / PNG_SIZE;                 // one unit = 1px at 1080
  const pad = 80 * u;
  const inner = size - pad * 2;

  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, size, size);

  /* A saffron rule at the top, the way the public pages open. */
  ctx.fillStyle = SAFFRON;
  ctx.fillRect(0, 0, size, 10 * u);

  ctx.textBaseline = 'alphabetic';

  // --- wordmark
  ctx.font = `600 ${34 * u}px ${DISPLAY}`;
  ctx.fillStyle = CREAM;
  ctx.fillText('TSN ', pad, pad + 34 * u);
  const markWidth = ctx.measureText('TSN ').width;
  ctx.font = `italic 600 ${34 * u}px ${DISPLAY}`;
  ctx.fillStyle = GOLD;
  ctx.fillText('Talks', pad + markWidth, pad + 34 * u);

  ctx.font = `700 ${18 * u}px ${TEXT}`;
  ctx.fillStyle = MUTED;
  ctx.textAlign = 'right';
  ctx.fillText(`SEASON ${episode.season} · EPISODE ${episode.number}`.toUpperCase(),
               size - pad, pad + 32 * u);
  ctx.textAlign = 'left';

  // --- the guest
  let y = pad + 150 * u;
  const nameSize = fitText(ctx, episode.guest, inner, { start: 96 * u, min: 44 * u });
  ctx.fillStyle = CREAM;
  ctx.fillText(episode.guest, pad, y);

  if (episode.role) {
    y += 46 * u;
    ctx.font = `500 ${26 * u}px ${TEXT}`;
    ctx.fillStyle = CREAM_DIM;
    for (const line of wrap(ctx, episode.role, inner, 2)) {
      ctx.fillText(line, pad, y);
      y += 34 * u;
    }
  }

  // --- the number
  y += 70 * u;
  ctx.font = `700 ${20 * u}px ${TEXT}`;
  ctx.fillStyle = GOLD;
  ctx.fillText('WATCHED', pad, y);

  y += 130 * u;
  const figure = full(episode.totalReach);
  const figureSize = fitText(ctx, figure, inner, { start: 170 * u, min: 80 * u });
  ctx.fillStyle = CREAM;
  ctx.fillText(figure, pad, y);

  y += 44 * u;
  ctx.font = `500 ${25 * u}px ${TEXT}`;
  ctx.fillStyle = CREAM_DIM;
  /* TIMES, not people. total_reach is a sum of view counts across the cuts;
     someone who watched the episode and then saw two clips is three in it. The
     card says the true thing, which is also the warm thing. */
  ctx.fillText('times, across the episode and every clip', pad, y);

  // --- the split
  y += 60 * u;
  const parts = [
    { id: 'youtube', value: episode.ytViews + episode.clipViews.youtube },
    { id: 'instagram', value: episode.clipViews.instagram },
    { id: 'tiktok', value: episode.clipViews.tiktok },
  ].filter((p) => p.value > 0);
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;

  let x = pad;
  for (const part of parts) {
    const width = (part.value / total) * inner;
    ctx.fillStyle = PLATFORM_COLOUR[part.id];
    ctx.fillRect(x, y, Math.max(width - 4 * u, 2 * u), 16 * u);
    x += width;
  }

  y += 50 * u;
  ctx.font = `600 ${21 * u}px ${TEXT}`;
  x = pad;
  for (const part of parts) {
    ctx.fillStyle = PLATFORM_COLOUR[part.id];
    ctx.fillRect(x, y - 14 * u, 14 * u, 14 * u);
    ctx.fillStyle = CREAM_DIM;
    /* The figure in words beside the swatch: a bar length alone is not a
       number, and three saturated colours are three greys to some readers. */
    const label = `${PLATFORM_NAME[part.id]} ${compact(part.value)}`;
    ctx.fillText(label, x + 22 * u, y);
    x += 22 * u + ctx.measureText(label).width + 40 * u;
  }

  // --- the top clip
  if (topClip) {
    y += 66 * u;
    ctx.font = `700 ${18 * u}px ${TEXT}`;
    ctx.fillStyle = MUTED;
    ctx.fillText(`TRAVELLED FURTHEST · ${(PLATFORM_NAME[topClip.platform] ?? '').toUpperCase()}`
                 + ` · ${full(topClip.viewsEnd)}`, pad, y);

    y += 34 * u;
    ctx.font = `500 ${24 * u}px ${TEXT}`;
    ctx.fillStyle = CREAM;
    for (const line of wrap(ctx, topClip.title || topClip.postId, inner, 2)) {
      ctx.fillText(line, pad, y);
      y += 32 * u;
    }
  }

  // --- the share link
  ctx.font = `500 ${21 * u}px ${TEXT}`;
  ctx.fillStyle = MUTED;
  ctx.fillText(shareUrl, pad, size - pad + 10 * u);

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('The card could not be drawn.'))),
      'image/png',
    );
  });
}
