/* Formatting. Re-exports the public pages' formatters unchanged so that no two
   surfaces round the same figure differently, and adds the handful the
   dashboard needs on top.

   Nothing here fetches, and nothing here decides what a number means — that is
   data.js. This module turns a number into a string. */

export {
  full, compact, pct, ageBand, bkk, bkkStamp, COUNTRY,
  PLATFORMS, STACK, PLATFORM_NAME, PLATFORM_COLOR, PLATFORM_HANDLE, PLATFORM_URL,
} from '../live-data.js';

import { COUNTRY, ageBand, full } from '../live-data.js';

/* A real minus sign, not a hyphen. At tabular width a hyphen sits at a
   different height from the plus and the column stops lining up. */
export const MINUS = '−';

const BKK = { timeZone: 'Asia/Bangkok' };

/**
 * Change from `previous` to `current`.
 *
 * `pct` is null when there is nothing to divide by. A rise from zero is not
 * "+∞%" and it is not "+100%"; it is a rise from zero, and the renderer says
 * that in words. Getting this wrong puts an infinity on a sponsor's PDF.
 *
 * @returns {{abs: number|null, pct: number|null, dir: 'up'|'down'|'flat'}}
 */
export function delta(current, previous) {
  if (current == null || previous == null || !Number.isFinite(Number(current))
      || !Number.isFinite(Number(previous))) {
    return { abs: null, pct: null, dir: 'flat' };
  }
  const abs = Number(current) - Number(previous);
  const pct = Number(previous) === 0 ? null : abs / Number(previous);
  return { abs, pct, dir: abs > 0 ? 'up' : abs < 0 ? 'down' : 'flat' };
}

/** `+12,400`, `−3,100`, `0`. Always carries its sign; never bare. */
export function signed(n) {
  if (n == null || !Number.isFinite(Number(n))) return '—';
  const v = Number(n);
  if (v === 0) return '0';
  return (v > 0 ? '+' : MINUS) + full(Math.abs(v));
}

/** A delta as a percentage: `+12.4%`, `−3.1%`, or `—` when there is no base. */
export function signedPct(fraction) {
  if (fraction == null || !Number.isFinite(Number(fraction))) return '—';
  const v = Number(fraction) * 100;
  const sign = v > 0 ? '+' : v < 0 ? MINUS : '';
  return `${sign}${Math.abs(v).toFixed(1)}%`;
}

/** Percentage points, for demographic shifts. `+3.2pp`. */
export function signedPoints(points) {
  if (points == null || !Number.isFinite(Number(points))) return '—';
  const v = Number(points);
  const sign = v > 0 ? '+' : v < 0 ? MINUS : '';
  return `${sign}${Math.abs(v).toFixed(1)}pp`;
}

export const ARROW = { up: '▲', down: '▼', flat: '–' };

/** A period's label, always in Bangkok. `to` boundaries are never shown. */
export function periodLabel(date, granularity) {
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return '';
  switch (granularity) {
    case 'hour':
      return d.toLocaleTimeString('en-GB', { ...BKK, hour: '2-digit', minute: '2-digit' });
    case 'week':
      return `w/c ${d.toLocaleDateString('en-GB', { ...BKK, day: 'numeric', month: 'short' })}`;
    case 'month':
      return d.toLocaleDateString('en-GB', { ...BKK, month: 'short', year: 'numeric' });
    case 'day':
    default:
      return d.toLocaleDateString('en-GB', { ...BKK, day: 'numeric', month: 'short' });
  }
}

/** A longer label for tooltips and table twins: `Wed 9 Sep 2026, 14:00`. */
export function periodLong(date, granularity) {
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return '';
  const day = d.toLocaleDateString('en-GB', {
    ...BKK, weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  });
  if (granularity === 'hour') {
    return `${day}, ${d.toLocaleTimeString('en-GB', { ...BKK, hour: '2-digit', minute: '2-digit' })}`;
  }
  if (granularity === 'month') return periodLabel(d, 'month');
  if (granularity === 'week') return `week commencing ${day}`;
  return day;
}

const parts = (d) => ({
  day: d.toLocaleDateString('en-GB', { ...BKK, day: 'numeric' }),
  month: d.toLocaleDateString('en-GB', { ...BKK, month: 'short' }),
  year: d.toLocaleDateString('en-GB', { ...BKK, year: 'numeric' }),
});

