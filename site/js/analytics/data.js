/* EVERY call the dashboard makes, and every derived series.
   No DOM, no formatting, no colour. The tabs are renderers over what this
   returns and are not allowed to talk to Supabase themselves.

   Written against docs/analytics-data-contract.md. If a number here disagrees
   with that document, the document is the specification and this is the bug. */

import { sb, TABLES } from './supa.js';
import { PLATFORMS } from '../live-data.js';

/* ==========================================================================
   Time
   ==========================================================================

   Asia/Bangkok is +07:00 and has been since 1952. Thailand has never observed
   daylight saving and has no mechanism to start; the offset below is a constant
   for that reason, not because nobody thought about it. A test walks a whole
   year and asserts the offset never moves, so that this comment cannot rot into
   a lie and nobody "fixes" the missing DST handling.

   THIS IS THE ONLY PLACE IN THE DASHBOARD THAT CONVERTS BETWEEN UTC AND
   BANGKOK. A tab that does its own date maths is a bug. */

export const BKK_OFFSET_MS = 7 * 60 * 60 * 1000;

/** The collector runs hourly, so two hours without a finished run means one was
    missed. The public pages use three; a visitor does not care about one hour,
    and the person reading this page does. */
export const STALE_AFTER_MS = 2 * 60 * 60 * 1000;

/** Where `all` starts if we cannot ask the database. The spec's date for the
    first Zernio snapshot. */
export const MEASURING_SINCE_FALLBACK = '2026-09-14T00:00:00+07:00';

const toLocal = (d) => new Date(d.getTime() + BKK_OFFSET_MS);
const fromLocal = (l) => new Date(l.getTime() - BKK_OFFSET_MS);

/**
 * The start of the Bangkok period containing `date`.
 *
 * Weeks start on Monday, matching Postgres `date_trunc('week', …)`. If those two
 * ever disagree the chart's x-axis and the SQL's periods drift by a day and
 * every total still looks plausible, which is the worst kind of wrong.
 */
export function floorPeriod(date, granularity) {
  const l = toLocal(date instanceof Date ? date : new Date(date));
  switch (granularity) {
    case 'hour':
      l.setUTCMinutes(0, 0, 0);
      break;
    case 'week': {
      l.setUTCHours(0, 0, 0, 0);
      l.setUTCDate(l.getUTCDate() - ((l.getUTCDay() + 6) % 7));
      break;
    }
    case 'month':
      l.setUTCHours(0, 0, 0, 0);
      l.setUTCDate(1);
      break;
    case 'day':
    default:
      l.setUTCHours(0, 0, 0, 0);
      break;
  }
  return fromLocal(l);
}

/** Move `n` whole periods. Calendar-aware: +1 month from 31 Jan is 28 Feb. */
export function addPeriods(date, granularity, n) {
  const l = toLocal(date instanceof Date ? date : new Date(date));
  switch (granularity) {
    case 'hour': l.setUTCHours(l.getUTCHours() + n); break;
    case 'week': l.setUTCDate(l.getUTCDate() + n * 7); break;
    case 'month': {
      /* setUTCMonth alone overflows: +1 month from 31 January is 3 March,
         because February has no 31st. Clamp to the last day of the target
         month, which is what every calendar and every reader expects. */
      const day = l.getUTCDate();
      l.setUTCDate(1);
      l.setUTCMonth(l.getUTCMonth() + n);
      const lastDay = new Date(Date.UTC(l.getUTCFullYear(), l.getUTCMonth() + 1, 0))
        .getUTCDate();
      l.setUTCDate(Math.min(day, lastDay));
      break;
    }
    case 'day':
    default: l.setUTCDate(l.getUTCDate() + n); break;
  }
  return fromLocal(l);
}

/** Whole periods in [from, to). */
export function countPeriods(from, to, granularity) {
  let n = 0;
  let cursor = floorPeriod(from, granularity);
  const end = to.getTime();
  while (cursor.getTime() < end && n < 100000) {
    cursor = addPeriods(cursor, granularity, 1);
    n += 1;
  }
  return n;
}

