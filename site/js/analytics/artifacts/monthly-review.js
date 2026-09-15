/* The monthly review, printed.
 *
 * To Sunny and Thai Sikh News, once a month. One page: this month against last
 * by platform — views, net followers, posts published — the five posts that
 * carried it, and the audience shift. Every chart has its table, open, because
 * a collapsed <details> in a PDF is a table nobody can reach.
 *
 * The XLSX is the same numbers from the same module, so the two cannot drift.
 */

import { chart } from '../charts.js';
import { full, rate, bkk, signed, signedPct, signedPoints, delta, ARROW, clip,
         PLATFORM_NAME } from '../format.js';
import { filename } from './index.js';
import {
  gatherMonth, monthKey, monthName, viewsRows, followersRows, postsRows,
  audienceRows, summaryRows,
} from './monthly-review-data.js';
import { startArtifact, masthead, colophon, fig, printTable, el } from './page.js';

startArtifact({
  title: 'Monthly review',
  render: async (root, query) => {
    const key = query.month || monthKey(new Date());
    const data = await gatherMonth(key);
    const previousName = monthName(
      monthKey(new Date(+data.windows.previous.from + 24 * 3600 * 1000)));

    root.replaceChildren();
    root.appendChild(masthead('Monthly review', bkk(new Date().toISOString())));

    root.appendChild(title(data, previousName));
    root.appendChild(summary(data, previousName));
    root.appendChild(comparison('Views by platform', viewsRows(data), data, previousName, full));
    root.appendChild(comparison('Net followers by platform', followersRows(data), data,
                                previousName, full,
                                'Gained minus lost inside the month. Not the follower '
                                + 'count: a count beside a month name reads as a monthly '
                                + 'figure when it is a lifetime one.'));
    root.appendChild(comparison('Posts published', postsRows(data), data, previousName, full));
    root.appendChild(topPosts(data));
    root.appendChild(audienceShift(data));
    root.appendChild(await colophon(
      { platforms: 'all', from: data.windows.current.from, to: data.windows.current.to },
      ['Audience is YouTube’s rolling 90-day window for the CHANNEL, not the '
       + 'month and not per post. YouTube does not publish it any other way.'],
    ));

    /* Every table twin is opened. On screen a collapsed <details> is a
       convenience; on paper it is a table that did not print. */
    for (const twin of root.querySelectorAll('details.a-twin')) twin.open = true;

    return { filename: filename('monthly-review', data.key, 'pdf') };
  },
});

function title(data, previousName) {
  const section = el('section');
  section.appendChild(el('span', 'eyebrow', `Against ${previousName}`));
  section.appendChild(el('h1', null, data.name));
  section.appendChild(el('p', 'lede',
    'How the show moved this month, by platform, with the posts that carried it.'));
  return section;
}

/* --- the four figures ------------------------------------------------------ */

function summary(data, previousName) {
  const section = el('section');
  const figs = el('div', 'figs');
  for (const row of summaryRows(data)) {
    figs.appendChild(fig(
      row.label,
      row.now == null ? 'not read' : row.format(row.now),
      changeText(row.now, row.was, row.format, previousName),
    ));
  }
  section.appendChild(figs);
  return section;
}

/**
 * The change, in words, with its direction spelled out.
 *
 * On paper there is no hover and no colour worth relying on after a monochrome
 * print, so the arrow and the sign carry it. A rise from nothing says so rather
 * than printing an infinity.
 */
function changeText(now, was, format, previousName) {
  if (now == null || was == null) return `No comparable ${previousName} figure`;
  const d = delta(now, was);
  if (d.dir === 'flat') return `Unchanged against ${previousName}`;
  const amount = d.pct == null
    ? `${signed(d.abs)} from nothing`
    : `${signedPct(d.pct)} (${format(was)} in ${previousName})`;
  return `${ARROW[d.dir]} ${amount}`;
}

/* --- a platform comparison ------------------------------------------------- */

function comparison(heading, rows, data, previousName, format, note) {
  const section = el('section');
  section.appendChild(el('h2', null, heading));
  if (note) section.appendChild(el('p', 'fine', note));

  if (!rows.some((r) => r.now || r.was)) {
    section.appendChild(el('p', 'empty', `Nothing recorded for ${heading.toLowerCase()}.`));
    return section;
  }

  /* Grouped bars: two series, one axis, one unit. This month and last month are
     the same quantity measured twice, which is the only case where two series
     belong on one chart. */
  section.appendChild(chart({
    kind: 'bar',
    name: `${heading}, ${data.name} against ${previousName}`,
    points: rows.map((r) => ({
      label: r.platform,
      values: { now: r.now, previous: r.was },
    })),
    series: [{ id: 'now', name: data.name }, { id: 'previous', name: previousName }],
    format,
    rows: rows.map((r) => ({
      platform: r.platform, now: r.now, was: r.was, change: r.change,
    })),
    columns: [
      { key: 'platform', name: 'Platform' },
      { key: 'now', name: data.name, num: true, format },
      { key: 'was', name: previousName, num: true, format },
      { key: 'change', name: 'Change', num: true, format: (v) => signed(v) },
    ],
  }));
  return section;
}

/* --- top five -------------------------------------------------------------- */

function topPosts(data) {
  const section = el('section');
  section.appendChild(el('h2', null, 'The five posts that carried the month'));

  if (!data.posts.ok) {
    section.appendChild(el('p', 'problem', data.posts.reason));
    return section;
  }
  if (!data.topPosts.length) {
    section.appendChild(el('p', 'empty', 'No post gained views this month.'));
    return section;
  }
  section.appendChild(printTable([
    { name: 'Platform', value: (r) => PLATFORM_NAME[r.platform] ?? r.platform },
    { name: 'Published', value: (r) => (r.publishedAt ? bkk(r.publishedAt.toISOString()) : null) },
    { name: 'Post', value: (r) => clip(r.title, 58) || r.postId },
    { name: 'Views gained', key: 'viewsGained', num: true, format: full },
    { name: 'Views total', key: 'viewsEnd', num: true, format: full },
    { name: 'Engagement', key: 'rate', num: true, format: (v) => rate(v) },
  ], data.topPosts));
  section.appendChild(el('p', 'fine',
    '"Views gained" is the change inside this month; "views total" is lifetime. '
    + 'A post published this month counts its whole total as gained.'));
  return section;
}

/* --- the audience shift ---------------------------------------------------- */

function audienceShift(data) {
  const section = el('section');
  section.appendChild(el('h2', null, 'Where the audience is'));

  if (!data.country.ok) {
    section.appendChild(el('p', 'problem', data.country.reason));
    return section;
  }
  const rows = audienceRows(data);
  if (!rows.length) {
    section.appendChild(el('p', 'empty', 'No country data collected yet.'));
    return section;
  }
  if (!data.country.current.prevWindow) {
    section.appendChild(el('p', 'fine',
      'No comparable earlier window yet, so the shift column is empty. It fills '
      + 'in as the history builds.'));
  }
  section.appendChild(printTable([
    { name: 'Country', value: (r) => r.dimension },
    { name: 'Share', key: 'share', num: true, format: (v) => `${v}%` },
    { name: 'Share before', key: 'prevShare', num: true, format: (v) => `${v}%` },
    { name: 'Shift', key: 'points', num: true, format: (v) => signedPoints(v) },
    { name: 'Views', key: 'views', num: true, format: full },
  ], rows));
  return section;
}
