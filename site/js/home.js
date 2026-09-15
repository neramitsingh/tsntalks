import {
  load, full, compact, pct, bkk, freshness, stillImage, ageBand,
  STACK, PLATFORM_NAME, PLATFORM_COLOR, COUNTRY,
} from './live-data.js';

const $ = (id) => document.getElementById(id);
const BASE = import.meta.url;

const episodeLabel = (e) => (e.number === '0' ? 'Kickoff' : `S${e.season} · E${e.number}`);

/* The hero shows the episode's own artwork whole and says, in the page's own
   voice, what the artwork cannot: what this show is and what it costs to be in
   it. The <h1> is the show, not the week's guest — a heading that changed every
   episode meant a screen reader announced a stranger's name as the page title,
   and a sponsor arriving cold never learned what they had opened. */
function renderHero(d) {
  const e = d.episodes[0];
  const img = stillImage(e.youtube_video_id, `TSN Talks ${episodeLabel(e)} — ${e.guest}`, BASE, { eager: true });
  img.id = 'heroimg';
  $('heroimg').replaceWith(img);

  const num = e.number === '0' ? 'Season kickoff' : `Episode ${e.number}`;
  $('herolink').href = e.url;
  $('herocap').innerHTML = '<b></b><span></span><span></span>';
  const [g, role, when] = $('herocap').children;
  g.textContent = e.guest;
  role.textContent = e.role || '';
  when.textContent = `Season ${e.season} · ${num} · ${bkk(e.published_at)}`;

  $('watch').href = e.url;
  $('watch').setAttribute('aria-label', `Watch ${e.guest} on YouTube`);
  $('reach').textContent =
    `in front of ${compact(d.total_views)} views across YouTube, Instagram and TikTok`;
}

function renderStrap(d) {
  const f = freshness(d.fetched_at);
  const strap = $('strap');
  strap.classList.toggle('stale', f.stale);
  const eps = d.episodes.length;
  /* Say it in words. Dimming the text was the only stale signal, and nobody
     notices the absence of a dot they never saw in the first place. */
  const flag = f.stale
    ? `<span class="stale-flag">Last updated ${f.hours} hours ago</span>`
    : '<span class="live">Live</span>';
  strap.innerHTML = `${flag}
    <span><b>${full(d.total_views)}</b> views across YouTube, Instagram and TikTok</span>
    <span><b>${full(d.total_followers)}</b> followers</span>
    <span><b>${eps}</b> ${eps === 1 ? 'episode' : 'episodes'}</span>
    <span>Updated ${f.stamp} Bangkok</span>`;
}

/* The episode wall. Every tile shows its thumbnail whole, with the caption
   underneath rather than printed over it.

   Two things changed here and both were substantive. The tiles used to be
   ranked by view count, which guaranteed the biggest tile carried the biggest
   number and every tile after it visibly decayed — a deficit gradient, and the
   one shape PRODUCT.md's first principle rules out. They run newest first now,
   which is also what a visitor expects from a show. And the view count has come
   off the tile: season two's numbers are four and three digits, so a wall of
   them argued against the 2.37M figure in the strap directly above it. The
   tiles say who was on; the audience section says how many watched. */
function renderWall(d) {
  const eps = d.episodes
    .filter((e) => e.season === 2)
    .sort((a, b) => new Date(b.published_at) - new Date(a.published_at));

  $('wall').replaceChildren(...eps.map((e, i) => {
    const a = document.createElement('a');
    a.className = i === 0 ? 'po lead' : 'po';
    a.href = e.url;
    a.target = '_blank';
    a.rel = 'noopener';
    a.appendChild(stillImage(e.youtube_video_id, '', BASE));

    const t = document.createElement('div');
    t.className = 't';
    t.innerHTML = '<div class="n"></div><div class="g"></div><div class="v"></div>';
    t.querySelector('.n').textContent = i === 0 ? `Latest · ${episodeLabel(e)}` : episodeLabel(e);
    t.querySelector('.g').textContent = e.guest;
    t.querySelector('.v').textContent = e.role || '';
    a.appendChild(t);

    a.setAttribute('aria-label', `${e.guest}, ${episodeLabel(e)} — watch on YouTube`);
    return a;
  }));
}