/** Bangkok midnight of the day containing `date`. */
export const bangkokDayStart = (date) => floorPeriod(date, 'day');

/** A YYYY-MM-DD Bangkok date string as the instant that Bangkok day begins. */
export const bangkokDate = (iso) => new Date(`${iso}T00:00:00+07:00`);

/** A Date as a YYYY-MM-DD Bangkok date string. */
export const bangkokDateString = (date) =>
  toLocal(date instanceof Date ? date : new Date(date)).toISOString().slice(0, 10);

/**
 * The window a control state describes: `[from, to)`, both instants, with
 * `from` snapped to a period boundary.
 *
 * `to` is the present moment for every preset, not the end of today. The
 * snapshot functions read "the last snapshot at or before to_ts", so a `to` in
 * the future would read the same numbers and claim a window that has not
 * happened yet.
 */
export async function windowFor(state) {
  const granularity = state.granularity || 'day';
  const now = new Date();
  let from;
  let to = now;

  switch (state.frame) {
    case '7d': from = addPeriods(bangkokDayStart(now), 'day', -6); break;
    case '30d': from = addPeriods(bangkokDayStart(now), 'day', -29); break;
    case '90d': from = addPeriods(bangkokDayStart(now), 'day', -89); break;
    case '12m': from = addPeriods(floorPeriod(now, 'month'), 'month', -11); break;
    case 'all': from = await measuringSince(); break;
    case 'custom':
      from = bangkokDate(state.from);
      /* The `to` date the user picked is inclusive on screen and exclusive
         everywhere below, so it becomes the following midnight. */
      to = addPeriods(bangkokDate(state.to), 'day', 1);
      if (to > now) to = now;
      break;
    default: from = addPeriods(bangkokDayStart(now), 'day', -29); break;
  }

  from = floorPeriod(from, granularity);
  if (from > to) from = floorPeriod(to, granularity);

  return {
    from,
    to,
    granularity,
    platform: state.platform || 'all',
    compare: Boolean(state.compare),
  };
}

/**
 * The window of the same number of periods immediately before `w`.
 *
 * Measured in PERIODS, not in milliseconds. A twelve-month comparison shifted
 * by a fixed number of milliseconds lands in the middle of a month and every
 * boundary after it is wrong by a day or two. Counting periods keeps the two
 * windows aligned to the same calendar edges, and `previous.to` is exactly
 * `w.from` — no gap, no overlap.
 */
export function previousWindow(w) {
  const periods = Math.max(1, countPeriods(w.from, w.to, w.granularity));
  return {
    ...w,
    from: addPeriods(w.from, w.granularity, -periods),
    to: w.from,
    compare: false,
  };
}

/* ==========================================================================
   Plumbing
   ========================================================================== */

const cache = new Map();

/** Cleared on sign-out, and whenever a caller knows the data moved. */
export function clearCache() {
  cache.clear();
  measuringSincePromise = null;
}

const ok = (current, previous = null, meta = {}) => ({ ok: true, current, previous, meta });
const fail = (reason) => ({ ok: false, reason });

/** Turn whatever went wrong into a sentence a renderer can print. */
function reasonFor(error) {
  const msg = String(error?.message ?? error ?? '');
  if (/failed to fetch|networkerror|load failed/i.test(msg)) {
    return 'Could not reach the database.';
  }
  if (/jwt|expired|401/i.test(msg)) return 'That session has expired. Sign in again.';
  if (/permission|denied|403/i.test(msg)) return "This account doesn't have access to that.";
  if (/does not exist|42883|pgrst202/i.test(msg)) {
    return 'That query is missing from the database. db/004_analytics.sql may not be applied yet.';
  }
  return msg || 'Something went wrong reading the database.';
}

