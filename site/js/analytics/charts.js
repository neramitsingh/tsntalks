/* Charts. Inline SVG, no chart library, no build step.
 *
 * Five primitives and one composer. Tabs call `chart()`, which draws the mark
 * AND the table below it in one element — so a tab cannot ship a picture of
 * numbers without the numbers. That is the accessibility contract from the
 * spec, and it doubles as the thing that makes every figure copyable.
 *
 * The dataviz rules these follow, from the spec and PRODUCT.md:
 *   thin marks · 2px between surfaces · hairline SOLID gridlines ·
 *   selective direct labels (the peak, not every point) · a legend only when
 *   there are two or more series · a tooltip on hover AND on keyboard focus ·
 *   NO DUAL AXES, ever — two units means two charts ·
 *   position, not deficit: no progress bars toward a target, no countdowns.
 *
 * Responsive by viewBox. Nothing here measures the DOM or listens for resize:
 * the SVG is drawn once in its own coordinate space and the browser scales it.
 */

import { full, compact, rangeLabel, PLATFORM_NAME } from './format.js';

/* The picture's coordinate space. Not pixels — the browser scales this to
   whatever width the panel turns out to be. */
const W = 720;
const H = 260;
const PAD = { top: 18, right: 16, bottom: 26, left: 52 };
const PLOT = { w: W - PAD.left - PAD.right, h: H - PAD.top - PAD.bottom };

const SVG = 'http://www.w3.org/2000/svg';

/**
 * Series colours. The three platform colours are fixed for the life of the
 * project and never reassigned — they are validated for dichromat separation on
 * the dark ground and tests/analytics/test_contrast.py keeps that true.
 *
 * The rest are directional rather than categorical: gained/lost read as up/down
 * and always carry a sign or an arrow somewhere nearby, because green-and-red
 * is the one pair a dichromat viewer cannot separate.
 */
export const SERIES_COLOR = {
  youtube: 'var(--yt)',
  instagram: 'var(--ig)',
  tiktok: 'var(--tt)',
  gained: 'var(--up)',
  lost: 'var(--down)',
  total: 'var(--gold2)',
  value: 'var(--saffron)',
  previous: 'var(--muted)',
};

export const seriesColor = (id) => SERIES_COLOR[id] ?? 'var(--saffron)';
export const seriesName = (id) => PLATFORM_NAME[id] ?? id;

/* --- small builders -------------------------------------------------------- */

function el(name, attrs = {}, text) {
  const node = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) {
    if (v != null) node.setAttribute(k, String(v));
  }
  if (text != null) node.textContent = text;
  return node;
}

