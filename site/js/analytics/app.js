/* Boot. Swaps the gate for the shell, owns the control state, and hands the
   active tab a context to render into.

   The only module that touches the page's top-level sections. Tabs get a mount
   element and a context; they never look for `#shell` or a session. */

import {
  configProblem, sendLink, signOut, watchSession, sessionEmail,
} from './supa.js';
import {
  readState, toSearch, withChange, renderControls, renderTabs, TAB_NAME,
} from './controls.js';
import { access, lastRun, clearCache, windowFor } from './data.js';
import { TAB_RENDERERS } from './tabs/index.js';
import { ago, bkkStamp } from './format.js';

const $ = (id) => document.getElementById(id);

let state = readState();
let stopWatching = null;
let session = null;

/* --- the sections -------------------------------------------------------- */

const SECTIONS = ['gate', 'noaccess', 'unconfigured', 'shell'];

function show(which) {
  for (const id of SECTIONS) $(id).hidden = id !== which;
  document.documentElement.dataset.view = which;
}

/* --- routing ------------------------------------------------------------- */

function setState(next, { replace = true } = {}) {
  state = next;
  const url = `${window.location.pathname}${toSearch(state)}`;
  if (replace) window.history.replaceState(null, '', url);
  else window.history.pushState(null, '', url);
  draw();
}

/* --- the shell ----------------------------------------------------------- */

/* A tab that is not in the registry yet renders a named placeholder rather than
   an empty <main> — there is no state of this page in which the view area is
   blank and unexplained. */

let drawToken = 0;

async function draw() {
  renderControls($('controls'), state, (next) => setState(next));
  renderTabs($('tabs'), state, (next) => setState(next, { replace: false }));

  const view = $('view');
  const render = TAB_RENDERERS[state.tab];
  const token = ++drawToken;

  /* Switching tabs empties the view first. A renderer awaits its data, and
     leaving the previous tab's numbers on screen under the new tab's name for
     those few hundred milliseconds is worse than an empty frame: it is the same
     figures labelled as something else. Changing a CONTROL does not clear —
     there the numbers on screen are still about the right thing, and a flash of
     blank on every click would be worse. */
  if (view.dataset.tab !== state.tab) {
    view.replaceChildren(loading(state.tab));
    view.dataset.tab = state.tab;
  }
  view.dataset.state = 'loading';

  if (!render) {
    view.replaceChildren(placeholder(state.tab));
    view.dataset.state = 'ready';
    return;
  }
  try {
    const window_ = await windowFor(state);
    await render(view, { state, window: window_, isCurrent: () => token === drawToken });
  } catch (err) {
    console.error(`${state.tab} tab failed`, err);
    if (token === drawToken) view.replaceChildren(panelError(state.tab, err));
  } finally {
    if (token === drawToken) view.dataset.state = 'ready';
  }
}

function loading(tab) {
  const p = document.createElement('section');
  p.className = 'a-panel';
  const h = document.createElement('header');
  h.appendChild(Object.assign(document.createElement('h2'), { textContent: TAB_NAME[tab] }));
  p.append(h, Object.assign(document.createElement('div'), { className: 'a-skel' }));
  return p;
}

function placeholder(tab) {
  const p = document.createElement('section');
  p.className = 'a-panel';
  p.innerHTML = `<header><h2>${TAB_NAME[tab]}</h2></header>`
    + '<p class="a-empty">Not built yet.</p>';
  return p;
}

function panelError(tab, err) {
  const p = document.createElement('section');
  p.className = 'a-panel';
  const h = document.createElement('header');
  h.innerHTML = `<h2>${TAB_NAME[tab]}</h2>`;
  const msg = document.createElement('p');
  msg.className = 'a-error';
  msg.textContent = `This tab could not be drawn: ${err?.message ?? err}`;
  p.append(h, msg);
  return p;
}

/* --- the gate ------------------------------------------------------------ */