async function once(key, run) {
  if (cache.has(key)) return cache.get(key);
  const promise = (async () => {
    try {
      return await run();
    } catch (err) {
      /* Nothing in this module throws. A renderer that has to wrap every call
         in try/catch will eventually forget one, and one forgotten catch blanks
         the page. */
      return fail(reasonFor(err));
    }
  })();
  cache.set(key, promise);
  const result = await promise;
  if (!result.ok) cache.delete(key);       // never cache a failure
  return result;
}

async function rpc(name, args) {
  const { data, error } = await sb().rpc(name, args);
  if (error) throw new Error(error.message);
  return Array.isArray(data) ? data : [];
}

const rpcWindow = (w) => ({
  from_ts: w.from.toISOString(),
  to_ts: w.to.toISOString(),
  granularity: w.granularity,
  platform_filter: w.platform,
});

const num = (v) => (v == null ? 0 : Number(v) || 0);
const maybe = (v) => (v == null ? null : Number(v));
const when = (v) => (v ? new Date(v) : null);

const key = (name, w, extra = '') =>
  `${name}|${w.from.toISOString()}|${w.to.toISOString()}|${w.granularity}|${w.platform}|${extra}`;

/**
 * Run `build` for the window, and again for the previous one when comparing.
 * A failed comparison does not fail the current window — the panel draws, and
 * the delta says it could not be computed.
 */
async function windowed(w, name, build, extra = '') {
  const current = await once(key(name, w, extra), () => build(w));
  if (!current.ok) return current;
  if (!w.compare) return ok(current.current, null, { window: w });

  const prev = previousWindow(w);
  const previous = await once(key(name, prev, extra), () => build(prev));
  return ok(current.current, previous.ok ? previous.current : null,
            { window: w, previousWindow: prev, previousFailed: !previous.ok });
}

/* ==========================================================================
   How far back "all" goes
   ========================================================================== */

let measuringSincePromise = null;

/**
 * `all` means "since we started measuring", not "since the show started".
 *
 * Views are differences between snapshots, so no period before the first
 * snapshot can produce a number. Starting the axis earlier would draw a long
 * flat run of zeros that reads as "nothing happened" when it means "we were not
 * looking".
 */
export function measuringSince() {
  if (!measuringSincePromise) {
    measuringSincePromise = (async () => {
      try {
        const { data, error } = await sb()
          .from('post_snapshots').select('taken_at').order('taken_at').limit(1);
        if (error || !data?.length) return new Date(MEASURING_SINCE_FALLBACK);
        return new Date(data[0].taken_at);
      } catch {
        return new Date(MEASURING_SINCE_FALLBACK);
      }
    })();
  }
  return measuringSincePromise;
}

/* ==========================================================================
   The calls
   ========================================================================== */

/** Views over time, by platform. */
export async function views(w) {
  return windowed(w, 'views', async (win) => {
    const rows = await rpc('rollup_views', rpcWindow(win));
    const series = rows.map((r) => ({
      period: new Date(r.period),
      platform: r.platform,
      views: num(r.views),
      postsPublished: num(r.posts_published),
    }));
    return ok({
      series,
      byPlatform: sumBy(series, 'platform', 'views'),
      total: series.reduce((a, r) => a + r.views, 0),
      postsPublished: series.reduce((a, r) => a + r.postsPublished, 0),
    });
  });
}

/** Followers over time, with the gained and lost halves of each change. */
export async function followers(w) {
  return windowed(w, 'followers', async (win) => {
    const rows = await rpc('rollup_followers', rpcWindow(win));
    const series = rows.map((r) => ({
      period: new Date(r.period),
      platform: r.platform,
      /* NULL before the platform's first snapshot (db/006): the chart breaks
         the line there instead of drawing a floor at zero for the weeks
         before the collector existed. num() would have turned it into 0. */
      followers: r.followers == null ? null : num(r.followers),
      gained: num(r.gained),
      lost: num(r.lost),
    }));
    /* `followers` is a stock, so the window's figure is the LAST period's, not
       the sum of them. Summing a stock is how a dashboard reports nine million
       followers. */
    const latest = {};
    for (const r of series) {
      const seen = latest[r.platform];
      if (!seen || r.period > seen.period) latest[r.platform] = r;
    }
    const byPlatform = Object.fromEntries(
      Object.entries(latest).map(([p, r]) => [p, r.followers]));
    return ok({
      series,
      latest: byPlatform,
      total: Object.values(byPlatform).reduce((a, n) => a + (n ?? 0), 0),
      gained: series.reduce((a, r) => a + r.gained, 0),
      lost: series.reduce((a, r) => a + r.lost, 0),
    });
  });
}

