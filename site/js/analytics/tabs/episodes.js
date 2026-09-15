/* Episodes — "what did one episode deliver?"
 *
 * One row per episode: the long cut on YouTube, every clip the collector matched
 * to it, split by platform, and the sum across all cuts. From a row, the two
 * artifacts a sponsor and a guest receive.
 *
 * These figures are LIFETIME. The time frame above does not apply to them, and
 * the panel says so on screen rather than leaving a reader to assume that a
 * 7-day frame means seven days of episode views.
 */

import { episodes, episodeClips, posts } from '../data.js';
import {
  chart, windowSub, resultPanel, table, postLink, platformCell,
  full, compact, fmtRate, periodLabel, periodLong, el, empty, errorNote,
  PLATFORM_NAME, PLATFORM_ORDER,
} from './shared.js';
import { artifactBar as artifactButtons, forScope } from '../artifacts/index.js';

export async function episodesTab(mount, { window: w }) {
  const [rollup, allPosts] = await Promise.all([episodes(), postsForUnassigned(w)]);

  mount.replaceChildren(
    episodesPanel(rollup, w),
    unassignedPanel(allPosts, w),
  );
}

/* All platforms whatever the control says: a clip is unassigned regardless of
   where it was posted, and hiding two thirds of the list behind a platform
   filter would make "everything is matched" look true when it is not. */
const postsForUnassigned = (w) => posts({ ...w, platform: 'all', compare: false });

/* --- the episodes table ---------------------------------------------------- */

function episodesPanel(result, w) {
  return resultPanel(result, {
    title: 'Episodes',
    /* The window is named even though it does not apply, because a panel with
       no window label on a page full of windowed panels reads as "the window
       above" by default. Saying which it is costs one line. */
    sub: windowSub('Lifetime totals, not the frame above', w.from, w.to,
                   'the time frame does not apply to these figures'),
    emptyMessage: 'No episodes in the database yet.',
  }, (section, { current }) => {
    if (!current.rows.length) return false;

    const wrap = el('div', 'a-tablewrap');
    const t = el('table', 'a-table');
    const thead = document.createElement('thead');
    const hr = document.createElement('tr');
    hr.appendChild(el('th', 'a-expandcol'));
    for (const c of COLUMNS) {
      const th = el('th', c.num ? 'num' : '', c.name);
      th.scope = 'col';
      hr.appendChild(th);
    }
    thead.appendChild(hr);
    t.appendChild(thead);

    const tbody = document.createElement('tbody');
    for (const row of current.rows) tbody.appendChild(episodeRow(row, w));
    t.appendChild(tbody);
    wrap.appendChild(t);
    section.appendChild(wrap);

    section.appendChild(el('p', 'a-note',
      '"All cuts" is a SUM OF VIEW COUNTS across the episode’s long cut and every '
      + 'clip matched to it. It is not reach in the advertising sense and it is not '
      + 'people: someone who watches the episode and then sees two clips is three in '
      + 'that number. The episode report carries the same sentence, because a sponsor '
      + 'will ask.'));
    return true;
  });
}

const COLUMNS = [
  { key: 'episode', name: 'Episode', cell: (r) => el('span', null, `S${r.season} E${r.number}`) },
  { key: 'guest', name: 'Guest', cell: (r) => el('b', null, r.guest) },
  { key: 'role', name: 'Role', wide: true },
  { key: 'publishedAt', name: 'Published',
    cell: (r) => el('span', null, r.publishedAt ? periodLabel(r.publishedAt, 'day') : '—'),
    title: (r) => (r.publishedAt ? periodLong(r.publishedAt, 'day') : '') },
  { key: 'ytViews', name: 'YouTube', num: true, format: full },
  { key: 'clipCount', name: 'Clips', num: true, format: full },
  { key: 'clipYt', name: 'Clip views · YT', num: true, format: full,
    value: (r) => r.clipViews.youtube },
  { key: 'clipIg', name: 'Clip views · IG', num: true, format: full,
    value: (r) => r.clipViews.instagram },
  { key: 'clipTt', name: 'Clip views · TT', num: true, format: full,
    value: (r) => r.clipViews.tiktok },
  { key: 'totalReach', name: 'All cuts', num: true, format: full },
];

