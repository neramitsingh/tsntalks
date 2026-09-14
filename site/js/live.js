import {
  load, full, compact, pct, bkk, freshness, stillImage, ageBand,
  STACK, PLATFORM_NAME, PLATFORM_COLOR, PLATFORM_HANDLE, PLATFORM_URL, COUNTRY,
} from '../js/live-data.js';

const $ = (id) => document.getElementById(id);
const BASE = import.meta.url;

/* Platform captions run long and carry emoji; cut on a word, never mid-word. */
function clip(text, n) {
  const one = (text || '').split(/\r?\n/)[0].trim();
  if (one.length <= n) return one;
  const cut = one.slice(0, n);
  const sp = cut.lastIndexOf(' ');
  return `${(sp > n * 0.6 ? cut.slice(0, sp) : cut).replace(/[\s,.;:…-]+$/, '')}…`;
}

const MONTH = (m) => new Date(`${m}-01T00:00:00Z`)
  .toLocaleDateString('en-GB', { month: 'short', year: '2-digit', timeZone: 'UTC' });

/* --- one number ---------------------------------------------------------- */

function renderTotal(d) {
  $('total').innerHTML = `${(d.total_views / 1e6).toFixed(2)}<i>M</i>`;
  $('totalnote').textContent =
    `views across the three platforms, all time. ${full(d.total_views)} exactly, `
    + `on ${full(Object.values(d.platforms).reduce((a, p) => a + p.posts, 0))} posts.`;

  $('prop').replaceChildren(...STACK.map((k) => {
    const i = document.createElement('i');
    i.style.width = `${(d.platforms[k].views / d.total_views) * 100}%`;
    i.style.background = PLATFORM_COLOR[k];
    i.title = `${PLATFORM_NAME[k]}: ${full(d.platforms[k].views)} views`;
    return i;
  }));
  $('propleg').innerHTML = STACK.map((k) =>
    `<span><i style="background:${PLATFORM_COLOR[k]}"></i>${PLATFORM_NAME[k]} `
    + `${pct(d.platforms[k].views, d.total_views)}%</span>`).join('');
}

function renderLegend(d) {
  $('legend').innerHTML = STACK.map((k) => {
    const p = d.platforms[k];
    return `<div class="card" style="--plat:${PLATFORM_COLOR[k]}">
      <h3>${PLATFORM_NAME[k]}</h3>
      <p class="h"><a href="${PLATFORM_URL[k]}" target="_blank" rel="noopener">${PLATFORM_HANDLE[k]}</a></p>
      <dl>
        <dt>Views</dt><dd>${full(p.views)}</dd>
        <dt>Followers</dt><dd>${full(p.followers)}</dd>
        <dt>Posts</dt><dd>${full(p.posts)}</dd>
        <dt>Best post</dt><dd>${full(p.top.views)}</dd>
      </dl>
    </div>`;
  }).join('');
}

/* --- when the hits happened ---------------------------------------------- */

/* Stacked columns of views by publish month, three series, zero-filled so the
   axis has no gaps. Direct label on the tallest month only; the rest is in the
   table twin below, which is the same numbers, not a summary of them. */
function renderColumns(d) {
  const keys = [...new Set(d.months.map((r) => r.m))].sort();
  const byMonth = new Map(keys.map((m) => [m, { m, total: 0, youtube: 0, instagram: 0, tiktok: 0 }]));
  for (const r of d.months) {
    const row = byMonth.get(r.m);
    row[r.platform] = r.views;
    row.total += r.views;
  }
  const rows = keys.map((m) => byMonth.get(m));
  const max = Math.max(...rows.map((r) => r.total)) || 1;
  const peak = rows.reduce((a, r) => (r.total > a.total ? r : a), rows[0]);

  $('cols').replaceChildren(...rows.map((r) => {
    const col = document.createElement('div');
    col.className = 'col';

    const lab = document.createElement('b');
    lab.className = 'col-peak';
    lab.textContent = r === peak ? compact(r.total) : '';
    col.appendChild(lab);

    const stack = document.createElement('div');
    stack.className = 'col-stack';
    stack.style.height = `${(r.total / max) * 100}%`;
    stack.title = `${MONTH(r.m)}: ${full(r.total)} views`;
    for (const k of STACK) {
      if (!r[k]) continue;
      const seg = document.createElement('i');
      seg.className = 'col-seg';
      seg.style.flex = String(r[k]);
      seg.style.background = PLATFORM_COLOR[k];
      stack.appendChild(seg);
    }
    col.appendChild(stack);

    const cap = document.createElement('span');
    cap.className = 'col-lab';
    cap.textContent = MONTH(r.m);
    col.appendChild(cap);
    return col;
  }));

  $('colsleg').innerHTML = STACK.map((k) =>
    `<span><i style="background:${PLATFORM_COLOR[k]}"></i>${PLATFORM_NAME[k]}</span>`).join('');

  $('monthstab').innerHTML =
    '<caption class="vh">Views by publish month and platform</caption>'
    + `<tr><th scope="col">Month</th>${STACK.map((k) => `<th scope="col" class="r">${PLATFORM_NAME[k]}</th>`).join('')}`
    + '<th scope="col" class="r">Total</th></tr>'
    + rows.map((r) => `<tr><th scope="row">${MONTH(r.m)}</th>`
      + STACK.map((k) => `<td class="r">${full(r[k])}</td>`).join('')
      + `<td class="r"><b>${full(r.total)}</b></td></tr>`).join('');
}

/* --- who is watching ------------------------------------------------------ */

