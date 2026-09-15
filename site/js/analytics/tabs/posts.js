/* Posts — "what performed?"
 *
 * Every post, sortable on every column, filterable by platform and by title.
 * Click a row and it expands its own view curve inline.
 *
 * The state below is module-level on purpose: the posts-table artifact exports
 * THE TAB'S CURRENT VIEW — its sort and its filters — rather than a fresh
 * unsorted query. Someone who has narrowed the table to Instagram clips about
 * one guest and then hits Export expects that spreadsheet, not a different one.
 */

import { posts, postHistory } from '../data.js';
import {
  chart, windowSub, resultPanel, postLink, platformCell, full, compact,
  fmtRate, periodLabel, periodLong, clip, el, empty, errorNote,
  PLATFORM_NAME,
} from './shared.js';

/** Read by artifacts/index.js. The tab's current view, not a query. */
export const postsView = {
  sort: { key: 'viewsGained', dir: 'desc' },
  search: '',
  rows: [],          // filtered and sorted, exactly as drawn
  window: null,
  platform: 'all',
};

const COLUMNS = [
  { key: 'platform', name: 'Platform', cell: (r) => platformCell(r.platform),
    sortValue: (r) => PLATFORM_NAME[r.platform] ?? r.platform },
  { key: 'publishedAt', name: 'Published',
    cell: (r) => el('span', null, r.publishedAt ? periodLabel(r.publishedAt, 'day') : '—'),
    title: (r) => (r.publishedAt ? periodLong(r.publishedAt, 'day') : ''),
    sortValue: (r) => (r.publishedAt ? r.publishedAt.getTime() : 0) },
  { key: 'title', name: 'Post', wide: true, cell: (r) => postLink(r),
    sortValue: (r) => (r.title || r.postId).toLowerCase() },
  { key: 'viewsEnd', name: 'Views', num: true, format: full },
  { key: 'likes', name: 'Likes', num: true, format: full },
  { key: 'comments', name: 'Comments', num: true, format: full },
  { key: 'shares', name: 'Shares', num: true, format: full },
  /* Instagram reports reach; the other two do not, and the cell says so rather
     than printing a zero that would read as "nobody saw it". */
  { key: 'reach', name: 'Reach', num: true, format: full },
  { key: 'rate', name: 'Engagement', num: true, format: (v) => fmtRate(v) },
  { key: 'viewsGained', name: 'Gained here', num: true, format: full },
];

export const POSTS_COLUMNS = COLUMNS;

export async function postsTab(mount, { state, window: w }) {
  const result = await posts(w);
  postsView.window = w;
  postsView.platform = w.platform;

  mount.replaceChildren(resultPanel(result, {
    title: 'Posts',
    sub: windowSub(
      w.platform === 'all' ? 'Every post' : `${PLATFORM_NAME[w.platform]} posts`,
      w.from, w.to,
      '"gained here" is the change inside this window; every other figure is lifetime'),
    emptyMessage: 'No posts existed in this window.',
  }, (section, { current }) => {
    if (!current.rows.length) {
      postsView.rows = [];
      return false;
    }
    section.appendChild(searchRow(current.rows, section, w));
    section.appendChild(el('div', 'a-postsbody'));
    drawTable(section, current.rows, w);
    return true;
  }));
}

/* --- the filter row -------------------------------------------------------- */

function searchRow(rows, section, w) {
  const bar = el('div', 'a-filters');

  const label = el('label', 'a-check');
  label.htmlFor = 'posts-search';
  label.textContent = 'Title contains';
  const input = document.createElement('input');
  input.type = 'search';
  input.id = 'posts-search';
  input.className = 'a-date';
  input.value = postsView.search;
  input.placeholder = 'guest name, hashtag, anything';
  input.addEventListener('input', () => {
    postsView.search = input.value;
    drawTable(section, rows, w);
  });
  bar.append(label, input);

  const count = el('span', 'a-count');
  count.id = 'posts-count';
  bar.appendChild(count);

  /* The platform filter is the global control, not a second one here. Two
     controls that mean the same thing is how a dashboard starts lying. */
  bar.appendChild(el('span', 'a-note',
    'Platform is the control above, so the filter and the charts always agree.'));
  return bar;
}

/* --- sorting and filtering ------------------------------------------------- */

function visible(rows) {
  const needle = postsView.search.trim().toLowerCase();
  const filtered = needle
    ? rows.filter((r) => `${r.title ?? ''} ${r.postId}`.toLowerCase().includes(needle))
    : [...rows];

  const column = COLUMNS.find((c) => c.key === postsView.sort.key) ?? COLUMNS[0];
  const value = column.sortValue ?? ((r) => r[column.key]);
  const dir = postsView.sort.dir === 'asc' ? 1 : -1;

  filtered.sort((a, b) => {
    const x = value(a);
    const y = value(b);
    /* Nulls last whichever way the column is sorted. "Not reported" is not the
       smallest value; it is not a value. */
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    if (typeof x === 'number' && typeof y === 'number') return (x - y) * dir;
    return String(x).localeCompare(String(y)) * dir;
  });
  return filtered;
}

