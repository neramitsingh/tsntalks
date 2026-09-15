/* What the monthly review is made of.
 *
 * Shared by the printed page and the workbook, so the PDF and the XLSX cannot
 * disagree. If Sunny prints the review and opens the spreadsheet beside it, the
 * numbers must be the same numbers — which they are only if there is one place
 * that decides what they are, and this is it. */

import {
  views, followers, engagement, posts, audience, bangkokDate, addPeriods, floorPeriod,
} from '../data.js';
import { PLATFORM_NAME, PLATFORMS, full, rate, dimensionLabel } from '../format.js';

/** `2026-09` for the month containing `date`, in Bangkok. */
export function monthKey(date) {
  const start = floorPeriod(date instanceof Date ? date : new Date(date), 'month');
  return start.toLocaleDateString('en-CA', { timeZone: 'Asia/Bangkok' }).slice(0, 7);
}

/** The window for a `YYYY-MM`, and the one before it. */
export function monthWindows(key) {
  if (!/^\d{4}-\d{2}$/.test(key ?? '')) throw new Error(`"${key}" is not a month.`);
  const from = bangkokDate(`${key}-01`);
  const to = addPeriods(from, 'month', 1);
  const base = { granularity: 'day', platform: 'all', compare: false };
  return {
    current: { ...base, from, to },
    previous: { ...base, from: addPeriods(from, 'month', -1), to: from },
  };
}

export const monthName = (key) =>
  bangkokDate(`${key}-01`).toLocaleDateString('en-GB',
    { timeZone: 'Asia/Bangkok', month: 'long', year: 'numeric' });

const TOP_N = 5;

/**
 * Everything the review needs, for both months.
 *
 * A partial failure is survivable: a missing follower series leaves that panel
 * saying so, and the rest of the review still goes out. A month that has not
 * happened yet is not — that is a bad link, and it says so.
 */
export async function gatherMonth(key) {
  const windows = monthWindows(key);
  if (windows.current.from > new Date()) {
    throw new Error(`${monthName(key)} has not happened yet.`);
  }

  const [nowViews, wasViews, nowFollowers, wasFollowers,
         nowEngagement, wasEngagement, nowPosts, country] = await Promise.all([
    views(windows.current), views(windows.previous),
    followers(windows.current), followers(windows.previous),
    engagement(windows.current), engagement(windows.previous),
    posts(windows.current),
    audience('yt_country', 90),
  ]);

  return {
    key,
    name: monthName(key),
    windows,
    views: { now: nowViews, was: wasViews },
    followers: { now: nowFollowers, was: wasFollowers },
    engagement: { now: nowEngagement, was: wasEngagement },
    posts: nowPosts,
    country,
    topPosts: nowPosts.ok
      ? [...nowPosts.current.rows].sort((a, b) => b.viewsGained - a.viewsGained).slice(0, TOP_N)
      : [],
  };
}

/* --- the tables both formats share ---------------------------------------- */

/** Views this month against last, per platform. */
export function viewsRows(data) {
  const now = data.views.now.ok ? data.views.now.current.byPlatform : {};
  const was = data.views.was.ok ? data.views.was.current.byPlatform : {};
  return PLATFORMS.map((id) => ({
    id,
    platform: PLATFORM_NAME[id],
    now: now[id] ?? 0,
    was: was[id] ?? 0,
    change: (now[id] ?? 0) - (was[id] ?? 0),
  }));
}

/**
 * Followers GAINED this month against last, per platform.
 *
 * Gained, not the follower count. The count is a stock and the month-on-month
 * difference of a stock is the same number as the gain — but printing the stock
 * beside a month name invites "TikTok had 2,100 followers in September", which
 * is a lifetime figure wearing a month's clothes.
 */
export function followersRows(data) {
  const sum = (result, id) => (result.ok
    ? result.current.series.filter((r) => r.platform === id)
      .reduce((a, r) => a + r.gained - r.lost, 0)
    : 0);
  return PLATFORMS.map((id) => ({
    id,
    platform: PLATFORM_NAME[id],
    now: sum(data.followers.now, id),
    was: sum(data.followers.was, id),
    change: sum(data.followers.now, id) - sum(data.followers.was, id),
  }));
}

/** Posts published this month against last, per platform. */
export function postsRows(data) {
  const count = (result, id) => (result.ok
    ? result.current.series.filter((r) => r.platform === id)
      .reduce((a, r) => a + r.postsPublished, 0)
    : 0);
  return PLATFORMS.map((id) => ({
    id,
    platform: PLATFORM_NAME[id],
    now: count(data.views.now, id),
    was: count(data.views.was, id),
    change: count(data.views.now, id) - count(data.views.was, id),
  }));
}

