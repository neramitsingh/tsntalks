/* The artifact registry.
 *
 * There is no generic "export this view". Each artifact is a named thing that
 * goes to a named person for a named reason, and the UI renders the recipient
 * and the reason next to the button — the spec's whole point is that this is
 * true, and the dashboard should make it visible rather than merely satisfy it.
 *
 * The five are decided (2026-09-15). A sixth is an edit to a working dashboard
 * after Sunny has seen these, and it needs a recipient before it needs a design.
 */

import { lastRun } from '../data.js';
import { bkk, bkkStamp, PLATFORM_NAME, rangeLabel } from '../format.js';

/**
 * @typedef {object} Artifact
 * @property {string} id
 * @property {string} name
 * @property {string} recipient  who receives it — never "whoever clicked"
 * @property {string} why        when it is sent and what it is for
 * @property {string[]} formats
 * @property {'episode'|'posts'|'month'|'date'} scope  what it needs to be told
 * @property {string} [page]     the print-designed page, under artifacts/
 */

/** @type {Artifact[]} */
export const ARTIFACTS = [
  {
    id: 'episode-report',
    name: 'Episode report',
    recipient: 'the episode’s sponsor',
    why: 'After the episode airs, so the sponsor can see what they paid for.',
    formats: ['pdf'],
    scope: 'episode',
    page: 'episode-report.html',
  },
  {
    id: 'posts-table',
    name: 'Posts table',
    recipient: 'whoever asked for a spreadsheet',
    why: 'The Posts tab exactly as it is on screen — same rows, same sort, same filter.',
    formats: ['csv', 'xlsx'],
    scope: 'posts',
  },
  {
    id: 'monthly-review',
    name: 'Monthly review',
    recipient: 'Sunny and Thai Sikh News',
    why: 'Once a month: this month against last, by platform.',
    formats: ['pdf', 'xlsx'],
    scope: 'month',
    page: 'monthly-review.html',
  },
  {
    id: 'guest-card',
    name: 'Guest card',
    recipient: 'the guest',
    why: 'A week after their episode — what it reached, and something to share.',
    formats: ['pdf', 'png'],
    scope: 'episode',
    page: 'guest-card.html',
  },
  {
    id: 'numbers-today',
    name: 'Numbers as of today',
    recipient: 'a sponsor who asks for a deck',
    why: 'The live page’s figures frozen at a date, in the public layout.',
    formats: ['pdf'],
    scope: 'date',
    page: 'numbers-today.html',
  },
];

export const byId = (id) => ARTIFACTS.find((a) => a.id === id) ?? null;

export const forScope = (scope) => ARTIFACTS.filter((a) => a.scope === scope);

/* --- builders -------------------------------------------------------------- */

/* Each artifact module registers itself here. The metadata above ships whether
   or not the builder does, so a button can exist and say "not built yet" rather
   than a feature quietly not existing. */
const BUILDERS = new Map();

export function register(id, build) {
  if (!byId(id)) throw new Error(`artifacts: no artifact called "${id}"`);
  BUILDERS.set(id, build);
}

export const has = (id) => BUILDERS.has(id);

/**
 * Produce an artifact.
 * @returns {Promise<{ok: true} | {ok: false, reason: string}>}
 */
export async function run(id, params = {}) {
  const artifact = byId(id);
  if (!artifact) return { ok: false, reason: `No artifact called "${id}".` };
  const build = BUILDERS.get(id);
  if (!build) {
    return { ok: false, reason: `${artifact.name} is not built yet.` };
  }
  try {
    await build({ ...params, artifact });
    return { ok: true };
  } catch (err) {
    return { ok: false, reason: String(err?.message ?? err) };
  }
}

/* --- filenames ------------------------------------------------------------- */

/**
 * `tsn-episode-report-s2e10-2026-09-15.pdf`
 *
 * Artifact, subject, date — in that order, so a folder of them sorts by kind
 * and then by subject, which is how someone looking for "the report we sent
 * Spark.love" actually looks.
 */