function renderIndex(d) {
  const s1 = d.episodes.filter((e) => e.season === 1);
  $('s1').replaceChildren(...s1.map((e) => {
    const li = document.createElement('li');
    li.innerHTML = '<b></b><div><a target="_blank" rel="noopener"></a><small></small></div>';
    li.querySelector('b').textContent = String(e.number).padStart(2, '0');
    const a = li.querySelector('a');
    a.textContent = e.guest;
    a.href = e.url;
    li.querySelector('small').textContent = e.role || '';
    return li;
  }));
  $('s1count').textContent = `${s1.length} episodes`;
}

function renderAudience(d) {
  const male = d.demographics.yt_gender.find((g) => g.dimension === 'male')?.value ?? 0;
  const topAge = d.demographics.yt_age[0];
  const cty = d.demographics.yt_country;
  const ctot = cty.reduce((a, c) => a + c.value, 0);
  const inShare = pct(cty.find((c) => c.dimension === 'IN')?.value ?? 0, ctot);
  const thShare = pct(cty.find((c) => c.dimension === 'TH')?.value ?? 0, ctot);
  const posts = Object.values(d.platforms).reduce((a, p) => a + p.posts, 0);

  /* Lifetime total, then a 90-day window. YouTube and Instagram only report
     demographics over a rolling window, so the window is named rather than
     quietly presented as if it described the lifetime figure above it. */
  $('bignum').innerHTML = `${(d.total_views / 1e6).toFixed(2)}<i>M</i>`;
  $('audp').innerHTML =
    `views on ${full(posts)} episodes and clips across the three platforms, all time. `
    + `Over the last 90 days, <b>${male.toFixed(0)}%</b> of YouTube viewers are men and `
    + `<b>${topAge.value.toFixed(0)}%</b> are ${topAge.dimension}; `
    + `<b>${thShare}%</b> of views came from Thailand and <b>${inShare}%</b> from India. `
    + `On Instagram the audience is Bangkok first.`;

  $('prop').replaceChildren(...STACK.map((k) => {
    const i = document.createElement('i');
    i.style.width = `${(d.platforms[k].views / d.total_views) * 100}%`;
    i.style.background = PLATFORM_COLOR[k];
    i.title = `${PLATFORM_NAME[k]}: ${full(d.platforms[k].views)} views`;
    return i;
  }));

  $('propleg').innerHTML = STACK.map((k) =>
    `<span><i style="background:${PLATFORM_COLOR[k]}"></i>${PLATFORM_NAME[k]} `
    + `${pct(d.platforms[k].views, d.total_views)}% · ${compact(d.platforms[k].views)}</span>`).join('');

  const age = d.demographics.yt_age;
  const amax = Math.max(...age.map((a) => a.value));
  $('agetab').innerHTML =
    '<caption>YouTube viewers by age · last 90 days</caption>'
    + '<tr><th scope="col">Age</th><th scope="col"><span class="vh">Share, as a bar</span></th>'
    + '<th scope="col" class="r">Share of views</th></tr>'
    + age.map((a) => `<tr><th scope="row">${ageBand(a.dimension)}</th>`
      + `<td class="bar"><i style="width:${(a.value / amax) * 100}%"></i></td>`
      + `<td class="r">${a.value.toFixed(1)}%</td></tr>`).join('');

  $('ctytab').innerHTML =
    '<caption>YouTube views by country · last 90 days</caption>'
    + '<tr><th scope="col">Country</th><th scope="col" class="r">Views</th><th scope="col" class="r">Share</th></tr>'
    + cty.slice(0, 5).map((c) => `<tr><th scope="row">${COUNTRY[c.dimension] || c.dimension}</th>`
      + `<td class="r">${full(c.value)}</td><td class="r">${pct(c.value, ctot)}%</td></tr>`).join('');
}

load((d) => {
  renderHero(d);
  renderStrap(d);
  renderWall(d);
  renderIndex(d);
  renderAudience(d);
});