/**
 * The string every panel subtitle uses to name its window: `9–15 Sep 2026`.
 *
 * `to` is exclusive everywhere in this dashboard, so the label shows the last
 * instant inside the window rather than the boundary after it. A window that
 * ends at midnight on the 16th is labelled the 15th, because that is the last
 * day anyone in it lived through.
 */
export function rangeLabel(from, to) {
  const a = from instanceof Date ? from : new Date(from);
  const b = new Date((to instanceof Date ? to : new Date(to)).getTime() - 1);
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return '';
  const p = parts(a);
  const q = parts(b);
  if (p.year !== q.year) return `${p.day} ${p.month} ${p.year} – ${q.day} ${q.month} ${q.year}`;
  if (p.month !== q.month) return `${p.day} ${p.month} – ${q.day} ${q.month} ${q.year}`;
  if (p.day !== q.day) return `${p.day}–${q.day} ${q.month} ${q.year}`;
  return `${q.day} ${q.month} ${q.year}`;
}

/**
 * An engagement rate. THE ONLY PLACE the ×100 happens.
 *
 * Everything upstream — post_snapshots.engagement_rate, rollup_engagement,
 * post_deltas — stores and returns a fraction, because that is what Zernio
 * sends. `null` is not zero: it means there were no views to divide by.
 */
export function rate(fraction, digits = 1) {
  if (fraction == null || !Number.isFinite(Number(fraction))) return '—';
  return `${(Number(fraction) * 100).toFixed(digits)}%`;
}

/** `42s`, `4m 12s`, `1h 04m`. metric_daily stores yt_avg_duration in seconds. */
export function duration(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s < 0) return '—';
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, '0')}s`;
  return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}m`;
}

/** How long ago, in the words the header uses. */
export function ago(ms) {
  if (ms == null || !Number.isFinite(Number(ms))) return 'unknown';
  const m = Math.floor(Number(ms) / 60000);
  if (m < 1) return 'just now';
  if (m === 1) return '1 minute ago';
  if (m < 60) return `${m} minutes ago`;
  const h = Math.floor(m / 60);
  if (h === 1) return '1 hour ago';
  if (h < 48) return `${h} hours ago`;
  return `${Math.floor(h / 24)} days ago`;
}

/**
 * The human name for a demographic dimension.
 *
 * Country codes go through the same COUNTRY map the public pages use, so the
 * dashboard and the media kit never spell a country two different ways. Ages
 * go through ageBand(), because YouTube labels its oldest band "65-".
 */
export function dimensionLabel(kind, dimension) {
  const d = String(dimension ?? '');
  if (kind.endsWith('_country')) return COUNTRY[d] ?? d;
  if (kind.endsWith('_age')) return ageBand(d);
  if (kind.endsWith('_gender')) return GENDER[d.toLowerCase()] ?? d;
  return d;
}

/* Instagram sends F/M/U; YouTube sends female/male/genderUserSpecified. Both
   end up in the same column, so both get spelled out. */
const GENDER = {
  f: 'Female', m: 'Male', u: 'Unspecified',
  female: 'Female', male: 'Male',
  genderuserspecified: 'Self-described',
};

/** The name for a metric_daily key, for axis labels and the "not reported" copy. */
export const METRIC_NAME = {
  yt_views: 'YouTube views',
  yt_minutes: 'Watch time (minutes)',
  yt_avg_duration: 'Average view duration',
  yt_subs_gained: 'Subscribers gained',
  yt_subs_lost: 'Subscribers lost',
  ig_reach: 'Instagram reach',
  ig_views: 'Instagram views',
  ig_engaged: 'Instagram accounts engaged',
  ig_interactions: 'Instagram interactions',
  ig_follows: 'Follows',
  ig_unfollows: 'Unfollows',
  tt_followers_gained: 'Followers gained',
  tt_followers_lost: 'Followers lost',
};

/** A caption clipped on a word, never mid-word. Same rule as /live. */
export function clip(text, n) {
  const one = String(text ?? '').split(/\r?\n/)[0].trim();
  if (one.length <= n) return one;
  const cut = one.slice(0, n);
  const sp = cut.lastIndexOf(' ');
  return `${(sp > n * 0.6 ? cut.slice(0, sp) : cut).replace(/[\s,.;:…-]+$/, '')}…`;
}
