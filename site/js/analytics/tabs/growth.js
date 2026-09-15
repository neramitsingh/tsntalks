/* Growth — "which channel is growing?"
 *
 * The rule this tab exists to keep: WHERE A PLATFORM DOES NOT REPORT A METRIC,
 * SAY SO. Never a zero line for missing data. A flat line at zero across a
 * quarter is a claim that nobody watched; "TikTok does not report watch time"
 * is the truth, and it is shorter.
 */

import { followers, dailyMetrics } from '../data.js';
import {
  chart, windowSub, resultPanel, seriesFor, pointsFor, periodLabel, notReported,
  full, compact, el, PLATFORM_NAME,
} from './shared.js';
import { duration, METRIC_NAME } from '../format.js';

/* Every metric_daily key the tab asks for. yt_views is requested because
   dailyMetrics weights the average-duration mean by it, not because the tab
   draws it — views over time is the Overview's chart and drawing it twice is
   how two panels start disagreeing. */
const METRICS = [
  'yt_views', 'yt_minutes', 'yt_avg_duration', 'yt_subs_gained', 'yt_subs_lost',
  'ig_follows', 'ig_unfollows', 'tt_followers_gained', 'tt_followers_lost',
];

/* Which platform each metric comes from, so a missing one can be named
   accurately: "TikTok does not report X" rather than "no data". */
const METRIC_PLATFORM = {
  yt_views: 'youtube', yt_minutes: 'youtube', yt_avg_duration: 'youtube',
  yt_subs_gained: 'youtube', yt_subs_lost: 'youtube',
  ig_follows: 'instagram', ig_unfollows: 'instagram',
  tt_followers_gained: 'tiktok', tt_followers_lost: 'tiktok',
};

/* Stated rather than inferred from an empty result, because "we asked and got
   nothing" and "this platform has never had this number" are different, and
   only the second one is permanent. */
const NEVER_REPORTED = [
  'Instagram and TikTok do not report watch time or average view duration '
  + 'through Zernio, so those two panels are YouTube only.',
];

export async function growth(mount, { state, window: w }) {
  const [followerResult, metricResult] = await Promise.all([
    followers(w), dailyMetrics(w, METRICS),
  ]);
  const series = seriesFor(w.platform);

  mount.replaceChildren(
    followersPanel(followerResult, w, series),
    gainedLostPanel(followerResult, w),
    subscribersPanel(metricResult, w),
    watchTimePanel(metricResult, w),
    durationPanel(metricResult, w),
  );
}

/* --- followers ------------------------------------------------------------ */

function followersPanel(result, w, series) {
  return resultPanel(result, {
    title: 'Followers by platform',
    sub: windowSub('Last snapshot in each period', w.from, w.to, `by ${w.granularity}`),
    emptyMessage: 'No follower snapshots in this window.',
  }, (section, { current }) => {
    if (!current.series.length) return false;
    section.appendChild(chart({
      kind: 'line',
      name: 'Followers by platform',
      points: pointsFor(current.series, 'followers', w.granularity, series),
      series,
      format: compact,
      summary: 'Show followers by period',
    }));
    return true;
  });
}

/**
 * Gained and lost as diverging bars: gains above the line, losses below it.
 *
 * Not a net line. A net of +3 that hides 40 gained and 37 lost is a different
 * story from a net of +3 that is three people arriving, and the second one is
 * the one a net line implies.
 */
function gainedLostPanel(result, w) {
  const scope = w.platform === 'all' ? 'All platforms combined' : PLATFORM_NAME[w.platform];
  return resultPanel(result, {
    title: 'Followers gained and lost',
    sub: windowSub(scope, w.from, w.to, `by ${w.granularity}`),
    emptyMessage: 'No follower snapshots in this window.',
  }, (section, { current }) => {
    if (!current.series.length) return false;

    const buckets = new Map();
    for (const r of current.series) {
      const t = r.period.getTime();
      if (!buckets.has(t)) buckets.set(t, { period: r.period, gained: 0, lost: 0 });
      const b = buckets.get(t);
      b.gained += r.gained;
      b.lost += r.lost;
    }
    const rows = [...buckets.values()].sort((a, b) => a.period - b.period);

    section.appendChild(chart({
      kind: 'bar',
      name: `Followers gained and lost, ${scope.toLowerCase()}`,
      points: rows.map((r) => ({
        label: periodLabel(r.period, w.granularity),
        /* Lost is drawn negative so the two diverge from the zero line. The
           table twin below carries it as the positive count it is. */
        values: { gained: r.gained, lost: -r.lost },
      })),
      series: [{ id: 'gained', name: 'Gained' }, { id: 'lost', name: 'Lost' }],
      format: compact,
      rows: rows.map((r) => ({
        label: periodLabel(r.period, w.granularity),
        gained: r.gained,
        lost: r.lost,
        net: r.gained - r.lost,
      })),
      columns: [
        { key: 'label', name: 'Period' },
        { key: 'gained', name: 'Gained', num: true, format: full },
        { key: 'lost', name: 'Lost', num: true, format: full },
        { key: 'net', name: 'Net', num: true, format: full },
      ],
      summary: 'Show gained and lost by period',
    }));
    section.appendChild(el('p', 'a-note',
      'Losses are drawn below the line and listed as positive counts in the table. '
      + 'The first period attributes no change: there is no earlier snapshot to '
      + 'difference against, which is not the same as nobody arriving.'));
    return true;
  });
}

