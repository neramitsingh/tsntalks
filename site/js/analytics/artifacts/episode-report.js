/* The episode report.
 *
 * Goes to the episode's sponsor, after it airs. One page of A4: the still, the
 * guest, the date, what the long cut did, what every clip did, the sum across
 * all cuts, the channel's audience, and a source note.
 *
 * This is the artifact most likely to be forwarded to someone who was not in
 * the conversation. Every number on it therefore says what it is a number OF —
 * "views at 7 days" is a different claim from "views", and "all cuts" is not
 * people. A caveat that a sponsor would need belongs on the page, not in a
 * covering email that gets deleted.
 */

import { episodes, episodeClips, viewsAt, audience, windowFor } from '../data.js';
import {
  full, bkk, PLATFORM_NAME, dimensionLabel, clip, rangeLabel,
} from '../format.js';
import { filename, episodeSlug } from './index.js';
import {
  startArtifact, masthead, colophon, fig, printTable, proportionBar, el,
} from './page.js';

const DAY = 24 * 60 * 60 * 1000;

/* The still. Same chain the public pages use: a committed override would need
   the manifest, which this page does not load, so it goes straight to YouTube's
   own image and falls back to the one that always exists. */
const stills = (videoId) => [
  `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`,
  `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
];

startArtifact({
  title: 'Episode report',
  render: async (root, query) => {
    const id = Number(query.episode);
    if (!Number.isFinite(id)) throw new Error('No episode was named in the link.');

    const list = await episodes();
    if (!list.ok) throw new Error(list.reason);
    const episode = list.current.rows.find((r) => r.episodeId === id);
    if (!episode) throw new Error(`There is no episode ${id}.`);

    const lifetimeWindow = await windowFor({ frame: 'all', granularity: 'day', platform: 'all' });
    const [clips, atSeven, atThirty, ages, countries] = await Promise.all([
      episodeClips(id, lifetimeWindow),
      episode.publishedAt
        ? viewsAt(`yt:${episode.youtubeVideoId}`, new Date(+episode.publishedAt + 7 * DAY))
        : null,
      episode.publishedAt
        ? viewsAt(`yt:${episode.youtubeVideoId}`, new Date(+episode.publishedAt + 30 * DAY))
        : null,
      audience('yt_age', 90),
      audience('yt_country', 90),
    ]);

    root.replaceChildren();
    root.appendChild(masthead('Episode report', bkk(new Date().toISOString())));
    root.appendChild(hero(episode));
    root.appendChild(headline(episode, atSeven, atThirty));
    root.appendChild(clipsSection(episode, clips));
    root.appendChild(reachSection(episode));
    root.appendChild(await audienceSection(ages, countries));
    root.appendChild(await colophon(
      { platforms: 'all', lifetime: true },
      ['Views at 7 and 30 days are read from the snapshot archive, which begins '
       + '14 September 2026. For an episode published before then the figure is '
       + 'marked "not measured" rather than estimated.'],
    ));

    return { filename: filename('episode-report', episodeSlug(episode), 'pdf') };
  },
});

/* --- the top of the page --------------------------------------------------- */

function hero(episode) {
  const section = el('section', 'card');

  const img = new Image();
  const chain = stills(episode.youtubeVideoId);
  let step = 0;
  img.alt = `${episode.guest} on TSN Talks`;
  img.style.cssText = 'width:100%;height:64mm;object-fit:cover;border:0.5pt solid var(--ink-dim)';
  img.addEventListener('error', () => {
    step += 1;
    if (step < chain.length) img.src = chain[step];
    else img.remove();            // no still is better than a broken-image icon
  });
  img.src = chain[0];
  section.appendChild(img);

  section.appendChild(el('span', 'eyebrow',
    `Season ${episode.season} · Episode ${episode.number}`));
  section.appendChild(el('h1', null, episode.guest));
  if (episode.role) section.appendChild(el('p', 'lede', episode.role));
  section.appendChild(el('p', 'fine', episode.publishedAt
    ? `Published ${bkk(episode.publishedAt.toISOString())}, Bangkok`
    : 'Publication date not recorded'));
  return section;
}

function headline(episode, atSeven, atThirty) {
  const section = el('section');
  section.appendChild(el('h2', null, 'The long cut on YouTube'));

  const figs = el('div', 'figs');
  figs.appendChild(fig('Views, lifetime', full(episode.ytViews),
                       'Every view since it was published'));
  figs.appendChild(fig('At 7 days', measured(atSeven), windowNote(atSeven, 7)));
  figs.appendChild(fig('At 30 days', measured(atThirty), windowNote(atThirty, 30)));
  section.appendChild(figs);
  return section;
}

/**
 * "Not measured", never zero.
 *
 * The snapshot archive starts on 14 September 2026. For an episode published
 * before that there is no seven-day figure, and a 0 on a sponsor's report would
 * say the episode did nothing in its first week.
 */
const measured = (result) =>
  (result?.ok && result.current.views != null ? full(result.current.views) : 'not measured');

function windowNote(result, days) {
  if (!result?.ok || result.current.views == null) {
    return `No snapshot from the episode’s first ${days} days`;
  }
  if (result.current.stale) {
    return `Nearest snapshot: ${bkk(result.current.takenAt.toISOString())}`;
  }
  return `As of ${bkk(result.current.takenAt.toISOString())}`;
}

/* --- the clips ------------------------------------------------------------- */

function clipsSection(episode, clips) {
  const section = el('section');
  section.appendChild(el('h2', null, 'Every clip'));

  if (!clips?.ok) {
    section.appendChild(el('p', 'problem',
      `The clip list could not be read: ${clips?.reason ?? 'no answer'}`));
    return section;
  }
  const cuts = clips.current.rows.filter((r) => r.postId !== `yt:${episode.youtubeVideoId}`);
  if (!cuts.length) {
    section.appendChild(el('p', 'empty',
      'No clips have been matched to this episode. Clips are matched on the '
      + 'guest’s name or the episode number appearing in the caption.'));
    return section;
  }

  cuts.sort((a, b) => b.viewsEnd - a.viewsEnd);
  section.appendChild(printTable([
    { name: 'Platform', value: (r) => PLATFORM_NAME[r.platform] ?? r.platform },
    { name: 'Published', value: (r) => (r.publishedAt ? bkk(r.publishedAt.toISOString()) : null) },
    { name: 'Clip', value: (r) => clip(r.title, 64) || r.postId },
    { name: 'Views', key: 'viewsEnd', num: true, format: full },
    { name: 'Likes', key: 'likes', num: true, format: full },
    { name: 'Comments', key: 'comments', num: true, format: full },
    { name: 'Shares', key: 'shares', num: true, format: full },
    /* Instagram reports reach and the other two do not. A dash, with the reason
       in the note below, rather than a zero. */
    { name: 'Reach', key: 'reach', num: true, format: full },
  ], cuts));
  section.appendChild(el('p', 'fine',
    'Reach is reported by Instagram only; a dash means the platform does not '
    + 'publish it, not that it was zero.'));
  return section;
}

/* --- the total, and what it is not ---------------------------------------- */

function reachSection(episode) {
  const section = el('section', 'card');
  section.appendChild(el('h2', null, 'Across all cuts'));

  section.appendChild(el('p', 'hero-number', full(episode.totalReach)));

  const parts = [
    { id: 'youtube', name: 'YouTube, long cut', value: episode.ytViews },
    { id: 'youtube', name: 'YouTube clips', value: episode.clipViews.youtube },
    { id: 'instagram', name: 'Instagram clips', value: episode.clipViews.instagram },
    { id: 'tiktok', name: 'TikTok clips', value: episode.clipViews.tiktok },
  ].filter((p) => p.value > 0);

  if (parts.length) section.appendChild(proportionBar(parts, full));

  /* The sentence a sponsor will ask about, on the page rather than in an email.
     episode_rollup's comment says the same thing, and so does the Episodes tab. */
  section.appendChild(el('p', 'fine',
    'This is a SUM OF VIEW COUNTS across the episode’s long cut and every clip '
    + 'matched to it. It is not reach in the advertising sense and it is not a '
    + 'count of people: someone who watched the episode and then saw two clips '
    + 'is three in this figure.'));
  return section;
}

/* --- audience -------------------------------------------------------------- */

/**
 * Audience, where YouTube exposes it.
 *
 * This is the CHANNEL's audience over YouTube's rolling 90 days, not this
 * episode's — YouTube does not publish demographics per video at this tier. The
 * heading and the note both say so, because a sponsor reading an episode report
 * will otherwise take it as the episode's, and that is the single most likely
 * way this page could mislead someone.
 */
async function audienceSection(ages, countries) {
  const section = el('section');
  section.appendChild(el('h2', null, 'Who watches the channel'));

  const known = ages.ok && ages.current.window;
  section.appendChild(el('p', 'fine', known
    ? `YouTube reports age and country for the CHANNEL, not per episode. Window: `
      + `${rangeLabel(ages.current.window.start, ages.current.window.end)}.`
    : 'YouTube reports age and country for the channel, not per episode.'));

  const columns = (label) => [
    { name: label, value: (r) => r.label },
    { name: 'Share', num: true, value: (r) => `${Math.round(r.share * 1000) / 10}%` },
  ];

  const grid = el('div');
  grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:10pt';

  for (const [result, kind, label] of [[ages, 'yt_age', 'Age'],
                                       [countries, 'yt_country', 'Country']]) {
    const box = el('div');
    box.appendChild(el('h3', null, label));
    if (!result.ok) {
      box.appendChild(el('p', 'problem', result.reason));
    } else if (!result.current.rows.length) {
      box.appendChild(el('p', 'empty', `No ${label.toLowerCase()} data collected yet.`));
    } else {
      box.appendChild(printTable(columns(label), result.current.rows.slice(0, 8).map((r) => ({
        label: dimensionLabel(kind, r.dimension),
        share: r.share ?? 0,
      }))));
    }
    grid.appendChild(box);
  }
  section.appendChild(grid);
  return section;
}
