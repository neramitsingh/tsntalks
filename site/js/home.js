import {
  load, full, compact, bkk, freshness, hasStill, stillUrl, faceImage,
} from './live-data.js';

const $ = (id) => document.getElementById(id);
const BASE = import.meta.url;

const episodeLabel = (e) => (e.number === '0' ? 'Kickoff' : `S${e.season} · E${e.number}`);
const initials = (name) => name.replace(/^(Mr\.|Dr\.|Major)\s+/, '').split(/\s+/).map((w) => w[0]).slice(0, 2).join('');

/* The room. The photograph is a frame from the newest episode that has one —
   never a thumbnail, because a thumbnail carries a headline and the offer would
   collide with it. The caption names the guest; the page's type never re-sets a
   name the artwork already carries. If no episode has a frame yet, the room is
   the ground colour and the caption is the show. */
function renderRoom(d) {
  const newest = d.episodes[0];
  const shown = d.episodes.find((e) => hasStill(e.youtube_video_id)) || null;

  const art = $('roomart');
  art.replaceChildren();
  if (shown) {
    const img = new Image();
    img.src = stillUrl(shown.youtube_video_id, BASE);
    img.alt = '';
    img.decoding = 'async';
    img.fetchPriority = 'high';
    art.appendChild(img);
  }

  const cap = $('herocap');
  cap.replaceChildren();
  const who = shown || newest;
  const b = document.createElement('b');
  b.textContent = who.guest;
  const role = document.createTextNode(who.role || '');
  const ep = document.createElement('span');
  ep.className = 'ep';
  const num = who.number === '0' ? 'Season kickoff' : `Episode ${who.number}`;
  ep.textContent = `Season ${who.season} · ${num} · ${bkk(who.published_at)} · `;
  const watch = document.createElement('a');
  watch.id = 'watch';
  watch.className = 'watch';
  watch.href = newest.url;
  watch.target = '_blank';
  watch.rel = 'noopener';
  watch.textContent = shown && shown !== newest ? 'Watch the latest' : 'Watch on YouTube';
  watch.setAttribute('aria-label', `Watch ${newest.guest} on YouTube`);
  ep.appendChild(watch);
  cap.append(b, role, ep);

  $('reach').textContent =
    `The audience is ${compact(d.total_views)} views across YouTube, Instagram and TikTok, read live.`;
}

function renderStrap(d) {
  const f = freshness(d.fetched_at);
  const strap = $('strap');
  strap.classList.toggle('stale', f.stale);
  const eps = d.episodes.length;
  const flag = f.stale
    ? `<span class="stale-flag">Last updated ${f.hours} hours ago</span>`
    : '<span class="live">Live</span>';
  strap.innerHTML = `${flag}
    <span><b>${full(d.total_views)}</b> views across YouTube, Instagram and TikTok</span>
    <span><b>${full(d.total_followers)}</b> followers</span>
    <span><b>${eps}</b> ${eps === 1 ? 'episode' : 'episodes'}</span>
    <span>Updated ${f.stamp} Bangkok</span>`;
}

/* One face tile. The image walks its own chain — face crop, episode still,
   thumbnail — and the tile falls back to the initials on wood only when every
   image source has failed, so a slow network never shows an empty box. */
function faceTile(e, { small = false } = {}) {
  const a = document.createElement('a');
  a.className = 'face';
  a.href = e.url;
  a.target = '_blank';
  a.rel = 'noopener';
  a.setAttribute('aria-label', `${e.guest}, ${episodeLabel(e)} — watch on YouTube`);

  const sq = document.createElement('div');
  sq.className = 'sq';
  sq.dataset.init = initials(e.guest);
  const img = faceImage(e.youtube_video_id, '', BASE);
  img.addEventListener('exhausted', () => { a.classList.add('nopic'); img.remove(); });
  sq.appendChild(img);

  const t = document.createElement('div');
  t.className = 't';
  t.innerHTML = '<div class="g"></div><div class="v"></div><div class="n"></div>';
  t.querySelector('.g').textContent = e.guest;
  t.querySelector('.v').textContent = small ? '' : (e.role || '');
  t.querySelector('.n').textContent = episodeLabel(e);

  a.append(sq, t);
  return a;
}

function renderFaces(d) {
  const byDate = (a, b) => new Date(b.published_at) - new Date(a.published_at);
  const s2 = d.episodes.filter((e) => e.season === 2).sort(byDate);
  const s1 = d.episodes.filter((e) => e.season === 1).sort(byDate);
  $('faces').replaceChildren(...s2.map((e) => faceTile(e)));
  $('s1').replaceChildren(...s1.map((e) => faceTile(e, { small: true })));
  $('s1count').textContent = `${s1.length} episodes · 2024 to 2025`;
}

/* Sponsors come from site/data/sponsors.json and the section stays hidden
   until that file names someone. Until Sunny confirms which season-one logos
   were paid placements, the page makes no claim. */
async function renderSponsors() {
  try {
    const r = await fetch(new URL('../data/sponsors.json', BASE).href, { cache: 'no-store' });
    if (!r.ok) return;
    const list = await r.json();
    if (!Array.isArray(list) || list.length === 0) return;
    $('wallof').replaceChildren(...list.map((s) => {
      if (s.logo) {
        const img = new Image();
        img.src = new URL(`../img/sponsors/${s.logo}`, BASE).href;
        img.alt = s.name;
        img.height = 40;
        return img;
      }
      const b = document.createElement('b');
      b.textContent = s.name;
      return b;
    }), Object.assign(document.createElement('b'), { className: 'you', textContent: 'Your brand here' }));
    $('sponsors').hidden = false;
  } catch { /* no sponsors file: the section stays hidden */ }
}

/* The reply channel. The sponsor arrived from a LINE thread; a mail link inside
   LINE's in-app browser is where the journey used to end. When contact.json
   carries a LINE link it becomes the primary button and email steps back. */
async function renderContact() {
  try {
    const r = await fetch(new URL('../data/contact.json', BASE).href, { cache: 'force-cache' });
    if (!r.ok) return;
    const c = await r.json();
    const mail = `mailto:${c.email}?subject=${encodeURIComponent('TSN Talks sponsorship')}`;
    for (const id of ['cta', 'cta2']) {
      const a = $(id);
      if (c.line) {
        a.href = c.line;
        a.textContent = 'Message us on LINE';
        a.classList.add('line');
        a.target = '_blank';
        a.rel = 'noopener';
      } else {
        a.href = mail;
      }
    }
    if (c.line) {
      const n = $('navcta');
      n.href = c.line; n.textContent = 'LINE'; n.classList.add('line'); n.target = '_blank'; n.rel = 'noopener';
    }
  } catch { /* the static mailto stays */ }
}

load((d) => {
  renderRoom(d);
  renderStrap(d);
  renderFaces(d);
});
renderSponsors();
renderContact();