/**
 * Interactions over time, and the rate they represent.
 *
 * The per-period rate comes from the SQL. The window's rate is computed here as
 * interactions over the window's views — one ratio of two sums, matching what
 * rollup_engagement does per period. Averaging the per-period rates would give
 * a quiet Tuesday the same weight as the day an episode landed, which is the
 * same mistake at a different scale.
 *
 * The extra rollup_views call is almost always free: the tab that draws this
 * has already asked for views over the same window, and the cache is keyed on
 * the window rather than on who asked.
 */
export async function engagement(w) {
  return windowed(w, 'engagement', async (win) => {
    const rows = await rpc('rollup_engagement', rpcWindow(win));
    const series = rows.map((r) => ({
      period: new Date(r.period),
      platform: r.platform,
      likes: num(r.likes),
      comments: num(r.comments),
      shares: num(r.shares),
      rate: maybe(r.engagement_rate),
    }));
    const likes = series.reduce((a, r) => a + r.likes, 0);
    const comments = series.reduce((a, r) => a + r.comments, 0);
    const shares = series.reduce((a, r) => a + r.shares, 0);
    const interactions = likes + comments + shares;

    const v = await views({ ...win, compare: false });
    const totalViews = v.ok ? v.current.total : 0;

    return ok({
      series, likes, comments, shares, interactions,
      /* null, never 0: no views means there was nothing to divide by, and a
         rate of zero is a claim about engagement rather than about data. */
      rate: totalViews ? interactions / totalViews : null,
    });
  });
}

/** One row per post. The Posts tab's source, and the posts-table artifact's. */
export async function posts(w) {
  return windowed(w, 'posts', async (win) => {
    const rows = await rpc('post_deltas', {
      from_ts: win.from.toISOString(),
      to_ts: win.to.toISOString(),
      platform_filter: win.platform,
    });
    return ok({ rows: rows.map(postRow) });
  });
}

function postRow(r) {
  return {
    postId: r.post_id,
    platform: r.platform,
    title: r.title ?? '',
    url: r.url ?? '',
    publishedAt: when(r.published_at),
    viewsStart: num(r.views_start),
    viewsEnd: num(r.views_end),
    viewsGained: num(r.views_gained),
    likes: num(r.likes),
    comments: num(r.comments),
    shares: num(r.shares),
    /* Instagram reports reach; YouTube and TikTok do not. null is "not
       reported" and must never be rendered as 0. Added to post_deltas in the
       Posts-tab commit; until then it arrives undefined and stays null. */
    reach: r.reach == null ? null : Number(r.reach),
    rate: maybe(r.engagement_rate),
    episodeId: r.episode_id ?? null,
  };
}

/**
 * One post's own view curve, for the inline expansion on a Posts row.
 *
 * Read straight from `post_snapshots` rather than through a rollup: this is one
 * post over one window, which is a handful of rows, and a function for it would
 * be a function Nav has to apply for no gain.
 */
export async function postHistory(postId, w) {
  return once(key('postHistory', w, postId), async () => {
    const { data, error } = await sb()
      .from('post_snapshots')
      .select('taken_at,views')
      .eq('post_id', postId)
      .gte('taken_at', w.from.toISOString())
      .lte('taken_at', w.to.toISOString())
      .order('taken_at');
    if (error) throw new Error(error.message);
    return ok({
      series: (data ?? []).map((r) => ({ period: new Date(r.taken_at), views: num(r.views) })),
    });
  });
}