/* --- the metric_daily panels ---------------------------------------------- */

/**
 * A panel over metric_daily that refuses to draw a zero where a platform has
 * simply never reported the number.
 */
function metricPanel(result, w, {
  title, name, metrics, kind = 'bar', format = compact, seriesNames, twin,
}) {
  return resultPanel(result, {
    title,
    sub: windowSub(metrics.map((m) => PLATFORM_NAME[METRIC_PLATFORM[m]]).filter(
      (v, i, a) => a.indexOf(v) === i).join(' and '), w.from, w.to, `by ${w.granularity}`),
  }, (section, { current }) => {
    const absent = metrics.filter((m) => current.missing.includes(m));
    if (absent.length === metrics.length) {
      section.appendChild(notReported(
        `${[...new Set(absent.map((m) => PLATFORM_NAME[METRIC_PLATFORM[m]]))].join(' and ')} `
        + `reported no ${title.toLowerCase()} in this window. `
        + 'That is an absence of data, not a zero — nothing is drawn for it.'));
      return true;
    }

    const periods = new Map();
    for (const m of metrics) {
      for (const r of current.byPeriod[m] ?? []) {
        const t = r.period.getTime();
        if (!periods.has(t)) periods.set(t, { period: r.period, values: {}, days: 0 });
        const bucket = periods.get(t);
        bucket.values[m] = r.value;
        bucket.days = Math.max(bucket.days, r.days ?? 0);
      }
    }
    const rows = [...periods.values()].sort((a, b) => a.period - b.period);
    if (!rows.length) return false;

    const series = metrics.map((m) => ({ id: m, name: seriesNames?.[m] ?? METRIC_NAME[m] }));
    section.appendChild(chart({
      kind,
      name,
      points: rows.map((r) => ({
        label: periodLabel(r.period, w.granularity),
        values: Object.fromEntries(metrics.map((m) => [m, r.values[m] ?? null])),
      })),
      series,
      format,
      rows: twin?.rows(rows),
      columns: twin?.columns,
      summary: 'Show the numbers by period',
    }));

    if (absent.length) {
      section.appendChild(notReported(
        `${absent.map((m) => METRIC_NAME[m]).join(' and ')}: nothing reported in this window.`));
    }
    return true;
  });
}

function subscribersPanel(result, w) {
  return metricPanel(result, w, {
    title: 'YouTube subscribers',
    name: 'YouTube subscribers gained and lost',
    metrics: ['yt_subs_gained', 'yt_subs_lost'],
    seriesNames: { yt_subs_gained: 'Gained', yt_subs_lost: 'Lost' },
    format: full,
  });
}

function watchTimePanel(result, w) {
  const panelEl = metricPanel(result, w, {
    title: 'Watch time',
    name: 'YouTube watch time in minutes',
    metrics: ['yt_minutes'],
    format: compact,
  });
  panelEl.appendChild(el('p', 'a-note', NEVER_REPORTED[0]));
  return panelEl;
}

/**
 * Average view duration, on its own chart.
 *
 * It shares a tab with watch time and it does NOT share an axis with it. One is
 * minutes summed, one is seconds averaged; a second axis would let a reader
 * compare two quantities that have nothing to do with each other, which is the
 * one rule the spec states twice.
 */
function durationPanel(result, w) {
  const panelEl = metricPanel(result, w, {
    title: 'Average view duration',
    name: 'YouTube average view duration',
    metrics: ['yt_avg_duration'],
    kind: 'line',
    format: (v) => duration(v),
    twin: {
      columns: [
        { key: 'label', name: 'Period' },
        { key: 'seconds', name: 'Average duration', num: true, format: (v) => duration(v) },
        { key: 'days', name: 'Days measured', num: true, format: full },
      ],
      rows: (rows) => rows.map((r) => ({
        label: periodLabel(r.period, w.granularity),
        seconds: r.values.yt_avg_duration == null ? null : Math.round(r.values.yt_avg_duration),
        days: r.days ?? null,
      })),
    },
  });
  panelEl.appendChild(el('p', 'a-note',
    'Periods longer than a day average their days weighted by that day’s views, '
    + 'so a quiet Tuesday does not count the same as the day an episode landed. '
    + 'Separate chart from watch time on purpose: different units never share an axis.'));
  return panelEl;
}