function barTable(el, caption, rows, { label, value, colour, share = true }) {
  const total = rows.reduce((a, r) => a + r.value, 0);
  const max = Math.max(...rows.map((r) => r.value)) || 1;
  el.style.setProperty('--plat', colour);
  el.innerHTML = `<caption>${caption}</caption>`
    + `<tr><th scope="col">${label}</th><th scope="col"><span class="vh">As a bar</span></th>`
    + `<th scope="col" class="r">${value}</th>${share ? '<th scope="col" class="r">Share</th>' : ''}</tr>`
    + rows.map((r) => `<tr><th scope="row">${r.label}</th>`
      + `<td class="bar"><i style="width:${(r.value / max) * 100}%"></i></td>`
      + `<td class="r">${r.display ?? full(r.value)}</td>`
      + (share ? `<td class="r">${pct(r.value, total)}%</td>` : '') + '</tr>').join('');
}

function renderAudience(d) {
  const cty = d.demographics.yt_country.slice(0, 6);
  barTable($('ctytab'), 'YouTube views by country · last 90 days',
    cty.map((c) => ({ label: COUNTRY[c.dimension] || c.dimension, value: c.value })),
    { label: 'Country', value: 'Views', colour: 'var(--yt)' });

  const city = d.demographics.ig_city.slice(0, 6);
  barTable($('igcitytab'), 'Instagram followers by city · last 30 days',
    city.map((c) => ({ label: c.dimension.split(',')[0], value: c.value })),
    { label: 'City', value: 'Followers', colour: 'var(--ig)' });

  const age = d.demographics.yt_age;
  barTable($('agetab'), 'YouTube views by age · last 90 days',
    age.map((a) => ({ label: ageBand(a.dimension), value: a.value, display: `${a.value.toFixed(1)}%` })),
    { label: 'Age', value: 'Share of views', colour: 'var(--yt)', share: false });
}

/* Four plain facts, each a sentence carrying its own window. */
function renderFacts(d) {
  const y = d.yt_90d;
  const net = y.subs_gained - y.subs_lost;
  const hours = Math.round(y.minutes / 60);
  const male = d.demographics.yt_gender.find((g) => g.dimension === 'male')?.value ?? 0;
  $('facts').innerHTML = [
    `<b>${full(y.views)}</b> YouTube views in the last 90 days.`,
    `<b>${full(hours)}</b> hours watched on YouTube over the same window.`,
    `<b>${net >= 0 ? '+' : ''}${full(net)}</b> net YouTube subscribers in 90 days: `
      + `${full(y.subs_gained)} gained, ${full(y.subs_lost)} lost.`,
    `<b>${male.toFixed(0)}%</b> of YouTube viewers are men.`,
  ].map((t) => `<li>${t}</li>`).join('');
}

/* --- now playing ---------------------------------------------------------- */

function renderTop(d) {
  const latest = d.episodes[0];
  const tiles = [{
    cls: 'big',
    href: latest.url,
    img: latest.youtube_video_id,
    kicker: `Latest episode · ${bkk(latest.published_at)}`,
    title: latest.guest,
    note: `${full(latest.views)} views on YouTube · ${latest.clips} clips, ${full(latest.clip_views)} views`,
  }];

  for (const k of ['youtube', 'instagram', 'tiktok']) {
    const t = d.platforms[k].top;
    tiles.push({
      cls: 'mid',
      href: t.url,
      thumb: t.thumb,
      kicker: `Top on ${PLATFORM_NAME[k]} · ${bkk(t.date)}`,
      title: (t.title || '').split('\n')[0].slice(0, 70),
      note: `${full(t.views)} views`,
      colour: PLATFORM_COLOR[k],
    });
  }

  $('top').replaceChildren(...tiles.map((t) => {
    const a = document.createElement('a');
    a.className = `po ${t.cls}`;
    a.href = t.href;
    a.target = '_blank';
    a.rel = 'noopener';

    if (t.img) {
      a.appendChild(stillImage(t.img, '', BASE));
    } else if (t.thumb) {
      const img = new Image();
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      /* Instagram and TikTok CDN thumbs expire; the tile keeps its ground when they do. */
      img.addEventListener('error', () => img.remove());
      img.src = t.thumb;
      a.appendChild(img);
    }

    const box = document.createElement('div');
    box.className = 't';
    box.innerHTML = '<div class="n"></div><div class="g"></div><div class="v"></div>';
    if (t.colour) box.querySelector('.n').style.color = t.colour;
    box.querySelector('.n').textContent = t.kicker;
    box.querySelector('.g').textContent = t.title;
    box.querySelector('.v').textContent = t.note;
    a.appendChild(box);
    return a;
  }));
}

/* --- the footer, which is the point of the page --------------------------- */

function renderFooter(d) {
  const f = freshness(d.fetched_at);
  $('srcfoot').innerHTML =
    '<div>Views, followers and post counts come from YouTube, Instagram and TikTok through Zernio. '
    + 'Audience breakdowns are the platforms’ own, over a rolling 90-day window on YouTube and 30 days '
    + 'on Instagram. Collected hourly; the platforms themselves report with a delay of up to 48 hours.</div>'
    + `<div class="fine">${f.stale ? '' : '<span class="live"></span>'}Updated ${f.stamp} Bangkok`
    + `${f.stale ? ` · ${f.hours} hours ago` : ''}</div>`;
}

load((d) => {
  renderTotal(d);
  renderLegend(d);
  renderColumns(d);
  renderAudience(d);
  renderFacts(d);
  renderTop(d);
  renderFooter(d);
});
