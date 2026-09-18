/* Overview — "how are we doing?", answered in five seconds.
 *
 * The four headline figures come first and carry the whole answer. Everything
 * below them is the evidence for it, and NOTHING below the fold is load-bearing:
 * if the charts never loaded, the top row would still say how the show is doing.
 */

import { headline, views, followers, posts } from '../data.js';
import {
  chart, panel, windowSub, resultPanel, figure, deltaEl, table, postLink,
  platformCell, seriesFor, pointsFor, full, compact, fmtRate, el, empty,
} from './shared.js';
import { artifactBar, forScope } from '../artifacts/index.js';

const SINCE = {
  '7d': 'previous 7 days', '30d': 'previous 30 days', '90d': 'previous 90 days',
  '12m': 'previous 12 months', all: 'the period before', custom: 'the period before',
};

export async function overview(mount, { state, window: w }) {
  const [head, viewSeries, followerSeries, postRows] = await Promise.all([
    headline(w), views(w), followers(w), posts(w),
  ]);

  const since = SINCE[state.frame] ?? 'the previous period';
  const series = seriesFor(w.platform);

  mount.replaceChildren(
    headlinePanel(head, w, since, state),
    viewsPanel(viewSeries, w, series),
    followersPanel(followerSeries, w, series),
    topPostsPanel(postRows, w),
    exportsPanel(w),
  );
}

/**
 * The two artifacts that are not scoped to one episode or to the Posts table.
 *
 * They live here because the Overview is the tab someone is on when they decide
 * to send something, and because an export nobody can find is an export that
 * does not exist.
 */
function exportsPanel(w) {
  const section = panel({
    title: 'Send something',
    sub: windowSub('Produced from the window above', w.from, w.to,
                   'each one goes to a named person'),
  });
  section.appendChild(artifactBar(
    [...forScope('month'), ...forScope('date')],
    () => ({ window: w }),
  ));
  section.appendChild(el('p', 'a-note',
    'There is no generic "export this view". Every artifact is a page designed '
    + 'for whoever receives it, and it carries the platforms, the window and the '
    + 'collector run it was built from.'));
  return section;
}

/* --- the four figures ----------------------------------------------------- */

function headlinePanel(result, w, since, state) {
  return resultPanel(result, {
    title: 'How are we doing',
    sub: windowSub(state.platform === 'all' ? 'All platforms' : null, w.from, w.to,
                   w.compare ? `compared with the ${since}` : 'no comparison'),
  }, (section, { current, previous }) => {
    const row = el('div', 'a-figrow');
    const prev = (key) => (previous ? previous[key] : null);

    row.append(
      figure('Views', current.views, {
        format: compact,
        delta: deltaEl(current.views, prev('views'), { since }),
      }),
      figure('Followers', current.followers, {
        format: compact,
        delta: deltaEl(current.followers, prev('followers'), { since }),
        /* Followers is a stock read at the end of the window. The change in it
           is not the same as gained-minus-lost over the window, and the note
           says which one this is. */
        note: current.followersGained != null
          ? `${full(current.followersGained)} gained in this window` : null,
      }),
      figure('Posts published', current.postsPublished, {
        delta: deltaEl(current.postsPublished, prev('postsPublished'), { since }),
      }),
      figure('Engagement rate', current.rate, {
        format: (v) => fmtRate(v),
        delta: deltaEl(current.rate, prev('rate'), { since, format: fmtRate }),
        note: current.interactions != null
          ? `${full(current.interactions)} likes, comments and shares` : null,
      }),
    );
    section.appendChild(row);
    return true;
  });
}

/* --- views over time ------------------------------------------------------ */

function viewsPanel(result, w, series) {
  return resultPanel(result, {
    title: 'Views over time',
    sub: windowSub('By platform', w.from, w.to, `by ${w.granularity}`),
  }, (section, { current }) => {
    if (!current.series.length) return false;
    /* One small chart per platform, each on its own scale. Stacked, TikTok at
       1.5M over YouTube at 244K is one platform and two slivers; the panel takes
       the full row so the three charts have room to be read. */
    section.appendChild(chart({
      kind: 'multiples',
      name: 'Views over time by platform',
      points: pointsFor(current.series, 'views', w.granularity, series),
      series,
      format: compact,
      summary: 'Show views by period',
    }));
    return true;
  });
}

/* --- follower growth ------------------------------------------------------ */

function followersPanel(result, w, series) {
  return resultPanel(result, {
    title: 'Follower growth',
    sub: windowSub('By platform', w.from, w.to, `by ${w.granularity}`),
    width: 'half',
  }, (section, { current }) => {
    if (!current.series.length) return false;
    /* Lines, not bars: followers are a stock, and a bar chart of a stock invites
       the reader to add the bars up. */
    section.appendChild(chart({
      kind: 'line',
      name: 'Followers by platform',
      points: pointsFor(current.series, 'followers', w.granularity, series),
      series,
      format: compact,
      summary: 'Show followers by period',
    }));
    section.appendChild(el('p', 'a-note',
      `${full(current.gained)} gained and ${full(current.lost)} lost across the window. `
      + 'A period with no snapshot repeats the previous value rather than dropping '
      + 'to zero, and before the first snapshot the line is simply absent; the first '
      + 'period attributes no change, because there is nothing earlier to compare it with.'));
    return true;
  });
}

/* --- top posts ------------------------------------------------------------ */

const TOP_N = 10;

function topPostsPanel(result, w) {
  return resultPanel(result, {
    title: 'Top posts in this window',
    sub: windowSub(`The ${TOP_N} that gained the most views`, w.from, w.to),
    emptyMessage: 'No posts gained views in this window.',
  }, (section, { current }) => {
    const rows = [...current.rows]
      .sort((a, b) => b.viewsGained - a.viewsGained)
      .slice(0, TOP_N);
    if (!rows.length) return false;

    section.appendChild(table([
      { name: 'Platform', value: (r) => platformCell(r.platform) },
      { name: 'Post', value: (r) => postLink(r), wide: true },
      { name: 'Gained here', key: 'viewsGained', num: true, format: full },
      { name: 'Views total', key: 'viewsEnd', num: true, format: full },
      { name: 'Likes', key: 'likes', num: true, format: full },
      { name: 'Comments', key: 'comments', num: true, format: full },
      { name: 'Shares', key: 'shares', num: true, format: full },
      { name: 'Rate', key: 'rate', num: true, format: (v) => fmtRate(v) },
    ], rows));
    section.appendChild(el('p', 'a-note',
      '"Gained here" is the change inside this window; "views total" is lifetime. '
      + 'A post we started watching inside the window counts only the views it gained after we first saw it; '
      + 'a post published inside the window counts all of them.'));
    return true;
  });
}
