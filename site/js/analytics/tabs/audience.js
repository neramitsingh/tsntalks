/* Audience — "who watches?"
 *
 * EVERY PANEL NAMES ITS OWN WINDOW. This is the whole reason this tab is built
 * the way it is. The old media kit claimed the audience was 54% India; it was,
 * in a window nobody printed, while the 90 days that mattered were 97% Thailand.
 * A demographic figure without its window is not a weak claim, it is a
 * different claim.
 *
 * And the window here is NOT the control above. Demographics arrive from the
 * platforms as fixed rolling windows — YouTube's 90 days, Instagram's 30 — and
 * the panel shows the window the data came with, which is why each subtitle
 * spells it out rather than inheriting the frame.
 */

import { audience } from '../data.js';
import {
  chart, windowSub, resultPanel, notReported, full, el,
} from './shared.js';
import { dimensionLabel, rangeLabel, signedPoints, ARROW } from '../format.js';

/**
 * The six panels, in the spec's order.
 *
 * `windowDays` is how far back the comparison sits, not a window length —
 * YouTube rewrites its 90-day demographics every day, so comparing consecutive
 * rows would show nothing but noise. See §3.6 of the data contract.
 */
const PANELS = [
  { kind: 'yt_age', title: 'YouTube · age', windowDays: 90, unit: 'Share of views' },
  { kind: 'yt_gender', title: 'YouTube · gender', windowDays: 90, unit: 'Share of views' },
  { kind: 'yt_country', title: 'YouTube · country', windowDays: 90, unit: 'Views', top: 12 },
  { kind: 'ig_age', title: 'Instagram · age', windowDays: 30, unit: 'Followers' },
  { kind: 'ig_city', title: 'Instagram · city', windowDays: 30, unit: 'Followers', top: 12 },
  { kind: 'ig_country', title: 'Instagram · country', windowDays: 30, unit: 'Followers', top: 12 },
];

/* yt_age and yt_gender arrive as percentages of channel views; everything else
   is an absolute count. data.js normalises both to `share`, so the chart is the
   same either way — but the twin prints the raw value and needs the right
   header for it. */
const PERCENTAGE_KINDS = new Set(['yt_age', 'yt_gender']);

export async function audienceTab(mount) {
  const results = await Promise.all(PANELS.map((p) => audience(p.kind, p.windowDays)));
  mount.replaceChildren(...PANELS.map((p, i) => panelFor(p, results[i])));
}

function panelFor(spec, result) {
  /* The subtitle is built before the result is unwrapped so that even an error
     panel says which window it failed to read. */
  const known = result.ok && result.current.window;
  const sub = known
    ? windowSub(spec.unit, result.current.window.start, result.current.window.end,
                comparisonNote(result.current.prevWindow))
    : `${spec.unit} · window unknown`;

  return resultPanel(result, {
    title: spec.title,
    sub,
    width: 'half',
    emptyMessage: `${spec.title}: nothing collected yet.`,
  }, (section, { current }) => {
    if (!current.rows.length) return false;

    const rows = spec.top ? current.rows.slice(0, spec.top) : current.rows;
    const hidden = current.rows.length - rows.length;

    section.appendChild(chart({
      kind: 'hbar',
      name: `${spec.title}, ${rangeLabel(current.window.start, current.window.end)}`,
      points: rows.map((r) => ({
        label: dimensionLabel(spec.kind, r.dimension),
        /* The bar is the SHARE, not the raw value, so a percentage kind and a
           count kind read the same way and neither has to be explained. */
        value: Math.round((r.share ?? 0) * 1000) / 10,
      })),
      format: (v) => `${v}%`,
      rows: rows.map((r) => ({
        label: dimensionLabel(spec.kind, r.dimension),
        share: r.share == null ? null : Math.round(r.share * 1000) / 10,
        value: PERCENTAGE_KINDS.has(spec.kind) ? r.value : Math.round(r.value),
        prevShare: r.prevShare == null ? null : Math.round(r.prevShare * 1000) / 10,
        change: r.shareDelta == null ? null : Math.round(r.shareDelta * 10) / 10,
      })),
      columns: [
        { key: 'label', name: 'Group' },
        { key: 'share', name: 'Share', num: true, format: (v) => `${v}%` },
        { key: 'value', name: spec.unit, num: true, format: full },
        { key: 'prevShare', name: 'Share before', num: true, format: (v) => `${v}%` },
        { key: 'change', name: 'Change', num: true, format: (v) => signedPoints(v) },
      ],
      summary: 'Show the numbers and the change',
    }));

    section.appendChild(changeList(spec, current));

    if (hidden > 0) {
      section.appendChild(el('p', 'a-note',
        `The ${rows.length} largest of ${full(current.rows.length)}. The long tail is `
        + `${full(hidden)} more, each under ${Math.round(
          (rows.at(-1).share ?? 0) * 1000) / 10}% — the monthly review exports all of them.`));
    }
    return true;
  });
}

function comparisonNote(prevWindow) {
  return prevWindow
    ? `compared with ${rangeLabel(prevWindow.start, prevWindow.end)}`
    : 'no comparable earlier window';
}

/**
 * The movers, in words, in percentage points.
 *
 * Points and not a relative change: "India is down 40%" is read as a share by
 * nearly everyone who sees it, and a share is exactly what it is not.
 */
function changeList(spec, current) {
  if (!current.prevWindow) {
    return notReported(
      'No comparable earlier window, so there is no change to show. The collector '
      + 'has only been recording since 14 September 2026; this panel fills in as the '
      + 'history builds.');
  }
  const movers = current.rows
    .filter((r) => r.shareDelta != null && Math.abs(r.shareDelta) >= 0.5)
    .sort((a, b) => Math.abs(b.shareDelta) - Math.abs(a.shareDelta))
    .slice(0, 3);

  if (!movers.length) {
    return el('p', 'a-note',
      `Nothing moved by more than half a point against ${rangeLabel(
        current.prevWindow.start, current.prevWindow.end)}.`);
  }

  const p = el('p', 'a-note');
  p.append(document.createTextNode('Biggest shifts: '));
  movers.forEach((r, i) => {
    if (i) p.append(document.createTextNode(', '));
    const span = el('span', 'a-delta');
    span.dataset.dir = r.shareDelta > 0 ? 'up' : 'down';
    span.appendChild(el('i', 'arrow', ARROW[r.shareDelta > 0 ? 'up' : 'down']));
    span.append(document.createTextNode(
      `${dimensionLabel(spec.kind, r.dimension)} ${signedPoints(r.shareDelta)}`));
    p.appendChild(span);
  });
  p.append(document.createTextNode(
    `, against ${rangeLabel(current.prevWindow.start, current.prevWindow.end)}.`));
  return p;
}