export function filename(id, subject, extension, date = new Date()) {
  const slug = (s) => String(s ?? '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/[\s_]+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 48)
    .replace(/^-|-$/g, '');
  const stamp = new Date(date).toLocaleDateString('en-CA', { timeZone: 'Asia/Bangkok' });
  return ['tsn', slug(id), slug(subject), stamp].filter(Boolean).join('-') + `.${extension}`;
}

/** `s2e10` — the subject slug for anything scoped to an episode. */
export const episodeSlug = (episode) =>
  `s${episode.season}e${String(episode.number).replace(/\D/g, '') || episode.number}`;

/* --- the source note ------------------------------------------------------- */

/**
 * The paragraph every artifact carries.
 *
 * Which platforms, which window, and which collector run it was built from. An
 * artifact without this is a number with no provenance, and the whole point of
 * replacing the hand-typed media kit was that a sponsor should never have to
 * ask "as of when?".
 */
export async function sourceNote({ platforms = 'all', from, to, lifetime = false } = {}) {
  const where = platforms === 'all'
    ? 'YouTube, Instagram and TikTok'
    : PLATFORM_NAME[platforms] ?? platforms;

  const when = lifetime
    ? 'Lifetime totals, not a window.'
    : (from && to ? `Window: ${rangeLabel(from, to)}, Bangkok time.` : '');

  const run = await lastRun();
  const built = run.ok && run.current.run?.finishedAt
    ? `Built from the collector run that finished ${
      bkkStamp(run.current.run.finishedAt.toISOString())} Bangkok (${
      run.current.run.status}).`
    : 'Built without a recorded collector run — the figures may be stale.';

  return [
    `Source: ${where}, collected automatically through Zernio and the YouTube Data API.`,
    when,
    built,
    `Produced ${bkk(new Date().toISOString())}. Nothing on this page was typed by hand.`,
  ].filter(Boolean).join(' ');
}

/* --- print pages ----------------------------------------------------------- */

/**
 * Open an artifact's print-designed page with its parameters in the query
 * string.
 *
 * A new tab, not an iframe and not this document: the artifact stylesheet is
 * A4 and ink-safe, and loading it over the dashboard would repaint the
 * dashboard. The page carries the session because it is the same origin.
 */
export function openPage(artifact, params) {
  const url = new URL(`./artifacts/${artifact.page}`, pageBase());
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== '') url.searchParams.set(k, String(v));
  }
  const win = window.open(url.href, '_blank', 'noopener');
  if (!win) {
    throw new Error('The browser blocked the pop-up. Allow pop-ups for this site '
      + 'and try again — the artifact opens in its own tab so it can print.');
  }
  return win;
}

/* /analytics/ whether the dashboard is served from a folder or a file. */
function pageBase() {
  const path = window.location.pathname.replace(/[^/]*$/, '');
  return new URL(path, window.location.origin).href;
}

/* --- the UI ---------------------------------------------------------------- */

/**
 * A button and, beside it, who it is for and why.
 *
 * The recipient is not a tooltip. It is next to the label, always, because the
 * difference between this dashboard and a generic export menu is exactly that
 * sentence.
 */
export function artifactButton(artifact, getParams, { onDone } = {}) {
  const wrap = document.createElement('div');
  wrap.className = 'a-artifact';

  const buttons = document.createElement('div');
  buttons.className = 'a-artifact-buttons';

  /* One button per format, not a dropdown. Two formats is two clicks' worth of
     choice, and a select that has to be opened to discover that XLSX exists is
     a worse answer than two buttons. */
  for (const format of artifact.formats) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'a-btn primary';
    button.textContent = artifact.formats.length > 1
      ? `${artifact.name} · ${format.toUpperCase()}`
      : artifact.name;
    button.dataset.artifact = artifact.id;
    button.dataset.format = format;

    if (!has(artifact.id)) {
      button.disabled = true;
      button.title = 'Not built yet — this artifact lands in a later commit.';
    } else {
      button.addEventListener('click', async () => {
        const label = button.textContent;
        button.disabled = true;
        button.textContent = 'Producing…';
        const result = await run(artifact.id, { ...getParams(), format });
        button.disabled = false;
        button.textContent = label;
        wrap.querySelector('.a-error')?.remove();
        if (!result.ok) {
          const err = document.createElement('p');
          err.className = 'a-error';
          err.textContent = result.reason;
          wrap.appendChild(err);
        }
        onDone?.(result);
      });
    }
    buttons.appendChild(button);
  }

  const meta = document.createElement('div');
  meta.className = 'a-artifact-meta';
  const to = document.createElement('span');
  to.className = 'a-recipient';
  to.textContent = `to ${artifact.recipient}`;
  const why = document.createElement('span');
  why.className = 'a-why';
  why.textContent = artifact.why;
  meta.append(to, why);

  wrap.append(buttons, meta);
  return wrap;
}

/** A row of artifact buttons, for a tab that offers more than one. */
export function artifactBar(artifacts, getParams) {
  const bar = document.createElement('div');
  bar.className = 'a-artifacts';
  for (const a of artifacts) bar.appendChild(artifactButton(a, getParams));
  return bar;
}