/**
 * What a post's counter read at one instant: the last snapshot at or before it.
 *
 * The episode report asks for "views at 7 days and at 30 days", which is this,
 * twice. Returns `null` rather than 0 when there is no snapshot that old —
 * the collector only started on 14 September 2026, so for every episode
 * published before then the answer is genuinely unknown, and a zero would read
 * as "nobody watched it in its first week".
 */
export async function viewsAt(postId, instant) {
  const at = instant instanceof Date ? instant : new Date(instant);
  return once(`viewsAt|${postId}|${at.toISOString()}`, async () => {
    const { data, error } = await sb()
      .from('post_snapshots')
      .select('taken_at,views')
      .eq('post_id', postId)
      .lte('taken_at', at.toISOString())
      .order('taken_at', { ascending: false })
      .limit(1);
    if (error) throw new Error(error.message);
    const row = data?.[0];
    return ok({
      views: row ? num(row.views) : null,
      takenAt: row ? new Date(row.taken_at) : null,
      /* True when the snapshot we found is much older than the instant asked
         for — the figure is real but it is not "as of" that date. */
      stale: row ? at - new Date(row.taken_at) > 36 * 60 * 60 * 1000 : true,
    });
  });
}

/**
 * One row per episode. Lifetime figures — the time frame does not apply, and
 * the Episodes tab says so on screen rather than leaving it to be assumed.
 */
export async function episodes() {
  return once('episodes', async () => {
    const rows = await rpc('episode_rollup', {});
    return ok({
      rows: rows.map((r) => ({
        episodeId: r.episode_id,
        season: r.season,
        number: r.number,
        title: r.title ?? '',
        guest: r.guest ?? '',
        role: r.role ?? '',
        publishedAt: when(r.published_at),
        youtubeVideoId: r.youtube_video_id,
        ytViews: num(r.yt_views),
        clipCount: num(r.clip_count),
        clipViews: {
          youtube: num(r.clip_views_youtube),
          instagram: num(r.clip_views_instagram),
          tiktok: num(r.clip_views_tiktok),
        },
        /* A sum of view counts across the episode's cuts. Not people: someone
           who watches the long cut and two clips is three. The artifacts
           inherit this figure and carry that sentence on the page. */
        totalReach: num(r.total_reach),
      })),
    });
  });
}

/**
 * The clips matched to one episode, from the same source as the Posts tab.
 *
 * Always across all three platforms, whatever the platform control says: an
 * episode's clips span platforms by definition, and a sponsor reading the
 * episode report wants the whole episode, not the YouTube slice of it.
 */
export async function episodeClips(episodeId, w) {
  const all = await posts({ ...w, platform: 'all', compare: false });
  if (!all.ok) return all;
  return ok({ rows: all.current.rows.filter((r) => r.episodeId === episodeId) });
}

/**
 * One demographic kind, this window against a comparable earlier one.
 *
 * `share` is computed here, after the rows arrive, over the sum of the returned
 * rows — so it is right for the kinds that are already percentages (yt_age,
 * yt_gender) and for the kinds that are raw counts, and no renderer has to know
 * which is which.
 *
 * `shareDelta` is in PERCENTAGE POINTS. A relative change in a percentage
 * ("India is down 40%") is read as a share by almost everyone who sees it.
 *
 * `window.end` and `prevWindow.end` are EXCLUSIVE — the instant after the last
 * day the window covers — because every other window in this dashboard is
 * [from, to) and one that was not would eventually be labelled a day short.
 * The database stores `window_end` as the inclusive last date.
 */
