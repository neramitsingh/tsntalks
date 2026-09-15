/* The numbers.
   Baked copy first so the page never renders empty, then the hourly copy from
   Supabase Storage applied in place. Every page imports its formatters from here
   so no two pages can round the same figure differently. */

const STORAGE_URL =
  'https://xygppcxxfggydlwgoadw.supabase.co/storage/v1/object/public/public/live.json';
const BAKED_URL = new URL('../data/live.json', import.meta.url).href;
const STALE_AFTER_MS = 3 * 60 * 60 * 1000;

export const PLATFORMS = ['youtube', 'instagram', 'tiktok'];

/* Stack order for every proportion bar and column: largest first, so the bar
   reads left to right without reordering as the numbers move. */
export const STACK = ['tiktok', 'instagram', 'youtube'];

export const PLATFORM_NAME = { youtube: 'YouTube', instagram: 'Instagram', tiktok: 'TikTok' };
export const PLATFORM_COLOR = { youtube: 'var(--yt)', instagram: 'var(--ig)', tiktok: 'var(--tt)' };
export const PLATFORM_HANDLE = {
  youtube: '@TSNTalksTH',
  instagram: '@tsntalks',
  tiktok: '@tsntalks.th',
};
export const PLATFORM_URL = {
  youtube: 'https://www.youtube.com/@TSNTalksTH',
  instagram: 'https://www.instagram.com/tsntalks',
  tiktok: 'https://www.tiktok.com/@tsntalks.th',
};

export const COUNTRY = {
  IN: 'India', TH: 'Thailand', US: 'United States', AU: 'Australia',
  GB: 'United Kingdom', CA: 'Canada', SG: 'Singapore', AE: 'United Arab Emirates',
  MY: 'Malaysia', HK: 'Hong Kong', NZ: 'New Zealand', DE: 'Germany',
  ID: 'Indonesia', PH: 'Philippines', JP: 'Japan', KR: 'South Korea',
  NL: 'Netherlands', IT: 'Italy', ES: 'Spain', FR: 'France', ZA: 'South Africa',
  PK: 'Pakistan', BD: 'Bangladesh', LK: 'Sri Lanka', NP: 'Nepal', VN: 'Vietnam',
};

/* `full` is the number a sponsor can quote; `compact` is for tight spaces.
   Every compact figure on the page has its full value in a title or a table twin. */
export const full = (n) => Number(n || 0).toLocaleString('en-US');

export const compact = (n) => {
  n = Number(n || 0);
  if (n >= 1e6) return `${(n / 1e6).toFixed(2).replace(/\.?0+$/, '')}M`;
  if (n >= 1e4) return `${Math.round(n / 1e3)}K`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1).replace(/\.0$/, '')}K`;
  return String(n);
};

/* YouTube labels the oldest band "65-", meaning 65 and over. */
export const ageBand = (d) => (d.endsWith('-') ? `${d.slice(0, -1)}+` : d);

export const pct = (part, whole) => (whole ? Math.round((part / whole) * 100) : 0);

export const bkk = (iso, opts = { day: 'numeric', month: 'short', year: 'numeric' }) =>
  (iso ? new Date(iso).toLocaleDateString('en-GB', { ...opts, timeZone: 'Asia/Bangkok' }) : '');

export const bkkStamp = (iso) =>
  new Date(iso).toLocaleString('en-GB', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Bangkok',
  });

/* Freshness. The strap says "Live" only when the data really is. */
export function freshness(fetchedAt) {
  const age = Date.now() - new Date(fetchedAt).getTime();
  return {
    stale: !(age >= 0 && age < STALE_AFTER_MS),
    stamp: bkkStamp(fetchedAt),
    hours: Math.max(0, Math.floor(age / 3.6e6)),
  };
}

/* Which video ids have a committed still override. Filled by load() from
   img/episodes/index.json, which the Pages workflow generates from the folder —
   so dropping a .jpg in there is still the whole change. Without the manifest
   every tile would fire a 404 probing for a file that is usually absent. */
let OVERRIDES = new Set();
let FACES = new Set();

export const hasStill = (videoId) => OVERRIDES.has(videoId);
export const stillUrl = (videoId, baseUrl) => new URL(`../img/episodes/${videoId}.jpg`, baseUrl).href;

/* Episode still: a committed override wins, then YouTube's maxres image, then
   hqdefault, which always exists. */
export function stills(videoId, baseUrl) {
  const chain = [
    `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`,
    `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
  ];
  if (OVERRIDES.has(videoId)) {
    chain.unshift(new URL(`../img/episodes/${videoId}.jpg`, baseUrl).href);
  }
  return chain;
}

/* An <img> that walks the still chain on error without reflowing the layout. */
export function stillImage(videoId, alt, baseUrl, { eager = false } = {}) {
  const chain = stills(videoId, baseUrl);
  const img = new Image();
  img.alt = alt;
  img.decoding = 'async';
  img.loading = eager ? 'eager' : 'lazy';
  let step = 0;
  img.addEventListener('error', () => {
    step += 1;
    if (step < chain.length) img.src = chain[step];
  });
  img.src = chain[0];
  return img;
}

/* A face tile: the 4:5 crop from the episode's own footage first, then the
   episode still, then the thumbnails. The <img> carries class "crop" while it
   shows a face crop and "thumb" once it has fallen back to artwork, so the CSS
   can frame a thumbnail on the guest. It dispatches "exhausted" when nothing loads. */
export function faceImage(videoId, alt, baseUrl) {
  const chain = [];
  if (FACES.has(videoId)) chain.push(new URL(`../img/faces/${videoId}.jpg`, baseUrl).href);
  chain.push(...stills(videoId, baseUrl));
  const img = new Image();
  img.alt = alt;
  img.decoding = 'async';
  img.loading = 'lazy';
  let step = 0;
  const cls = () => { img.className = chain[step].includes('/img/faces/') ? 'crop' : 'thumb'; };
  img.addEventListener('error', () => {
    step += 1;
    if (step < chain.length) { cls(); img.src = chain[step]; }
    else img.dispatchEvent(new Event('exhausted'));
  });
  cls();
  img.src = chain[0];
  return img;
}

async function fetchJson(url, init) {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

/**
 * Render immediately from the committed copy, then again from Storage if it is newer.
 * A failure of either source is survivable; a failure of both marks the document
 * so the page can say so instead of showing an empty frame.
 * @param {(data: object, meta: {source: 'baked'|'live'}) => void} render
 */
export async function load(render) {
  try {
    OVERRIDES = new Set(await fetchJson(new URL('../img/episodes/index.json', import.meta.url).href,
                                        { cache: 'force-cache' }));
  } catch {
    OVERRIDES = new Set();          // no manifest: every still comes from YouTube
  }
  try {
    FACES = new Set(await fetchJson(new URL('../img/faces/index.json', import.meta.url).href,
                                    { cache: 'force-cache' }));
  } catch {
    FACES = new Set();
  }

  let baked = null;
  try {
    baked = await fetchJson(BAKED_URL, { cache: 'force-cache' });
    render(baked, { source: 'baked' });
  } catch (err) {
    console.warn('baked live.json unavailable', err);
  }
  try {
    const live = await fetchJson(STORAGE_URL, { cache: 'no-store' });
    if (!baked || new Date(live.fetched_at) >= new Date(baked.fetched_at)) {
      render(live, { source: 'live' });
    }
    return live;
  } catch (err) {
    console.warn('storage live.json unavailable', err);
    if (!baked) document.documentElement.classList.add('data-failed');
    return baked;
  }
}
