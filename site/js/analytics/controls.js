/* The controls row: frame, granularity, platform, compare.
   Pure state plus one renderer. Knows nothing about Supabase and nothing about
   what a tab does with the result.

   Every control is serialised into the query string, so a view can be pasted
   into LINE and opened on the same numbers. Reload restores it. */

import { PLATFORM_NAME } from '../live-data.js';

export const TABS = ['overview', 'growth', 'posts', 'episodes', 'audience', 'health'];

export const TAB_NAME = {
  overview: 'Overview',
  growth: 'Growth',
  posts: 'Posts',
  episodes: 'Episodes',
  audience: 'Audience',
  health: 'Health',
};

export const FRAMES = ['7d', '30d', '90d', '12m', 'all', 'custom'];

export const FRAME_NAME = {
  '7d': '7 days', '30d': '30 days', '90d': '90 days',
  '12m': '12 months', all: 'All', custom: 'Custom',
};

export const GRANULARITIES = ['hour', 'day', 'week', 'month'];

export const GRANULARITY_NAME = {
  hour: 'Hourly', day: 'Daily', week: 'Weekly', month: 'Monthly',
};

export const PLATFORM_CHOICES = ['all', 'youtube', 'instagram', 'tiktok'];

/* Hourly snapshots survive 90 days and are then thinned to one a day by
   thin_snapshots(), so hourly is only truthful over a short frame. Seven days
   is the line the spec draws and the line the data supports. */
const HOUR_MAX_DAYS = 7;

const DEFAULT_GRANULARITY = {
  '7d': 'day', '30d': 'day', '90d': 'week', '12m': 'month', all: 'month',
};

export const DEFAULT_STATE = {
  tab: 'overview',
  frame: '30d',
  from: '',
  to: '',
  granularity: 'day',
  platform: 'all',
  compare: false,
};

/** Whole days a frame spans, for the granularity rules. */
export function frameDays(state) {
  switch (state.frame) {
    case '7d': return 7;
    case '30d': return 30;
    case '90d': return 90;
    case '12m': return 365;
    case 'all': return Infinity;
    case 'custom': {
      const a = Date.parse(`${state.from}T00:00:00+07:00`);
      const b = Date.parse(`${state.to}T00:00:00+07:00`);
      if (!Number.isFinite(a) || !Number.isFinite(b)) return Infinity;
      return Math.max(1, Math.round((b - a) / 86400000) + 1);
    }
    default: return 30;
  }
}

/** Which granularities this frame may be read at. Hour narrows out above 7 days. */
export function granularityOptions(state) {
  return frameDays(state) <= HOUR_MAX_DAYS ? GRANULARITIES : GRANULARITIES.slice(1);
}

/** The granularity a frame picks for itself when the user has not. */
export function defaultGranularity(state) {
  if (state.frame !== 'custom') return DEFAULT_GRANULARITY[state.frame] ?? 'day';
  const days = frameDays(state);
  if (days <= HOUR_MAX_DAYS) return 'day';
  if (days <= 45) return 'day';
  if (days <= 180) return 'week';
  return 'month';
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Read control state out of a query string. Anything unrecognised falls back to
 * the default rather than throwing — a hand-edited URL should not white-screen.
 */
export function readState(search = window.location.search) {
  const q = new URLSearchParams(search);
  const state = { ...DEFAULT_STATE };

  const tab = q.get('tab');
  if (TABS.includes(tab)) state.tab = tab;

  const frame = q.get('frame');
  if (FRAMES.includes(frame)) state.frame = frame;

  const from = q.get('from');
  const to = q.get('to');
  if (ISO_DATE.test(from ?? '')) state.from = from;
  if (ISO_DATE.test(to ?? '')) state.to = to;
  /* A custom frame with no usable dates is not a custom frame. */
  if (state.frame === 'custom' && !(state.from && state.to && state.from <= state.to)) {
    state.frame = DEFAULT_STATE.frame;
    state.from = '';
    state.to = '';
  }

  const platform = q.get('p');
  if (PLATFORM_CHOICES.includes(platform)) state.platform = platform;

  state.compare = q.get('cmp') === '1';

  const g = q.get('g');
  state.granularity = granularityOptions(state).includes(g) ? g : defaultGranularity(state);

  return state;
}

/** The query string for a state. Defaults are omitted so a plain link stays short. */
export function toSearch(state) {
  const q = new URLSearchParams();
  if (state.tab !== DEFAULT_STATE.tab) q.set('tab', state.tab);
  if (state.frame !== DEFAULT_STATE.frame) q.set('frame', state.frame);
  if (state.frame === 'custom') {
    q.set('from', state.from);
    q.set('to', state.to);
  }
  if (state.granularity !== defaultGranularity(state)) q.set('g', state.granularity);
  if (state.platform !== DEFAULT_STATE.platform) q.set('p', state.platform);
  if (state.compare) q.set('cmp', '1');
  const s = q.toString();
  return s ? `?${s}` : '';
}

/**
 * Apply a change and repair anything it invalidates.
 *
 * Changing the frame can take the current granularity off the menu — 30 days
 * has no hourly reading — so the granularity falls back to that frame's default
 * rather than being silently left at a value the data cannot support.
 */
export function withChange(state, change) {
  const next = { ...state, ...change };

  if (next.frame === 'custom' && !(next.from && next.to)) {
    const today = bangkokToday();
    next.to = next.to || today;
    next.from = next.from || addDays(today, -29);
  }
  if (next.frame === 'custom' && next.from > next.to) {
    /* Whichever end the user just moved wins; the other follows it. */
    if ('from' in change) next.to = next.from;
    else next.from = next.to;
  }
  if (next.frame !== 'custom') {
    next.from = '';
    next.to = '';
  }

  const allowed = granularityOptions(next);
  if (!allowed.includes(next.granularity)) next.granularity = defaultGranularity(next);
  /* A frame change that did not come with an explicit granularity resets to that
     frame's default: 90 days read daily is 270 marks nobody can see. */
  if ('frame' in change && !('granularity' in change)) next.granularity = defaultGranularity(next);

  return next;
}

/** Today in Bangkok, as YYYY-MM-DD. The dashboard's only "now". */
export function bangkokToday() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Bangkok' });
}