function html(name, className, text) {
  const node = document.createElement(name);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

/** Four or five round-ish gridline values covering 0..max. */
function ticks(max, count = 4) {
  if (!Number.isFinite(max) || max <= 0) return [0];
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10;
  const out = [];
  for (let v = 0; v <= max + step / 2; v += step) out.push(v);
  return out;
}

/**
 * The frame: hairline solid gridlines, y labels, x labels.
 *
 * Solid, not dashed. A dashed gridline at this weight reads as a series.
 */
function frame(svg, { max, min = 0, labels, format = compact, everyNth = 1 }) {
  const span = (max - min) || 1;
  const y = (v) => PAD.top + PLOT.h - ((v - min) / span) * PLOT.h;

  const g = el('g', { class: 'a-grid' });
  for (const t of ticks(max - min).map((v) => v + min)) {
    g.appendChild(el('line', {
      x1: PAD.left, x2: PAD.left + PLOT.w, y1: y(t), y2: y(t), class: 'a-gridline',
    }));
    g.appendChild(el('text', {
      x: PAD.left - 8, y: y(t) + 4, class: 'a-axis a-axis-y',
    }, format(t)));
  }
  /* The zero line is drawn brighter when the chart has negative values, because
     it is a boundary rather than a gridline. */
  if (min < 0) {
    g.appendChild(el('line', {
      x1: PAD.left, x2: PAD.left + PLOT.w, y1: y(0), y2: y(0), class: 'a-zeroline',
    }));
  }
  svg.appendChild(g);

  const xs = el('g', { class: 'a-axis-x' });
  const step = PLOT.w / Math.max(labels.length, 1);
  labels.forEach((label, i) => {
    if (i % everyNth !== 0 && i !== labels.length - 1) return;
    xs.appendChild(el('text', {
      x: PAD.left + step * (i + 0.5), y: H - 8, class: 'a-axis', 'text-anchor': 'middle',
    }, label));
  });
  svg.appendChild(xs);

  return { y, step };
}

/** Keep the x-axis readable without measuring anything: thin the labels. */
const thinning = (n) => (n <= 8 ? 1 : n <= 16 ? 2 : n <= 40 ? Math.ceil(n / 8) : Math.ceil(n / 6));

function newChart(name) {
  const svg = el('svg', {
    class: 'a-chart',
    viewBox: `0 0 ${W} ${H}`,
    preserveAspectRatio: 'xMidYMid meet',
    role: 'group',
    'aria-label': name,
  });
  return svg;
}

/**
 * A focusable, hoverable point.
 *
 * `tabindex` on the group is what makes the chart readable without a mouse; the
 * aria-label is what makes it readable without eyes. The `<title>` is the
 * browser's own tooltip, which survives even if the JS tooltip below breaks.
 */
function hotspot(shape, { label, value }) {
  const g = el('g', {
    class: 'a-point', tabindex: '0', role: 'img', 'aria-label': label,
  });
  g.dataset.value = value == null ? '' : String(value);
  g.dataset.tip = label;
  g.appendChild(shape);
  g.appendChild(el('title', {}, label));
  return g;
}

function assertName(name) {
  if (!name || typeof name !== 'string') {
    throw new Error('charts: every chart needs an accessible name');
  }
  return name;
}

/* --- the five primitives --------------------------------------------------- */

/**
 * Lines over time. Stocks — followers, cumulative anything.
 *
 * A gap in the data breaks the line rather than joining across it: a straight
 * segment over a week we did not measure is a claim we cannot support.
 */
export function lineSeries({ name, points, series, format = compact }) {
  assertName(name);
  const svg = newChart(name);
  const values = points.flatMap((p) => series.map((s) => p.values[s.id])).filter((v) => v != null);
  const max = Math.max(1, ...values);
  const min = Math.min(0, ...values);
  const { y, step } = frame(svg, { max, min, labels: points.map((p) => p.label), format,
                                   everyNth: thinning(points.length) });
  const x = (i) => PAD.left + step * (i + 0.5);

  for (const s of series) {
    let run = [];
    const flush = () => {
      if (run.length > 1) {
        svg.appendChild(el('path', {
          class: 'a-line', stroke: seriesColor(s.id),
          d: run.map((p, i) => `${i ? 'L' : 'M'}${p.x} ${p.y}`).join(' '),
        }));
      } else if (run.length === 1) {
        svg.appendChild(el('circle', {
          class: 'a-lone', cx: run[0].x, cy: run[0].y, r: 2.5, fill: seriesColor(s.id),
        }));
      }
      run = [];
    };
    points.forEach((p, i) => {
      const v = p.values[s.id];
      if (v == null) flush();
      else run.push({ x: x(i), y: y(v) });
    });
    flush();

    points.forEach((p, i) => {
      const v = p.values[s.id];
      if (v == null) return;
      svg.appendChild(hotspot(
        el('circle', { cx: x(i), cy: y(v), r: 8, class: 'a-hit' }),
        { label: `${p.label} · ${seriesName(s.id)}: ${full(v)}`, value: v },
      ));
      svg.appendChild(el('circle', {
        cx: x(i), cy: y(v), r: 2, fill: seriesColor(s.id), class: 'a-dotmark',
      }));
    });
  }
  labelThePeak(svg, points, series, x, y, format);
  return svg;
}

/** Grouped columns. Flows — views, gains — where the series are compared. */
export function barSeries({ name, points, series, format = compact }) {
  assertName(name);
  const svg = newChart(name);
  const values = points.flatMap((p) => series.map((s) => p.values[s.id] ?? 0));
  const max = Math.max(1, ...values);
  const min = Math.min(0, ...values);
  const { y, step } = frame(svg, { max, min, labels: points.map((p) => p.label), format,
                                   everyNth: thinning(points.length) });
  const slot = (step * 0.72) / series.length;
  const zero = y(0);

  points.forEach((p, i) => {
    series.forEach((s, k) => {
      const v = p.values[s.id] ?? 0;
      const bx = PAD.left + step * (i + 0.14) + slot * k;
      const by = Math.min(y(v), zero);
      svg.appendChild(hotspot(
        el('rect', {
          x: bx, y: by, width: Math.max(slot - 1, 1), height: Math.max(Math.abs(y(v) - zero), 1),
          fill: seriesColor(s.id), class: 'a-bar',
        }),
        { label: `${p.label} · ${seriesName(s.id)}: ${full(v)}`, value: v },
      ));
    });
  });
  return svg;
}

/** Stacked columns. Parts of one whole, per period. */
export function stackedBars({ name, points, series, format = compact }) {
  assertName(name);
  const svg = newChart(name);
  const totals = points.map((p) => series.reduce((a, s) => a + (p.values[s.id] ?? 0), 0));
  const max = Math.max(1, ...totals);
  const { y, step } = frame(svg, { max, labels: points.map((p) => p.label), format,
                                   everyNth: thinning(points.length) });
  const width = step * 0.68;

  points.forEach((p, i) => {
    let base = 0;
    const bx = PAD.left + step * i + (step - width) / 2;
    for (const s of series) {
      const v = p.values[s.id] ?? 0;
      if (!v) continue;
      const top = y(base + v);
      svg.appendChild(hotspot(
        el('rect', {
          x: bx, y: top, width, height: Math.max(y(base) - top, 1),
          fill: seriesColor(s.id), class: 'a-bar',
        }),
        { label: `${p.label} · ${seriesName(s.id)}: ${full(v)}`, value: v },
      ));
      base += v;
    }
  });

  /* One direct label, on the tallest column. Labelling every column is how a
     chart turns into a table that is hard to read. */
  const peak = totals.indexOf(Math.max(...totals));
  if (totals[peak] > 0) {
    svg.appendChild(el('text', {
      x: PAD.left + step * (peak + 0.5), y: y(totals[peak]) - 6,
      class: 'a-peak', 'text-anchor': 'middle',
    }, format(totals[peak])));
  }
  return svg;
}

/** Horizontal bars. Categories with names too long to stand under a column. */
export function horizontalBars({ name, points, format = compact, colour = 'var(--saffron)' }) {
  assertName(name);
  const rowH = 22;
  const height = Math.max(points.length * rowH + 20, 60);
  const labelW = 150;
  const svg = el('svg', {
    class: 'a-chart', viewBox: `0 0 ${W} ${height}`,
    preserveAspectRatio: 'xMidYMid meet', role: 'group', 'aria-label': name,
  });
  const max = Math.max(1, ...points.map((p) => p.value ?? 0));
  const barW = W - labelW - 90;

  points.forEach((p, i) => {
    const y = 12 + i * rowH;
    svg.appendChild(el('text', {
      x: labelW - 10, y: y + 11, class: 'a-axis', 'text-anchor': 'end',
    }, p.label));
    const w = Math.max((Math.max(p.value ?? 0, 0) / max) * barW, p.value ? 2 : 0);
    svg.appendChild(hotspot(
      el('rect', { x: labelW, y: y + 2, width: w, height: rowH - 8, fill: colour, class: 'a-bar' }),
      { label: `${p.label}: ${full(p.value)}`, value: p.value },
    ));
    /* The number in text, next to the bar. PRODUCT.md: numbers are never only
       a bar length. */
    svg.appendChild(el('text', {
      x: labelW + w + 8, y: y + 12, class: 'a-barval',
    }, format(p.value)));
  });
  return svg;
}

/**
 * A sparkline. The one primitive that may be used without a table twin, and
 * only inline beside the figures it summarises — in a table row whose cells
 * already carry the numbers. On its own it is a chart and needs `chart()`.
 */
export function sparkline(values, { name = 'trend', width = 90, height = 22 } = {}) {
  const clean = values.filter((v) => v != null && Number.isFinite(v));
  const svg = el('svg', {
    class: 'a-spark', viewBox: `0 0 ${width} ${height}`,
    preserveAspectRatio: 'none', role: 'img', 'aria-label': name,
  });
  if (clean.length < 2) return svg;
  const max = Math.max(...clean);
  const min = Math.min(...clean);
  const span = (max - min) || 1;
  const step = width / (clean.length - 1);
  svg.appendChild(el('path', {
    class: 'a-sparkline',
    d: clean.map((v, i) =>
      `${i ? 'L' : 'M'}${(i * step).toFixed(1)} ${(height - 2 - ((v - min) / span) * (height - 4)).toFixed(1)}`,
  ).join(' '),
  }));
  return svg;
}

/** The single direct label that the line charts get: the highest point. */
function labelThePeak(svg, points, series, x, y, format) {
  let best = null;
  points.forEach((p, i) => {
    for (const s of series) {
      const v = p.values[s.id];
      if (v != null && (!best || v > best.v)) best = { v, i, id: s.id };
    }
  });
  if (!best) return;
  svg.appendChild(el('text', {
    x: x(best.i), y: y(best.v) - 8, class: 'a-peak', 'text-anchor': 'middle',
  }, format(best.v)));
}

/* --- legend ---------------------------------------------------------------- */

/**
 * A legend, and only when there are two or more series.
 *
 * One series with a legend is a label pretending to be a key, and it takes up
 * the room the chart wanted.
 */
export function legend(series) {
  if (series.length < 2) return null;
  const ul = html('ul', 'a-legend');
  for (const s of series) {
    const li = document.createElement('li');
    const swatch = html('i');
    swatch.style.background = seriesColor(s.id);
    li.append(swatch, document.createTextNode(s.name ?? seriesName(s.id)));
    ul.appendChild(li);
  }
  return ul;
}

/* --- the table twin -------------------------------------------------------- */

/**
 * The `<details><table>` that must accompany every chart.
 *
 * The same numbers, not a summary of them. If the chart shows fourteen points
 * the table has fourteen rows, and `data-value` on each cell is what the
 * "chart and twin carry identical numbers" test compares.
 *
 * @param {Array<object>} rows
 * @param {Array<{key: string, name: string, num?: boolean, format?: Function}>} columns
 */
export function tableTwin(rows, columns, { summary = 'Show the numbers' } = {}) {
  const details = html('details', 'a-twin');
  details.appendChild(html('summary', null, summary));

  const wrap = html('div', 'a-tablewrap');
  const table = html('table', 'a-table');

  const thead = document.createElement('thead');
  const hr = document.createElement('tr');
  for (const c of columns) {
    const th = document.createElement('th');
    th.textContent = c.name;
    th.scope = 'col';
    if (c.num) th.className = 'num';
    hr.appendChild(th);
  }
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (const row of rows) {
    const tr = document.createElement('tr');
    for (const c of columns) {
      const td = document.createElement('td');
      const raw = row[c.key];
      if (c.num) td.className = 'num';
      if (raw == null) {
        td.textContent = '—';
        td.classList.add('none');
      } else {
        td.textContent = c.format ? c.format(raw) : String(raw);
        if (typeof raw === 'number') td.dataset.value = String(raw);
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
  details.appendChild(wrap);
  return details;
}

/* --- the composer ---------------------------------------------------------- */

const DRAW = {
  line: lineSeries,
  bar: barSeries,
  stacked: stackedBars,
  hbar: horizontalBars,
};

/**
 * A chart and its table, in one element, with the legend and the tooltip.
 *
 * This is what tabs call. The primitives above are exported because the plan
 * names them and because the tests drive them directly, but every chart on
 * screen comes through here — and a test walks each tab asserting that no
 * `.a-chart` exists without a `details.a-twin` beside it.
 *
 * @param {object} spec
 * @param {'line'|'bar'|'stacked'|'hbar'} spec.kind
 * @param {string} spec.name       accessible name; required
 * @param {Array} spec.points      `[{ label, values: {seriesId: n} }]`, or
 *                                 `[{ label, value }]` for `hbar`
 * @param {Array} [spec.series]    `[{ id, name }]`; one entry means no legend
 * @param {Array} [spec.columns]   overrides the default twin columns
 * @param {Array} [spec.rows]      overrides the default twin rows
 */
export function chart(spec) {
  const { kind, name, points = [], series = [], format = compact } = spec;
  assertName(name);

  const figure = html('figure', 'a-figure');

  if (!points.length) {
    figure.appendChild(html('p', 'a-empty', spec.empty ?? `No data for ${name} in this window.`));
    return figure;
  }

  const draw = DRAW[kind];
  if (!draw) throw new Error(`charts: unknown kind "${kind}"`);
  const svg = draw({ ...spec, format });

  const key = legend(series);
  if (key) figure.appendChild(key);
  figure.appendChild(svg);

  const tip = html('div', 'a-tip');
  tip.hidden = true;
  figure.appendChild(tip);
  wireTooltip(figure, svg, tip);

  const caption = html('figcaption', 'vh', name);
  figure.appendChild(caption);

  figure.appendChild(tableTwin(
    spec.rows ?? defaultTwinRows(points, series, kind),
    spec.columns ?? defaultTwinColumns(series, kind, format),
    { summary: spec.summary ?? 'Show the numbers' },
  ));
  return figure;
}

function defaultTwinRows(points, series, kind) {
  if (kind === 'hbar') return points.map((p) => ({ label: p.label, value: p.value }));
  return points.map((p) => {
    const row = { label: p.label };
    let total = 0;
    for (const s of series) {
      row[s.id] = p.values[s.id] ?? null;
      total += p.values[s.id] ?? 0;
    }
    if (series.length > 1) row.total = total;
    return row;
  });
}

function defaultTwinColumns(series, kind, format) {
  if (kind === 'hbar') {
    return [{ key: 'label', name: 'Name' }, { key: 'value', name: 'Value', num: true, format: full }];
  }
  const cols = [{ key: 'label', name: 'Period' }];
  for (const s of series) {
    cols.push({ key: s.id, name: s.name ?? seriesName(s.id), num: true, format: full });
  }
  if (series.length > 1) cols.push({ key: 'total', name: 'Total', num: true, format: full });
  return cols;
}

/**
 * One tooltip per figure, driven by pointer AND focus.
 *
 * Focus is not an afterthought here: the points are in the tab order, so a
 * keyboard reader walks the series and sees the same box a mouse reader does.
 * Positioned from the hotspot's own client rect, so it follows the SVG however
 * the browser has scaled the viewBox.
 */
function wireTooltip(figure, svg, tip) {
  const show = (target) => {
    const label = target?.dataset?.tip;
    if (!label) return;
    tip.textContent = label;
    tip.hidden = false;
    const box = target.getBoundingClientRect();
    const host = figure.getBoundingClientRect();
    tip.style.left = `${Math.max(0, Math.min(box.left - host.left + box.width / 2, host.width))}px`;
    tip.style.top = `${Math.max(0, box.top - host.top - 8)}px`;
  };
  const hide = () => { tip.hidden = true; };

  svg.addEventListener('pointerover', (e) => show(e.target.closest('.a-point')));
  svg.addEventListener('pointerout', hide);
  svg.addEventListener('focusin', (e) => show(e.target.closest('.a-point')));
  svg.addEventListener('focusout', hide);
  /* Escape dismisses it without moving focus, the way a tooltip should. */
  svg.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
}

/* --- panels ---------------------------------------------------------------- */

/**
 * A panel with a heading and a subtitle.
 *
 * `sub` is not optional decoration. Every panel that shows a window names that
 * window in its subtitle — the Audience tab's whole reason for existing is that
 * the old media kit claimed India 54% from a window it never printed.
 */
export function panel({ title, sub, width = '', id = '' }) {
  const section = html('section', `a-panel ${width}`.trim());
  if (id) section.id = id;
  const header = document.createElement('header');
  header.appendChild(html('h2', null, title));
  if (sub) {
    const s = html('span', 'sub');
    /* A Node or a string, never innerHTML: half of what lands in a subtitle is
       a guest name or a post caption straight off a platform. */
    if (sub instanceof Node) s.appendChild(sub);
    else s.textContent = sub;
    header.appendChild(s);
  }
  section.appendChild(header);
  return section;
}

/**
 * A subtitle fragment that names a window, for the panels that show one.
 * `sub: windowSub('Views by platform', from, to)` rather than a hand-built
 * string, so every panel spells its window the same way.
 */
export function windowSub(text, from, to, extra = '') {
  const frag = document.createDocumentFragment();
  if (text) frag.append(document.createTextNode(`${text} · `));
  frag.appendChild(html('b', 'a-window', rangeLabel(from, to)));
  if (extra) frag.append(document.createTextNode(` · ${extra}`));
  return frag;
}

/** A named empty state. Never a blank panel. */
export const empty = (message) => html('p', 'a-empty', message);

/** A panel-level error. The rest of the tab still draws. */
export const errorNote = (reason) => html('p', 'a-error', reason);

/** A "this platform does not report that" note. Not the same as a zero. */
export const notReported = (what) => html('p', 'a-note', what);
