/* What every tab needs and none of them should write twice.
   Renderers only: nothing here fetches, and nothing here converts a date. */

import {
  chart, panel, windowSub, empty, errorNote, notReported, seriesColor,
} from '../charts.js';
import {
  full, compact, rate as fmtRate, delta, signed, signedPct, ARROW,
  periodLabel, periodLong, rangeLabel, PLATFORM_NAME, clip,
} from '../format.js';
import { byPeriod } from '../data.js';

export {
  chart, panel, windowSub, empty, errorNote, notReported, seriesColor,
  full, compact, fmtRate, delta, signed, signedPct, ARROW,
  periodLabel, periodLong, rangeLabel, PLATFORM_NAME, clip,
};

export const PLATFORM_ORDER = ['youtube', 'instagram', 'tiktok'];

export const el = (name, className, text) => {
  const node = document.createElement(name);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
};

/** The series a chart should draw, honouring the platform control. */
export function seriesFor(platform) {
  const ids = platform === 'all' ? PLATFORM_ORDER : [platform];
  return ids.map((id) => ({ id, name: PLATFORM_NAME[id] }));
}

/**
 * Fold `{period, platform, …}` rows into chart points.
 *
 * Labels come from format.periodLabel, which is Bangkok-aware. A tab that built
 * its own label would be doing date maths, which is the one thing tabs are not
 * allowed to do.
 */
export function pointsFor(rows, valueKey, granularity, series) {
  return byPeriod(rows, valueKey).map((r) => ({
    label: periodLabel(r.period, granularity),
    values: Object.fromEntries(series.map((s) => [s.id, r[s.id] ?? null])),
  }));
}

/**
 * A delta, as position rather than deficit.
 *
 * Three channels, always: a sign, an arrow, and a colour. Green against red is
 * the pair a dichromat viewer cannot separate, so the colour is the last of the
 * three and never the only one.
 *
 * A rise from zero has no percentage. It says so in words rather than printing
 * an infinity, because this figure ends up on a sponsor's PDF.
 */
export function deltaEl(current, previous, { since = 'previous period', format = full } = {}) {
  const span = el('span', 'a-delta');
  if (previous == null || current == null) {
    span.dataset.dir = 'flat';
    span.appendChild(el('span', 'since', 'no comparison'));
    return span;
  }
  const d = delta(current, previous);
  span.dataset.dir = d.dir;
  span.appendChild(el('i', 'arrow', ARROW[d.dir]));
  span.append(document.createTextNode(
    d.pct == null ? `${signed(d.abs)} from nothing` : signedPct(d.pct)));
  span.appendChild(el('span', 'since', `${signed(d.abs)} vs ${since}`.replace('+', '+')));
  span.title = `${format(previous)} → ${format(current)}`;
  return span;
}

/** A headline figure: the number, its name, and its change. */
export function figure(label, value, { delta: deltaNode, note, format = full } = {}) {
  const box = el('div', 'a-fig');
  box.appendChild(el('span', 'k', label));
  const n = el('span', 'n', value == null ? '—' : format(value));
  if (value != null && format !== full) n.title = full(value);
  box.appendChild(n);
  if (deltaNode) box.appendChild(deltaNode);
  if (note) box.appendChild(el('span', 'since', note));
  return box;
}

/**
 * A panel that knows what to do with a `{ok:false}`.
 *
 * The rest of the tab still draws. There is no path where one dead endpoint
 * blanks a screen.
 */
export function resultPanel(result, spec, draw) {
  const section = panel(spec);
  if (!result?.ok) {
    section.appendChild(errorNote(result?.reason ?? 'No answer from the database.'));
    return section;
  }
  const drawn = draw(section, result);
  if (drawn === false) section.appendChild(empty(spec.emptyMessage ?? 'Nothing in this window.'));
  return section;
}

/** A plain table. The sortable one lives in the Posts tab, which needs it. */
export function table(columns, rows, { emptyMessage = 'Nothing to show.' } = {}) {
  if (!rows.length) return empty(emptyMessage);
  const wrap = el('div', 'a-tablewrap');
  const t = el('table', 'a-table');

  const thead = document.createElement('thead');
  const hr = document.createElement('tr');
  for (const c of columns) {
    const th = el('th', c.num ? 'num' : '', c.name);
    th.scope = 'col';
    hr.appendChild(th);
  }
  thead.appendChild(hr);
  t.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (const row of rows) {
    const tr = document.createElement('tr');
    for (const c of columns) {
      const td = el('td', [c.num ? 'num' : '', c.wide ? 'wide' : ''].filter(Boolean).join(' '));
      const raw = c.value ? c.value(row) : row[c.key];
      if (raw == null) {
        /* "not reported" and "zero" are different answers and the table shows
           both. An em dash is not a nought. */
        td.textContent = '—';
        td.classList.add('none');
      } else if (raw instanceof Node) {
        td.appendChild(raw);
      } else {
        td.textContent = c.format ? c.format(raw) : String(raw);
        if (typeof raw === 'number') {
          td.dataset.value = String(raw);
          if (raw < 0) td.classList.add('neg');
        }
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  t.appendChild(tbody);
  wrap.appendChild(t);
  return wrap;
}

/** A post title as a link, clipped on a word and never mid-word. */
export function postLink(row, n = 70) {
  if (!row.url) return el('span', null, clip(row.title, n) || row.postId);
  const a = el('a', null, clip(row.title, n) || row.postId);
  a.href = row.url;
  a.target = '_blank';
  a.rel = 'noopener';
  a.title = row.title || row.postId;
  return a;
}

/** A platform name with its colour swatch, for a table cell. */
export function platformCell(platform) {
  const span = el('span', 'a-plat');
  const i = el('i');
  i.style.background = seriesColor(platform);
  span.append(i, document.createTextNode(PLATFORM_NAME[platform] ?? platform));
  return span;
}

/** The sentence a tab shows when the frame reaches back past the data. */
export const MEASURING_NOTE =
  'The collector has been recording since 14 September 2026; anything earlier '
  + 'has no snapshots to difference, so it reads as zero rather than as nothing.';
