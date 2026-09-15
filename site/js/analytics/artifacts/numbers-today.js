/* The numbers, frozen at a date.
 *
 * To a sponsor who asks for a deck. The live page's figures, as they stood on a
 * chosen day, in the public page's shape: one number, the platform split, when
 * the views happened, who is watching, what is playing now.
 *
 * The reason it exists: /live is always now, and a deck is not. Somebody
 * assembling a pitch in October needs the figures as at the end of September,
 * and screenshotting the live page in October and captioning it "September" is
 * exactly the hand-typed claim this whole project replaced.
 *
 * Built from the windowed functions rather than from live_json(), which only
 * ever answers "now" — see §6 of the data contract.
 */

import { posts, followers, audience, windowFor, bangkokDate, addPeriods } from '../data.js';
import {
  full, compact, pct, bkk, clip, dimensionLabel, rangeLabel, PLATFORM_NAME, STACK,
} from '../format.js';
import { filename } from './index.js';
import { startArtifact, masthead, colophon, fig, printTable, proportionBar, el } from './page.js';

/* PRODUCT.md, principle 3: a lifetime total sits next to a momentum figure.
   Ninety days is the window the public pages already use for momentum. */
const MOMENTUM_DAYS = 90;

startArtifact({
  title: 'Numbers as of today',
  render: async (root, query) => {
    const asAt = resolveDate(query.date);
    const from = addPeriods(asAt, 'day', -MOMENTUM_DAYS);
    const window_ = { from, to: asAt, granularity: 'day', platform: 'all', compare: false };

    const [postResult, followerResult, countries, ages] = await Promise.all([
      posts(window_),
      followers({ ...window_, from: addPeriods(asAt, 'day', -30) }),
      audience('yt_country', 90),
      audience('yt_age', 90),
    ]);
    if (!postResult.ok) throw new Error(postResult.reason);

    const rows = postResult.current.rows;
    const platforms = summarise(rows, followerResult);
    const totals = {
      views: rows.reduce((a, r) => a + r.viewsEnd, 0),
      gained: rows.reduce((a, r) => a + r.viewsGained, 0),
      followers: Object.values(platforms).reduce((a, p) => a + (p.followers ?? 0), 0),
      posts: rows.length,
    };

    root.replaceChildren();
    root.appendChild(masthead('The numbers', bkk(asAt.toISOString())));
    root.appendChild(oneNumber(asAt, totals, platforms));
    root.appendChild(legend(platforms));
    root.appendChild(whenTheViewsHappened(rows));
    root.appendChild(whoIsWatching(countries, ages));
    root.appendChild(nowPlaying(rows));
    root.appendChild(await colophon(
      { platforms: 'all', from, to: asAt },
      [`Every figure on this page is as at ${bkk(asAt.toISOString())}, Bangkok. `
       + 'It is not a live page and it does not update: that is the point of it.',
       'Platforms report with a delay of up to 48 hours, so the last two days of '
       + 'any window are still settling.'],
    ));

    return { filename: filename('numbers', bangkokStamp(asAt), 'pdf') };
  },
});

/** The chosen date's end of day, never later than now. */
function resolveDate(value) {
  if (value && !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error(`"${value}" is not a date. Use YYYY-MM-DD.`);
  }
  const now = new Date();
  if (!value) return now;
  /* The last instant of the chosen Bangkok day, so "as at 30 September"
     includes the 30th rather than stopping at midnight on the 30th. The last
     instant, not the exclusive bound: midnight starting 1 October formats as
     1 October, and the page said "as at" the day after the one asked for
     (found 2026-09-16; the worker's run on the 15th never saw it, because a
     bound in the future is clamped to now). */
  const endOfDay = new Date(addPeriods(bangkokDate(value), 'day', 1).getTime() - 1);
  if (endOfDay > now) return now;
  return endOfDay;
}

const bangkokStamp = (date) =>
  date.toLocaleDateString('en-CA', { timeZone: 'Asia/Bangkok' });

/* --- the figures ----------------------------------------------------------- */

function summarise(rows, followerResult) {
  const out = {};
  for (const id of STACK) {
    const mine = rows.filter((r) => r.platform === id);
    const top = mine.reduce((best, r) => (!best || r.viewsEnd > best.viewsEnd ? r : best), null);
    out[id] = {
      id,
      name: PLATFORM_NAME[id],
      views: mine.reduce((a, r) => a + r.viewsEnd, 0),
      gained: mine.reduce((a, r) => a + r.viewsGained, 0),
      posts: mine.length,
      followers: followerResult.ok ? (followerResult.current.latest[id] ?? null) : null,
      top,
    };
  }
  return out;
}

function oneNumber(asAt, totals, platforms) {
  const section = el('section', 'card');
  section.appendChild(el('span', 'eyebrow', `As at ${bkk(asAt.toISOString())}`));

  /* The live page hard-codes millions in its hero, which is right for 2.36M and
     reads as "0.16M" for anything smaller — and a deck assembled early in a
     season is exactly when that happens. compact() picks the unit; the exact
     figure is in the sentence underneath either way. */
  const number = el('p', 'hero-number');
  const [, digits, unit] = compact(totals.views).match(/^([\d.,]+)([A-Za-z]*)$/);
  number.append(document.createTextNode(digits));
  if (unit) number.appendChild(el('i', null, unit));
  section.appendChild(number);

  section.appendChild(el('p', 'lede',
    `views across YouTube, Instagram and TikTok. ${full(totals.views)} exactly, `
    + `on ${full(totals.posts)} posts — and ${full(totals.gained)} of them arrived in `
    + `the last ${MOMENTUM_DAYS} days.`));

  section.appendChild(proportionBar(
    STACK.map((id) => ({ id, name: platforms[id].name, value: platforms[id].views })),
    full));

  const figs = el('div', 'figs');
  figs.appendChild(fig('Views, all time', full(totals.views)));
  figs.appendChild(fig(`Views, last ${MOMENTUM_DAYS} days`, full(totals.gained),
                       'The momentum figure, beside the lifetime one'));
  figs.appendChild(fig('Followers', full(totals.followers)));
  figs.appendChild(fig('Posts', full(totals.posts)));
  section.appendChild(figs);
  return section;
}

