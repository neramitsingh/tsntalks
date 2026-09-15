/* The guest card.
 *
 * To the guest, a week after their episode. One page, and one square PNG they
 * can post. What it says is: this is how far your episode travelled, this is
 * the clip that went furthest, and here is the link.
 *
 * ONE DEPARTURE FROM THE SPEC'S WORDING, and it is deliberate. The spec says
 * the card reads "your episode reached N people". The number available is
 * `total_reach` from episode_rollup, which is a SUM OF VIEW COUNTS across the
 * episode's cuts — someone who watched the episode and then saw two clips is
 * three in it. Printing "N people" would be a claim the data does not make, on
 * the one artifact a guest is most likely to screenshot and post. The card says
 * "watched N times, across the episode and every clip", which is true, is
 * warmer, and is the same number.
 */

import { episodes, episodeClips, windowFor } from '../data.js';
import { full, compact, bkk, clip, PLATFORM_NAME } from '../format.js';
import { filename, episodeSlug } from './index.js';
import { download } from './csv.js';
import { renderGuestCard, PNG_SIZE } from './png.js';
import { startArtifact, masthead, colophon, fig, printTable, proportionBar, el } from './page.js';

const shareUrl = (episode) => `https://www.youtube.com/watch?v=${episode.youtubeVideoId}`;

startArtifact({
  title: 'Guest card',
  render: async (root, query) => {
    const id = Number(query.episode);
    if (!Number.isFinite(id)) throw new Error('No episode was named in the link.');

    const list = await episodes();
    if (!list.ok) throw new Error(list.reason);
    const episode = list.current.rows.find((r) => r.episodeId === id);
    if (!episode) throw new Error(`There is no episode ${id}.`);

    const lifetime = await windowFor({ frame: 'all', granularity: 'day', platform: 'all' });
    const clips = await episodeClips(id, lifetime);
    const cuts = clips.ok
      ? clips.current.rows.filter((r) => r.postId !== `yt:${episode.youtubeVideoId}`)
        .sort((a, b) => b.viewsEnd - a.viewsEnd)
      : [];
    const topClip = cuts[0] ?? null;

    root.replaceChildren();
    root.appendChild(masthead('Guest card', bkk(new Date().toISOString())));
    root.appendChild(card(episode, topClip, cuts));
    root.appendChild(await colophon(
      { platforms: 'all', lifetime: true },
      ['"Watched N times" is the sum of view counts across the episode and every '
       + 'clip matched to it. It is not a count of people — one person who watched '
       + 'the episode and then saw two clips is three in that figure.'],
    ));

    const pngName = filename('guest-card', episodeSlug(episode), 'png');
    addPngButton(episode, topClip, pngName);
    if (query.download === 'png') {
      /* Opened from the dashboard's PNG button: produce the file rather than
         making someone click a second time in a tab they did not ask for. */
      await downloadPng(episode, topClip, pngName);
    }

    return { filename: filename('guest-card', episodeSlug(episode), 'pdf') };
  },
});

/* --- the printed card ------------------------------------------------------ */

function card(episode, topClip, cuts) {
  const section = el('section', 'card-square');

  section.appendChild(el('span', 'eyebrow',
    `Season ${episode.season} · Episode ${episode.number}`));
  section.appendChild(el('h1', null, episode.guest));
  if (episode.role) section.appendChild(el('p', 'lede', episode.role));
  section.appendChild(el('p', 'fine', episode.publishedAt
    ? `Published ${bkk(episode.publishedAt.toISOString())}`
    : ''));

  const number = el('div');
  number.style.marginTop = '8pt';
  number.appendChild(el('span', 'eyebrow', 'Watched'));
  number.appendChild(el('p', 'hero-number', full(episode.totalReach)));
  number.appendChild(el('p', 'lede', 'times, across the episode and every clip.'));
  section.appendChild(number);

  const parts = [
    { id: 'youtube', name: PLATFORM_NAME.youtube,
      value: episode.ytViews + episode.clipViews.youtube },
    { id: 'instagram', name: PLATFORM_NAME.instagram, value: episode.clipViews.instagram },
    { id: 'tiktok', name: PLATFORM_NAME.tiktok, value: episode.clipViews.tiktok },
  ].filter((p) => p.value > 0);
  if (parts.length) section.appendChild(proportionBar(parts, full));

  if (topClip) {
    const clipBox = el('div', 'clip-row');
    clipBox.style.marginTop = '8pt';
    clipBox.appendChild(el('span', 'eyebrow',
      `Travelled furthest · ${PLATFORM_NAME[topClip.platform]} · ${full(topClip.viewsEnd)}`));
    clipBox.appendChild(el('h3', null, clip(topClip.title, 90) || topClip.postId));
    if (topClip.url) {
      const a = el('a', null, topClip.url);
      a.href = topClip.url;
      clipBox.appendChild(el('p', 'fine')).appendChild(a);
    }
    section.appendChild(clipBox);
  } else if (cuts.length === 0) {
    section.appendChild(el('p', 'empty', 'No clips have been matched to this episode yet.'));
  }

  const share = el('p', 'fine');
  share.style.marginTop = 'auto';
  const link = el('a', null, shareUrl(episode));
  link.href = shareUrl(episode);
  share.append(document.createTextNode('Watch it again: '), link);
  section.appendChild(share);

  return section;
}

/* --- the PNG --------------------------------------------------------------- */

function addPngButton(episode, topClip, name) {
  const toolbar = document.getElementById('toolbar');
  const button = el('button', null, `Download PNG (${PNG_SIZE}×${PNG_SIZE})`);
  button.type = 'button';
  button.dataset.png = '';
  button.addEventListener('click', async () => {
    button.disabled = true;
    const label = button.textContent;
    button.textContent = 'Drawing…';
    try {
      await downloadPng(episode, topClip, name);
    } catch (err) {
      const problem = document.getElementById('status');
      problem.className = 'problem';
      problem.textContent = String(err?.message ?? err);
    }
    button.textContent = label;
    button.disabled = false;
  });
  toolbar.insertBefore(button, toolbar.querySelector('[data-hint]'));
}

async function downloadPng(episode, topClip, name) {
  const blob = await renderGuestCard({ episode, topClip, shareUrl: shareUrl(episode) });
  download(blob, name);
}