export async function audience(kind, windowDays = 90) {
  return once(`audience|${kind}|${windowDays}`, async () => {
    const rows = await rpc('demographics_compare', { kind, window_days: windowDays });
    const total = rows.reduce((a, r) => a + num(r.value), 0);
    const prevTotal = rows.reduce((a, r) => a + num(r.prev_value), 0);
    const first = rows[0] ?? {};
    return ok({
      rows: rows.map((r) => {
        const share = total ? num(r.value) / total : null;
        const prevShare = r.prev_value == null || !prevTotal
          ? null : Number(r.prev_value) / prevTotal;
        return {
          dimension: r.dimension,
          value: maybe(r.value) ?? 0,
          prevValue: maybe(r.prev_value),
          delta: maybe(r.delta),
          share,
          prevShare,
          shareDelta: share != null && prevShare != null ? (share - prevShare) * 100 : null,
        };
      }),
      window: first.window_start
        ? { start: bangkokDate(first.window_start),
            end: addPeriods(bangkokDate(first.window_end), 'day', 1) }
        : null,
      prevWindow: first.prev_window_start
        ? { start: bangkokDate(first.prev_window_start),
            end: addPeriods(bangkokDate(first.prev_window_end), 'day', 1) }
        : null,
      total,
    });
  });
}

/**
 * Daily platform metrics over the window.
 *
 * `day` is a bare date and is treated as a Bangkok calendar date WITHOUT
 * conversion — see §7.1 of the data contract. Pushing a bare date through a
 * timezone is how you lose a day.
 *
 * `missing` names the metrics that came back with no rows at all, so the Growth
 * tab can say "TikTok does not report watch time" rather than draw a zero line
 * over data that does not exist.
 *
 * `byPeriod` buckets the daily rows into the window's granularity, HERE, so no
 * tab has to. Most metrics sum. `yt_avg_duration` is an average and is combined
 * as a mean weighted by that day's `yt_views` when those were requested too — a
 * plain mean of daily averages gives a Tuesday with forty views the same weight
 * as the day an episode landed, which is the same mistake as a mean of rates.
 */
export const MEAN_METRICS = new Set(['yt_avg_duration']);

export async function dailyMetrics(w, metrics) {
  const wanted = [...metrics];
  return windowed(w, 'dailyMetrics', async (win) => {
    const [{ data, error }, accs] = await Promise.all([
      sb().from('metric_daily')
        .select('account_id,day,metric,value')
        .gte('day', bangkokDateString(win.from))
        .lte('day', bangkokDateString(win.to))
        .in('metric', wanted)
        .order('day'),
      accounts(),
    ]);
    if (error) throw new Error(error.message);

    const platformOf = {};
    if (accs.ok) for (const a of accs.current.rows) platformOf[a.id] = a.platform;

    const series = (data ?? []).map((r) => ({
      day: bangkokDate(r.day),
      metric: r.metric,
      value: Number(r.value),
      accountId: r.account_id,
      platform: platformOf[r.account_id] ?? null,
    })).filter((r) => win.platform === 'all' || r.platform === win.platform);

    const byMetric = {};
    for (const m of wanted) byMetric[m] = [];
    for (const r of series) (byMetric[r.metric] ??= []).push(r);

    const weights = new Map();
    for (const r of byMetric.yt_views ?? []) {
      weights.set(`${r.accountId}|${r.day.getTime()}`, r.value);
    }

    const byPeriod = {};
    for (const m of wanted) {
      const buckets = new Map();
      for (const r of byMetric[m]) {
        const t = floorPeriod(r.day, win.granularity).getTime();
        if (!buckets.has(t)) {
          buckets.set(t, { period: new Date(t), value: 0, weight: 0, days: 0 });
        }
        const b = buckets.get(t);
        b.days += 1;
        if (MEAN_METRICS.has(m)) {
          const weight = weights.get(`${r.accountId}|${r.day.getTime()}`) ?? 1;
          b.value += r.value * weight;
          b.weight += weight;
        } else {
          b.value += r.value;
        }
      }
      byPeriod[m] = [...buckets.values()]
        .map((b) => ({
          period: b.period,
          value: MEAN_METRICS.has(m) ? (b.weight ? b.value / b.weight : null) : b.value,
          days: b.days,
        }))
        .sort((a, b) => a.period - b.period);
    }

    return ok({
      series,
      byMetric,
      byPeriod,
      missing: wanted.filter((m) => byMetric[m].length === 0),
    });
  }, wanted.join(','));
}