function legend(platforms) {
  const section = el('section');
  section.appendChild(el('h2', null, 'By platform'));
  section.appendChild(printTable([
    { name: 'Platform', value: (p) => p.name },
    { name: 'Views', key: 'views', num: true, format: full },
    { name: 'Share', num: true,
      value: (p) => `${pct(p.views, STACK.reduce((a, id) => a + platforms[id].views, 0))}%` },
    { name: `Last ${MOMENTUM_DAYS} days`, key: 'gained', num: true, format: full },
    { name: 'Followers', key: 'followers', num: true, format: full },
    { name: 'Posts', key: 'posts', num: true, format: full },
    { name: 'Best post', value: (p) => (p.top ? full(p.top.viewsEnd) : null) },
  ], STACK.map((id) => platforms[id])));
  return section;
}

/* --- when the views happened ---------------------------------------------- */

/**
 * Views by the month the post was PUBLISHED, which is the shape the live page
 * uses — it answers "when did the hits happen", not "when were they watched".
 * A post from last November that is still being watched counts in November.
 */
function whenTheViewsHappened(rows) {
  const section = el('section');
  section.appendChild(el('h2', null, 'When the hits happened'));
  section.appendChild(el('p', 'fine',
    'Views counted against the month the post was published, so a clip that is '
    + 'still being watched counts in the month it went out.'));

  const months = new Map();
  for (const row of rows) {
    if (!row.publishedAt) continue;
    const key = row.publishedAt.toLocaleDateString('en-CA',
      { timeZone: 'Asia/Bangkok' }).slice(0, 7);
    if (!months.has(key)) {
      months.set(key, { month: key, youtube: 0, instagram: 0, tiktok: 0, total: 0 });
    }
    const bucket = months.get(key);
    bucket[row.platform] += row.viewsEnd;
    bucket.total += row.viewsEnd;
  }
  const ordered = [...months.values()].sort((a, b) => a.month.localeCompare(b.month));
  if (!ordered.length) {
    section.appendChild(el('p', 'empty', 'No posts with a publication date.'));
    return section;
  }

  section.appendChild(printTable([
    { name: 'Month', value: (r) => bangkokDate(`${r.month}-01`)
      .toLocaleDateString('en-GB', { timeZone: 'Asia/Bangkok', month: 'short', year: 'numeric' }) },
    { name: 'YouTube', key: 'youtube', num: true, format: full },
    { name: 'Instagram', key: 'instagram', num: true, format: full },
    { name: 'TikTok', key: 'tiktok', num: true, format: full },
    { name: 'Total', key: 'total', num: true, format: full },
  ], ordered));
  return section;
}

/* --- who is watching ------------------------------------------------------- */

function whoIsWatching(countries, ages) {
  const section = el('section');
  section.appendChild(el('h2', null, 'Who is watching'));

  const known = countries.ok && countries.current.window;
  section.appendChild(el('p', 'fine', known
    ? 'YouTube, for the channel. Window: '
      + `${rangeLabel(countries.current.window.start, countries.current.window.end)}. `
      + 'This window is YouTube’s, not the date above — it is the only one they publish.'
    : 'YouTube, for the channel.'));

  const grid = el('div');
  grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:10pt';
  for (const [result, kind, label] of [[countries, 'yt_country', 'Country'],
                                       [ages, 'yt_age', 'Age']]) {
    const box = el('div');
    box.appendChild(el('h3', null, label));
    if (!result.ok) box.appendChild(el('p', 'problem', result.reason));
    else if (!result.current.rows.length) box.appendChild(el('p', 'empty', 'Nothing collected yet.'));
    else {
      box.appendChild(printTable([
        { name: label, value: (r) => dimensionLabel(kind, r.dimension) },
        { name: 'Share', num: true, value: (r) => `${Math.round((r.share ?? 0) * 1000) / 10}%` },
      ], result.current.rows.slice(0, 8)));
    }
    grid.appendChild(box);
  }
  section.appendChild(grid);
  return section;
}

/* --- now playing ----------------------------------------------------------- */

function nowPlaying(rows) {
  const section = el('section');
  section.appendChild(el('h2', null, 'Playing now'));

  const recent = rows
    .filter((r) => r.publishedAt)
    .sort((a, b) => b.publishedAt - a.publishedAt)
    .slice(0, 3);
  const best = [...rows].sort((a, b) => b.viewsEnd - a.viewsEnd).slice(0, 6);

  if (recent.length) {
    section.appendChild(el('h3', null, 'Most recent'));
    section.appendChild(postsTable(recent));
  }
  section.appendChild(el('h3', null, 'Most watched'));
  section.appendChild(best.length ? postsTable(best) : el('p', 'empty', 'No posts yet.'));
  return section;
}

const postsTable = (rows) => printTable([
  { name: 'Platform', value: (r) => PLATFORM_NAME[r.platform] ?? r.platform },
  { name: 'Published', value: (r) => (r.publishedAt ? bkk(r.publishedAt.toISOString()) : null) },
  { name: 'Post', value: (r) => clip(r.title, 58) || r.postId },
  { name: 'Views', key: 'viewsEnd', num: true, format: full },
], rows);