function wireGate() {
  const form = $('gate-form');
  const msg = $('gate-msg');
  const send = $('gate-send');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    msg.textContent = '';
    msg.dataset.kind = '';
    send.disabled = true;
    send.textContent = 'Sending…';

    const result = await sendLink($('email').value);

    send.disabled = false;
    send.textContent = 'Email me a sign-in link';
    if (result.ok) {
      msg.dataset.kind = 'sent';
      /* Says nothing about whether the address is known. See supa.sendLink(). */
      msg.textContent = 'If that address has access, the link is on its way. '
        + 'Open it on this device.';
    } else {
      msg.dataset.kind = 'error';
      msg.textContent = result.reason;
    }
  });
}

/* --- freshness and access ------------------------------------------------ */

/**
 * The header's collector freshness.
 *
 * Three states, and the third is the one that matters: a run that FAILED is
 * failed whatever its age. An eight-minute-old failure is not fresher than a
 * two-hour-old success, and a green dot over a broken pipeline is the single
 * most expensive thing this header could do.
 */
async function drawFreshness() {
  const fresh = $('fresh');
  const text = $('fresh-text');
  const result = await lastRun();

  if (!result.ok) {
    fresh.dataset.state = 'failed';
    text.textContent = 'collector status unavailable';
    fresh.title = result.reason;
    return;
  }
  const { run, ageMs, stale, failed } = result.current;
  if (!run) {
    fresh.dataset.state = 'stale';
    text.textContent = 'no collector run recorded';
    return;
  }
  fresh.dataset.state = failed ? 'failed' : stale ? 'stale' : 'ok';
  const when = run.finishedAt ? bkkStamp(run.finishedAt.toISOString()) : 'unknown';
  text.textContent = failed
    ? `last run ${run.status} · ${ago(ageMs)}`
    : `collected ${ago(ageMs)}`;
  fresh.title = [
    `${when} Bangkok · ${run.status} · ${run.rowsWritten} rows`,
    'Stale after two hours; the collector runs hourly.',
  ].join('\n');
}

async function onSession(next) {
  session = next;

  if (!session) {
    show('gate');
    return;
  }

  $('who').textContent = sessionEmail(session);
  $('noaccess-email').textContent = sessionEmail(session);

  const permitted = await access();
  if (!permitted.ok) {
    /* Cannot tell allowed from unreachable, so say which one we cannot tell.
       Showing the dashboard and letting every panel fail separately would be
       six copies of the same message. */
    show('shell');
    $('view').replaceChildren(fatal('Could not reach the database', permitted.reason));
    $('fresh').dataset.state = 'failed';
    $('fresh-text').textContent = 'not reachable';
    return;
  }
  if (!permitted.current.allowed) {
    show('noaccess');
    return;
  }

  show('shell');
  drawFreshness();
  draw();
}

function fatal(title, detail) {
  const p = document.createElement('section');
  p.className = 'a-panel';
  const h = document.createElement('h2');
  h.textContent = title;
  const d = document.createElement('p');
  d.className = 'a-error';
  d.textContent = detail;
  const hint = document.createElement('p');
  hint.className = 'a-note';
  hint.textContent = 'Nothing has been lost — this page only reads. Reload once '
    + 'the connection is back.';
  p.append(h, d, hint);
  return p;
}

/* --- start --------------------------------------------------------------- */

function start() {
  wireGate();

  for (const b of document.querySelectorAll('[data-signout]')) {
    b.addEventListener('click', async () => {
      await signOut();
      clearCache();
      onSession(null);
    });
  }

  window.addEventListener('popstate', () => {
    state = readState();
    if (!$('shell').hidden) draw();
  });

  const problem = configProblem();
  if (problem) {
    $('unconfigured-why').textContent = problem;
    show('unconfigured');
    return;
  }

  show('gate');
  stopWatching = watchSession(onSession);
}

window.addEventListener('beforeunload', () => stopWatching?.());

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', start);
} else {
  start();
}

/* Exposed for the test harness only: the suite drives the page rather than
   poking at internals, but it needs a way to re-read state after a scripted
   history change. Nothing in the dashboard imports this. */
window.__analytics = {
  get state() { return state; },
  setState: (next) => setState(withChange(state, next)),
  redraw: draw,
};