export function addDays(isoDate, n) {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/* --- rendering ------------------------------------------------------------ */

function button(label, { pressed, value, name, title }) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'a-btn';
  b.textContent = label;
  b.dataset.control = name;
  b.dataset.value = value;
  b.setAttribute('aria-pressed', String(pressed));
  if (title) b.title = title;
  return b;
}

function group(label, children) {
  const g = document.createElement('div');
  g.className = 'a-group';
  const l = document.createElement('span');
  l.className = 'label';
  l.textContent = label;
  g.appendChild(l);
  const seg = document.createElement('div');
  seg.className = 'a-seg';
  seg.append(...children);
  g.appendChild(seg);
  return g;
}

/**
 * Draw the controls row. `onChange(nextState)` fires with a repaired state.
 * Re-rendered in full on every change — it is four groups of buttons, and a
 * full redraw is cheaper to reason about than a diff.
 */
export function renderControls(el, state, onChange) {
  const change = (c) => onChange(withChange(state, c));

  el.replaceChildren();

  el.appendChild(group('Frame', FRAMES.map((f) =>
    button(FRAME_NAME[f], { pressed: state.frame === f, value: f, name: 'frame' }))));

  const custom = document.createElement('div');
  custom.className = 'a-custom';
  custom.hidden = state.frame !== 'custom';
  for (const key of ['from', 'to']) {
    const input = document.createElement('input');
    input.type = 'date';
    input.className = 'a-date';
    input.value = state[key];
    input.max = bangkokToday();
    input.dataset.control = key;
    input.setAttribute('aria-label', key === 'from' ? 'From date' : 'To date');
    input.addEventListener('change', () => change({ [key]: input.value }));
    if (key === 'to') {
      const dash = document.createElement('span');
      dash.className = 'label';
      dash.textContent = 'to';
      custom.appendChild(dash);
    }
    custom.appendChild(input);
  }
  el.appendChild(custom);

  const allowed = granularityOptions(state);
  el.appendChild(group('By', GRANULARITIES.map((g) => {
    const b = button(GRANULARITY_NAME[g], {
      pressed: state.granularity === g, value: g, name: 'granularity',
      title: allowed.includes(g) ? '' : 'Hourly is only available over 7 days or less',
    });
    b.disabled = !allowed.includes(g);
    return b;
  })));

  el.appendChild(group('Platform', PLATFORM_CHOICES.map((p) =>
    button(p === 'all' ? 'All' : PLATFORM_NAME[p],
           { pressed: state.platform === p, value: p, name: 'platform' }))));

  const cmp = document.createElement('label');
  cmp.className = 'a-check';
  const box = document.createElement('input');
  box.type = 'checkbox';
  box.checked = state.compare;
  box.id = 'compare';
  box.addEventListener('change', () => change({ compare: box.checked }));
  cmp.append(box, document.createTextNode('Compare with previous period'));
  el.appendChild(cmp);

  /* onclick, not addEventListener: this row is redrawn on every change and the
     element itself survives, so a listener added per render would stack. */
  el.onclick = (e) => {
    const b = e.target.closest('button[data-control]');
    if (!b || b.disabled) return;
    change({ [b.dataset.control]: b.dataset.value });
  };
}

/** The tab strip. Separate from the controls row: it selects a view, not a window. */
export function renderTabs(el, state, onChange) {
  el.replaceChildren(...TABS.map((id) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'a-tab';
    b.id = `tab-${id}`;
    b.textContent = TAB_NAME[id];
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(state.tab === id));
    b.setAttribute('aria-controls', 'view');
    b.tabIndex = state.tab === id ? 0 : -1;
    b.addEventListener('click', () => onChange({ ...state, tab: id }));
    return b;
  }));

  /* Arrow keys across a tablist, as the pattern expects. */
  el.onkeydown = (e) => {
    const i = TABS.indexOf(state.tab);
    if (e.key === 'ArrowRight') onChange({ ...state, tab: TABS[(i + 1) % TABS.length] });
    else if (e.key === 'ArrowLeft') onChange({ ...state, tab: TABS[(i - 1 + TABS.length) % TABS.length] });
    else if (e.key === 'Home') onChange({ ...state, tab: TABS[0] });
    else if (e.key === 'End') onChange({ ...state, tab: TABS[TABS.length - 1] });
    else return;
    e.preventDefault();
    el.querySelector('[aria-selected="true"]')?.focus();
  };
}
