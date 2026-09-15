/* Boot. Swaps the gate for the shell, owns the control state, and hands the
   active tab a context to render into.

   The only module that touches the page's top-level sections. Tabs get a mount
   element and a context; they never look for `#shell` or a session. */

import {
  configProblem, sendLink, signOut, watchSession, sessionEmail, sb,
} from './supa.js';
import {
  readState, toSearch, withChange, renderControls, renderTabs, TAB_NAME,
} from './controls.js';

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

/* Tabs register themselves here. Task 3 ships the shell; tasks 6 to 11 fill the
   six entries in. A tab that has not been built yet renders a named placeholder
   rather than an empty <main> — there is no state of this page in which the
   view area is blank and unexplained. */
export const TAB_RENDERERS = {};

let drawToken = 0;

async function draw() {
  renderControls($('controls'), state, (next) => setState(next));
  renderTabs($('tabs'), state, (next) => setState(next, { replace: false }));

  const view = $('view');
  const render = TAB_RENDERERS[state.tab];
  const token = ++drawToken;

  if (!render) {
    view.replaceChildren(placeholder(state.tab));
    return;
  }
  try {
    await render(view, { state, isCurrent: () => token === drawToken });
  } catch (err) {
    /* A renderer that throws is a bug, but it must not leave the dashboard
       showing the previous tab's numbers under this tab's name. */
    console.error(`${state.tab} tab failed`, err);
    if (token === drawToken) view.replaceChildren(panelError(state.tab, err));
  }
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

/* --- access -------------------------------------------------------------- */

/**
 * Signed in is not the same as allowed. Supabase will authenticate any address
 * it has a user for; `allowed_users` is what RLS checks. One row back means
 * allowed, zero rows means authenticated-but-not-allowed, and an error means a
 * transport problem that should not be reported as a permissions one.
 */
async function isAllowed() {
  try {
    const { data, error } = await sb().from('allowed_users').select('email').limit(1);
    if (error) return { ok: false, reason: error.message };
    return { ok: true, allowed: (data?.length ?? 0) > 0 };
  } catch (err) {
    return { ok: false, reason: String(err?.message ?? err) };
  }
}

async function onSession(next) {
  session = next;

  if (!session) {
    show('gate');
    return;
  }

  $('who').textContent = sessionEmail(session);
  $('noaccess-email').textContent = sessionEmail(session);

  const access = await isAllowed();
  if (!access.ok) {
    /* Cannot tell allowed from unreachable, so say which one we cannot tell.
       Showing the dashboard and letting every panel fail separately would be
       six copies of the same message. */
    show('shell');
    $('view').replaceChildren(fatal('Could not reach the database', access.reason));
    $('fresh').dataset.state = 'failed';
    $('fresh-text').textContent = 'not reachable';
    return;
  }
  if (!access.allowed) {
    show('noaccess');
    return;
  }

  show('shell');
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