/** The audience shift, in percentage points. */
export function audienceRows(data, limit = 8) {
  if (!data.country.ok) return [];
  return data.country.current.rows.slice(0, limit).map((r) => ({
    dimension: dimensionLabel('yt_country', r.dimension),
    share: r.share == null ? null : Math.round(r.share * 1000) / 10,
    prevShare: r.prevShare == null ? null : Math.round(r.prevShare * 1000) / 10,
    points: r.shareDelta == null ? null : Math.round(r.shareDelta * 10) / 10,
    views: Math.round(r.value),
  }));
}

/** The headline four, as `{ label, now, was, format }`. */
export function summaryRows(data) {
  const total = (r) => (r.ok ? r.current.total : null);
  const gained = (r) => (r.ok ? r.current.gained - r.current.lost : null);
  const published = (r) => (r.ok ? r.current.postsPublished : null);
  const engaged = (r) => (r.ok ? r.current.rate : null);

  return [
    { label: 'Views', now: total(data.views.now), was: total(data.views.was), format: full },
    { label: 'Net followers', now: gained(data.followers.now),
      was: gained(data.followers.was), format: full },
    { label: 'Posts published', now: published(data.views.now),
      was: published(data.views.was), format: full },
    { label: 'Engagement rate', now: engaged(data.engagement.now),
      was: engaged(data.engagement.was), format: (v) => rate(v) },
  ];
}

/* --- the workbook ---------------------------------------------------------- */

const platformColumns = (nowLabel, wasLabel) => [
  { name: 'Platform', raw: (r) => r.platform },
  { name: nowLabel, raw: (r) => r.now },
  { name: wasLabel, raw: (r) => r.was },
  { name: 'Change', raw: (r) => r.change },
];

/**
 * The sheets the XLSX carries: the underlying tables, one per chart on the PDF,
 * plus an About sheet with the provenance.
 */
export function workbookSheets(data, sourceText) {
  const now = data.name;
  const was = monthName(monthKey(addPeriods(data.windows.current.from, 'month', -1)));

  return [
    {
      name: 'Summary',
      columns: [
        { name: 'Figure', raw: (r) => r.label },
        { name: now, raw: (r) => r.now },
        { name: was, raw: (r) => r.was },
      ],
      rows: summaryRows(data),
    },
    { name: 'Views', columns: platformColumns(now, was), rows: viewsRows(data) },
    { name: 'Followers', columns: platformColumns(now, was), rows: followersRows(data) },
    { name: 'Posts published', columns: platformColumns(now, was), rows: postsRows(data) },
    {
      name: 'Top posts',
      columns: [
        { name: 'Platform', raw: (r) => PLATFORM_NAME[r.platform] ?? r.platform },
        { name: 'Published', raw: (r) => r.publishedAt },
        { name: 'Title', raw: (r) => r.title },
        { name: 'URL', raw: (r) => r.url },
        { name: 'Views gained in month', raw: (r) => r.viewsGained },
        { name: 'Views total', raw: (r) => r.viewsEnd },
        { name: 'Likes', raw: (r) => r.likes },
        { name: 'Comments', raw: (r) => r.comments },
        { name: 'Shares', raw: (r) => r.shares },
        { name: 'Engagement rate (fraction)', raw: (r) => r.rate },
      ],
      rows: data.topPosts,
    },
    {
      name: 'Audience',
      columns: [
        { name: 'Country', raw: (r) => r.dimension },
        { name: 'Share now (%)', raw: (r) => r.share },
        { name: 'Share before (%)', raw: (r) => r.prevShare },
        { name: 'Change (percentage points)', raw: (r) => r.points },
        { name: 'Views in window', raw: (r) => r.views },
      ],
      rows: audienceRows(data, 25),
    },
    {
      name: 'About',
      columns: [
        { name: 'Field', raw: (r) => r.field },
        { name: 'Value', raw: (r) => r.value },
      ],
      rows: [
        { field: 'Artifact', value: `TSN Talks — monthly review, ${now}` },
        { field: 'Produced', value: new Date() },
        { field: 'Compared with', value: was },
        { field: 'Note', value: 'Followers is the NET change in the month '
          + '(gained minus lost), not the follower count — a count beside a '
          + 'month name reads as a monthly figure when it is a lifetime one.' },
        { field: 'Note', value: 'Audience is YouTube’s rolling 90-day window '
          + 'for the CHANNEL, not the month, and not per post. YouTube does not '
          + 'publish it any other way.' },
        { field: 'Source', value: sourceText },
      ],
    },
  ];
}