/** The connected accounts. Cached for the session; they change once a year. */
export async function accounts() {
  return once('accounts', async () => {
    const { data, error } = await sb()
      .from('accounts').select('id,platform,handle,display_name,active').order('platform');
    if (error) throw new Error(error.message);
    return ok({
      rows: (data ?? []).map((r) => ({
        id: r.id, platform: r.platform, handle: r.handle,
        displayName: r.display_name, active: r.active !== false,
      })),
    });
  });
}

/** Recent collector runs, newest first. */
export async function runs(limit = 20) {
  return once(`runs|${limit}`, async () => {
    const { data, error } = await sb()
      .from('collector_runs')
      .select('id,started_at,finished_at,status,rows_written,notes')
      .order('started_at', { ascending: false })
      .limit(limit);
    if (error) throw new Error(error.message);
    return ok({ rows: (data ?? []).map(runRow) });
  });
}

function runRow(r) {
  const finished = when(r.finished_at);
  return {
    id: r.id,
    startedAt: when(r.started_at),
    finishedAt: finished,
    status: r.status,
    rowsWritten: num(r.rows_written),
    notes: r.notes ?? {},
    ageMs: finished ? Date.now() - finished.getTime() : null,
  };
}

/**
 * The header's freshness. A run that failed is failed whatever its age — an
 * eight-minute-old failure is not fresher than a two-hour-old success.
 */
export async function lastRun() {
  const result = await runs(1);
  if (!result.ok) return result;
  const run = result.current.rows[0] ?? null;
  if (!run) return ok({ run: null, ageMs: null, stale: true, failed: false });
  return ok({
    run,
    ageMs: run.ageMs,
    stale: run.ageMs == null || run.ageMs > STALE_AFTER_MS,
    failed: run.status !== 'ok',
  });
}

/** The latest health check per account. The table is append-only. */
export async function accountHealth() {
  return once('accountHealth', async () => {
    const [{ data, error }, accs] = await Promise.all([
      sb().from('account_health')
        .select('account_id,checked_at,status,can_fetch_analytics,needs_reconnect,token_expires_at')
        .order('checked_at', { ascending: false })
        .limit(60),
      accounts(),
    ]);
    if (error) throw new Error(error.message);

    const platformOf = {};
    if (accs.ok) for (const a of accs.current.rows) platformOf[a.id] = a.platform;

    const latest = new Map();
    for (const r of data ?? []) {
      if (!latest.has(r.account_id)) latest.set(r.account_id, r);
    }
    return ok({
      rows: [...latest.values()].map((r) => ({
        accountId: r.account_id,
        platform: platformOf[r.account_id] ?? null,
        checkedAt: when(r.checked_at),
        status: r.status,
        canFetchAnalytics: r.can_fetch_analytics,
        needsReconnect: Boolean(r.needs_reconnect),
        tokenExpiresAt: when(r.token_expires_at),
        ageMs: r.checked_at ? Date.now() - new Date(r.checked_at).getTime() : null,
      })).sort((a, b) => String(a.platform).localeCompare(String(b.platform))),
    });
  });
}

/**
 * When each platform last produced data.
 *
 * Not the same question as "did the collector run". The run can finish `ok`
 * while one platform's token has expired and that account has not been
 * snapshotted for a day — which is precisely the failure the Health tab exists
 * to surface, and the one a green dot on the header would hide.
 *
 * Read from `account_snapshots`, because that is the table a platform writes to
 * on every successful run.
 */