/* --- the table ------------------------------------------------------------- */

function drawTable(section, allRows, w) {
  const body = section.querySelector('.a-postsbody');
  const rows = visible(allRows);
  postsView.rows = rows;

  const count = section.querySelector('#posts-count');
  if (count) {
    count.textContent = rows.length === allRows.length
      ? `${full(rows.length)} posts`
      : `${full(rows.length)} of ${full(allRows.length)} posts`;
  }

  if (!rows.length) {
    body.replaceChildren(empty(`No post title contains "${postsView.search}".`));
    return;
  }

  const wrap = el('div', 'a-tablewrap');
  const table = el('table', 'a-table a-sortable');

  const thead = document.createElement('thead');
  const hr = document.createElement('tr');
  hr.appendChild(el('th', 'a-expandcol'));            // the expand toggles
  for (const c of COLUMNS) {
    const th = el('th', c.num ? 'num' : '');
    th.scope = 'col';
    const button = el('button', 'a-sort', c.name);
    button.type = 'button';
    button.dataset.sort = c.key;
    const active = postsView.sort.key === c.key;
    th.setAttribute('aria-sort', active
      ? (postsView.sort.dir === 'asc' ? 'ascending' : 'descending') : 'none');
    if (active) button.appendChild(el('i', 'a-sortmark', postsView.sort.dir === 'asc' ? '▲' : '▼'));
    button.addEventListener('click', () => {
      postsView.sort = postsView.sort.key === c.key
        ? { key: c.key, dir: postsView.sort.dir === 'asc' ? 'desc' : 'asc' }
        /* First click on a new column: numbers descend (the biggest is what you
           were looking for), text ascends (A first). */
        : { key: c.key, dir: c.num ? 'desc' : 'asc' };
      drawTable(section, allRows, w);
    });
    th.appendChild(button);
    hr.appendChild(th);
  }
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (const row of rows) tbody.appendChild(postRow(row, w));
  table.appendChild(tbody);

  wrap.appendChild(table);
  body.replaceChildren(wrap);
}

function postRow(row, w) {
  const tr = document.createElement('tr');
  tr.dataset.postId = row.postId;

  const toggleCell = el('td', 'a-expandcol');
  const toggle = el('button', 'a-expand', '▸');
  toggle.type = 'button';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-label', `Show the view curve for ${clip(row.title, 40) || row.postId}`);
  toggleCell.appendChild(toggle);
  tr.appendChild(toggleCell);

  for (const c of COLUMNS) {
    const td = el('td', [c.num ? 'num' : '', c.wide ? 'wide' : ''].filter(Boolean).join(' '));
    if (c.cell) {
      td.appendChild(c.cell(row));
      if (c.title?.(row)) td.title = c.title(row);
    } else {
      const raw = row[c.key];
      if (raw == null) {
        td.textContent = '—';
        td.classList.add('none');
        td.title = 'Not reported by this platform';
      } else {
        td.textContent = c.format ? c.format(raw) : String(raw);
        td.dataset.value = String(raw);
        if (typeof raw === 'number' && raw < 0) td.classList.add('neg');
      }
    }
    tr.appendChild(td);
  }

  toggle.addEventListener('click', () => expand(tr, toggle, row, w));
  return tr;
}

/* --- the inline growth curve ----------------------------------------------- */

async function expand(tr, toggle, row, w) {
  const open = toggle.getAttribute('aria-expanded') === 'true';
  if (open) {
    tr.nextElementSibling?.remove();
    toggle.setAttribute('aria-expanded', 'false');
    toggle.textContent = '▸';
    return;
  }
  toggle.setAttribute('aria-expanded', 'true');
  toggle.textContent = '▾';

  const holder = document.createElement('tr');
  holder.className = 'a-expanded';
  const cell = document.createElement('td');
  cell.colSpan = COLUMNS.length + 1;
  cell.appendChild(el('p', 'a-note', 'Reading the snapshots…'));
  holder.appendChild(cell);
  tr.after(holder);

  const history = await postHistory(row.postId, w);
  /* The user may have collapsed it, re-sorted, or left the tab while that was
     in flight. */
  if (!holder.isConnected) return;

  if (!history.ok) {
    cell.replaceChildren(errorNote(history.reason));
    return;
  }
  const series = history.current.series;
  if (series.length < 2) {
    cell.replaceChildren(empty(
      'Fewer than two snapshots inside this window, so there is no curve to draw. '
      + 'Widen the frame.'));
    return;
  }
  cell.replaceChildren(chart({
    kind: 'line',
    name: `Views over time for ${clip(row.title, 60) || row.postId}`,
    points: series.map((s) => ({
      label: periodLabel(s.period, w.granularity === 'hour' ? 'hour' : 'day'),
      values: { value: s.views },
    })),
    series: [{ id: 'value', name: 'Views' }],
    format: compact,
    summary: 'Show the snapshots',
  }));
}