function episodeRow(row, w) {
  const tr = document.createElement('tr');
  tr.dataset.episodeId = String(row.episodeId);

  const toggleCell = el('td', 'a-expandcol');
  const toggle = el('button', 'a-expand', '▸');
  toggle.type = 'button';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-label', `Show the cuts and exports for ${row.guest}`);
  toggleCell.appendChild(toggle);
  tr.appendChild(toggleCell);

  for (const c of COLUMNS) {
    const td = el('td', [c.num ? 'num' : '', c.wide ? 'wide' : ''].filter(Boolean).join(' '));
    if (c.cell) {
      td.appendChild(c.cell(row));
      if (c.title?.(row)) td.title = c.title(row);
    } else {
      const raw = c.value ? c.value(row) : row[c.key];
      if (raw == null || raw === '') {
        td.textContent = '—';
        td.classList.add('none');
      } else {
        td.textContent = c.format ? c.format(raw) : String(raw);
        if (typeof raw === 'number') td.dataset.value = String(raw);
      }
    }
    tr.appendChild(td);
  }

  toggle.addEventListener('click', () => expand(tr, toggle, row, w));
  return tr;
}

/* --- the expansion: cuts, split, and the two artifacts --------------------- */

async function expand(tr, toggle, row, w) {
  if (toggle.getAttribute('aria-expanded') === 'true') {
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
  cell.appendChild(el('p', 'a-note', 'Reading the cuts…'));
  holder.appendChild(cell);
  tr.after(holder);

  const clips = await episodeClips(row.episodeId, w);
  if (!holder.isConnected) return;

  const body = document.createDocumentFragment();
  body.appendChild(artifactBar(row));
  body.appendChild(splitChart(row));

  if (!clips.ok) {
    body.appendChild(errorNote(clips.reason));
  } else {
    const cuts = clips.current.rows.filter((r) => r.postId !== `yt:${row.youtubeVideoId}`);
    body.appendChild(cuts.length
      ? table([
        { name: 'Platform', value: (r) => platformCell(r.platform) },
        { name: 'Published', value: (r) =>
          el('span', null, r.publishedAt ? periodLabel(r.publishedAt, 'day') : '—') },
        { name: 'Clip', value: (r) => postLink(r), wide: true },
        { name: 'Views', key: 'viewsEnd', num: true, format: full },
        { name: 'Likes', key: 'likes', num: true, format: full },
        { name: 'Comments', key: 'comments', num: true, format: full },
        { name: 'Shares', key: 'shares', num: true, format: full },
        { name: 'Engagement', key: 'rate', num: true, format: (v) => fmtRate(v) },
      ], cuts)
      : empty('No clips have been matched to this episode yet.'));
  }
  cell.replaceChildren(body);
}

/** Where the episode's views came from. A proportion bar with its numbers. */
function splitChart(row) {
  const points = [
    { label: 'YouTube, long cut', value: row.ytViews },
    ...PLATFORM_ORDER.map((p) => ({
      label: `${PLATFORM_NAME[p]} clips`, value: row.clipViews[p],
    })),
  ].filter((p) => p.value > 0);

  if (!points.length) return empty('No views recorded for any cut of this episode yet.');

  return chart({
    kind: 'hbar',
    name: `Where ${row.guest}'s episode was watched`,
    points,
    format: compact,
    summary: 'Show the split',
  });
}

/**
 * The artifacts an episode row produces: the report to its sponsor, the card to
 * its guest. Both come out of the registry, which renders the recipient and the
 * reason beside each button.
 */
const artifactBar = (row) => artifactButtons(forScope('episode'), () => ({ episode: row }));

/* --- unassigned ------------------------------------------------------------ */

/**
 * Clips the collector could not match to an episode.
 *
 * Read-only. Spec §4 describes assigning them by hand here; this dashboard
 * does not write, and the assignment lives in `data/episodes.json` plus the
 * collector's title match instead. The panel says where to go rather than
 * pretending the list is complete.
 */
function unassignedPanel(result, w) {
  return resultPanel(result, {
    title: 'Unassigned clips',
    sub: windowSub('Posts the collector could not match to an episode', w.from, w.to),
    emptyMessage: 'Every post in this window is matched to an episode.',
  }, (section, { current }) => {
    const rows = current.rows.filter((r) => r.episodeId == null);
    if (!rows.length) return false;

    section.appendChild(table([
      { name: 'Platform', value: (r) => platformCell(r.platform) },
      { name: 'Published', value: (r) =>
        el('span', null, r.publishedAt ? periodLabel(r.publishedAt, 'day') : '—') },
      { name: 'Post', value: (r) => postLink(r), wide: true },
      { name: 'Views', key: 'viewsEnd', num: true, format: full },
    ], rows));
    section.appendChild(el('p', 'a-note',
      'Matching is by title: the collector looks for the guest’s name or the '
      + 'episode number in the caption. To assign one of these, add a match term '
      + 'to data/episodes.json and let the next collector run pick it up. This '
      + 'page only reads.'));
    return true;
  });
}