export async function platformFreshness() {
  return once('platformFreshness', async () => {
    const [{ data, error }, accs] = await Promise.all([
      sb().from('account_snapshots')
        .select('account_id,taken_at')
        .order('taken_at', { ascending: false })
        .limit(200),
      accounts(),
    ]);
    if (error) throw new Error(error.message);

    const platformOf = {};
    for (const a of accs.ok ? accs.current.rows : []) platformOf[a.id] = a.platform;

    const latest = new Map();
    for (const r of data ?? []) {
      if (!latest.has(r.account_id)) latest.set(r.account_id, r);
    }
    /* An account with no snapshot at all still gets a row, with a null age.
       Leaving it out would make a platform that has never reported look fine. */
    const rows = (accs.ok ? accs.current.rows : []).map((a) => {
      const seen = latest.get(a.id);
      return {
        accountId: a.id,
        platform: a.platform,
        handle: a.handle,
        lastSeen: seen ? new Date(seen.taken_at) : null,
        ageMs: seen ? Date.now() - new Date(seen.taken_at).getTime() : null,
      };
    });
    return ok({ rows: rows.sort((a, b) => a.platform.localeCompare(b.platform)) });
  });
}

/**
 * Row counts per table, from PostgREST's Content-Range rather than a select.
 * A table that errors reports null, not zero — "we could not count" and "there
 * is nothing there" are different answers and the Health tab shows both.
 */
export async function rowCounts() {
  return once('rowCounts', async () => {
    const entries = await Promise.all(TABLES.map(async (table) => {
      try {
        const { count, error } = await sb()
          .from(table).select('*', { count: 'exact', head: true });
        return [table, error ? null : count];
      } catch {
        return [table, null];
      }
    }));
    return ok({ counts: Object.fromEntries(entries) });
  });
}

/**
 * The Overview's four headline figures, current and previous.
 *
 * Derived rather than fetched: every number here already exists in one of the
 * three calls above, and fetching it a second way is how two panels on the same
 * screen end up disagreeing.
 */
export async function headline(w) {
  const [v, f, e] = await Promise.all([views(w), followers(w), engagement(w)]);
  if (!v.ok) return v;

  const shape = (viewsPart, followersPart, engagementPart) => {
    if (!viewsPart) return null;
    const interactions = engagementPart
      ? engagementPart.likes + engagementPart.comments + engagementPart.shares : null;
    return {
      views: viewsPart.total,
      postsPublished: viewsPart.postsPublished,
      followers: followersPart ? followersPart.total : null,
      followersGained: followersPart ? followersPart.gained : null,
      interactions,
      /* One ratio of two sums over the whole window, matching what the SQL does
         per period. Averaging the per-period rates would weight a quiet Tuesday
         the same as the day an episode landed. */
      rate: interactions != null && viewsPart.total ? interactions / viewsPart.total : null,
    };
  };

  return ok(
    shape(v.current, f.ok ? f.current : null, e.ok ? e.current : null),
    w.compare ? shape(v.previous, f.ok ? f.previous : null, e.ok ? e.previous : null) : null,
    { window: w, followersFailed: !f.ok, engagementFailed: !e.ok },
  );
}

/** Signed in is not the same as allowed. See the data contract, §2. */
export async function access() {
  try {
    const { data, error } = await sb().from('allowed_users').select('email').limit(1);
    if (error) return fail(reasonFor(error));
    return ok({ allowed: (data?.length ?? 0) > 0 });
  } catch (err) {
    return fail(reasonFor(err));
  }
}

/* ==========================================================================
   Helpers
   ========================================================================== */

function sumBy(rows, groupKey, valueKey) {
  const out = Object.fromEntries(PLATFORMS.map((p) => [p, 0]));
  for (const r of rows) out[r[groupKey]] = (out[r[groupKey]] ?? 0) + r[valueKey];
  return out;
}

/** Rows folded into one entry per period, with a column per platform. */
export function byPeriod(series, valueKey) {
  const map = new Map();
  for (const r of series) {
    const t = r.period.getTime();
    if (!map.has(t)) {
      map.set(t, { period: r.period, total: 0,
                   ...Object.fromEntries(PLATFORMS.map((p) => [p, 0])) });
    }
    const row = map.get(t);
    row[r.platform] = r[valueKey];
    row.total += r[valueKey];
  }
  return [...map.values()].sort((a, b) => a.period - b.period);
}
