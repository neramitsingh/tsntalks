/* Health — "is the pipeline alive?"
 *
 * The thresholds are written on screen, in words, next to the colours. A green
 * dot that means "under two hours" only means that to the person who wrote it;
 * to everyone else it means "fine", which is not a measurement. Colour is the
 * second channel here, never the first — every state also carries its label.
 */

import {
  runs, lastRun, accountHealth, rowCounts, platformFreshness, accounts, STALE_AFTER_MS,
} from '../data.js';
import {
  windowSub, resultPanel, table, full, el, PLATFORM_NAME,
} from './shared.js';
import { ago, bkkStamp, duration } from '../format.js';

/* The one place these live. Both the copy on screen and the dot colours read
   from here, so they cannot drift apart. */
const AMBER_AFTER_MS = 6 * 60 * 60 * 1000;

const THRESHOLDS = 'Green under 2 hours, amber under 6, red beyond that — '
  + 'the collector runs hourly, so two hours means a run was missed.';

function state(ageMs, { failed = false } = {}) {
  if (failed) return 'bad';
  if (ageMs == null) return 'bad';
  if (ageMs <= STALE_AFTER_MS) return 'ok';
  if (ageMs <= AMBER_AFTER_MS) return 'warn';
  return 'bad';
}

const LABEL = { ok: 'Healthy', warn: 'Late', bad: 'Stale or failed' };

/** A coloured dot that also says the word. Never colour alone. */
function pill(kind, text) {
  const span = el('span', 'a-pill');
  span.dataset.state = kind;
  span.append(el('i'), document.createTextNode(text));
  return span;
}

export async function health(mount, { window: w }) {
  const [last, recent, accountRows, freshness, counts, accountList] = await Promise.all([
    lastRun(), runs(20), accountHealth(), platformFreshness(), rowCounts(), accounts(),
  ]);

  mount.replaceChildren(
    collectorPanel(last, w),
    freshnessPanel(freshness, w),
    accountsPanel(accountRows, accountList, w),
    runsPanel(recent, w),
    countsPanel(counts, w),
  );
}

/* --- the collector --------------------------------------------------------- */

function collectorPanel(result, w) {
  return resultPanel(result, {
    title: 'The collector',
    sub: windowSub('Last run', w.from, w.to, THRESHOLDS),
    emptyMessage: 'No collector run has ever been recorded.',
  }, (section, { current }) => {
    const { run, ageMs, failed } = current;
    if (!run) return false;

    const kind = state(ageMs, { failed });
    const row = el('div', 'a-figrow');

    const box = el('div', 'a-fig');
    box.appendChild(el('span', 'k', 'Status'));
    box.appendChild(pill(kind, failed ? `Last run ${run.status}` : LABEL[kind]));
    box.appendChild(el('span', 'since', `${ago(ageMs)} · ${
      run.finishedAt ? bkkStamp(run.finishedAt.toISOString()) : 'never finished'} Bangkok`));
    row.appendChild(box);

    const written = el('div', 'a-fig');
    written.appendChild(el('span', 'k', 'Rows written'));
    written.appendChild(el('span', 'n', full(run.rowsWritten)));
    row.appendChild(written);

    const took = el('div', 'a-fig');
    took.appendChild(el('span', 'k', 'Run took'));
    took.appendChild(el('span', 'n', run.finishedAt && run.startedAt
      ? duration((run.finishedAt - run.startedAt) / 1000) : '—'));
    row.appendChild(took);

    section.appendChild(row);

    const notes = describeNotes(run.notes);
    if (notes) section.appendChild(el('p', 'a-error', notes));

    /* Stated, not implied by a colour. A reader who is not the person who wrote
       this page has no way to know what "green" was measured against. */
    section.appendChild(el('p', 'a-note', THRESHOLDS));
    return true;
  });
}

function describeNotes(notes) {
  if (!notes || typeof notes !== 'object' || !Object.keys(notes).length) return '';
  const failed = Array.isArray(notes.failed) ? notes.failed.join(', ') : notes.failed;
  const reason = notes.reason ? ` — ${notes.reason}` : '';
  if (failed) return `Failed steps: ${failed}${reason}`;
  return JSON.stringify(notes);
}

/* --- freshness per platform ------------------------------------------------ */

/**
 * When each platform last produced data.
 *
 * A separate question from "did the collector run". The run can finish `ok`
 * with one account's token expired and no snapshot written for a day, and a
 * green header would hide exactly that.
 */
function freshnessPanel(result, w) {
  return resultPanel(result, {
    title: 'Freshness per platform',
    sub: windowSub('Newest account snapshot', w.from, w.to, THRESHOLDS),
    emptyMessage: 'No account snapshots at all.',
  }, (section, { current }) => {
    if (!current.rows.length) return false;
    section.appendChild(table([
      { name: 'Platform', value: (r) => el('span', null, PLATFORM_NAME[r.platform] ?? r.platform) },
      { name: 'Account', key: 'handle' },
      { name: 'State', value: (r) => pill(state(r.ageMs), LABEL[state(r.ageMs)]) },
      { name: 'Last snapshot', value: (r) => el('span', null,
        r.lastSeen ? `${bkkStamp(r.lastSeen.toISOString())} Bangkok` : 'never') },
      { name: 'Age', value: (r) => el('span', null, r.ageMs == null ? 'never' : ago(r.ageMs)) },
    ], current.rows));
    section.appendChild(el('p', 'a-note',
      'A run can finish "ok" while one platform is silent — an expired token stops '
      + 'that account without stopping the others. This table is the one that '
      + 'notices.'));
    return true;
  });
}

/* --- accounts -------------------------------------------------------------- */

function accountsPanel(result, accountList, w) {
  return resultPanel(result, {
    title: 'Accounts',
    sub: windowSub('Latest health check per account', w.from, w.to, THRESHOLDS),
    emptyMessage: 'No health checks recorded.',
  }, (section, { current }) => {
    if (!current.rows.length) return false;
    const handles = {};
    if (accountList?.ok) for (const a of accountList.current.rows) handles[a.id] = a.handle;

    section.appendChild(table([
      { name: 'Platform', value: (r) => el('span', null, PLATFORM_NAME[r.platform] ?? r.platform) },
      { name: 'Account', value: (r) => el('span', null, handles[r.accountId] ?? r.accountId) },
      { name: 'State', value: (r) => pill(
        r.needsReconnect ? 'bad' : state(r.ageMs), r.needsReconnect ? 'Reconnect needed'
          : (r.status || LABEL[state(r.ageMs)])) },
      { name: 'Analytics', value: (r) => el('span', null,
        r.canFetchAnalytics === false ? 'no' : r.canFetchAnalytics === true ? 'yes' : '—') },
      { name: 'Token expires', value: (r) => el('span', null,
        r.tokenExpiresAt ? bkkStamp(r.tokenExpiresAt.toISOString()) : 'no expiry reported') },
      { name: 'Checked', value: (r) => el('span', null, r.ageMs == null ? '—' : ago(r.ageMs)) },
    ], current.rows));

    const reconnect = current.rows.filter((r) => r.needsReconnect);
    if (reconnect.length) {
      section.appendChild(el('p', 'a-error',
        `${reconnect.map((r) => PLATFORM_NAME[r.platform] ?? r.accountId).join(', ')} `
        + 'needs reconnecting in Zernio. TikTok tokens expire; YouTube refreshes '
        + 'itself. Until it is reconnected that platform stops producing data and '
        + 'every figure that includes it is short.'));
    }
    return true;
  });
}

/* --- recent runs ----------------------------------------------------------- */

function runsPanel(result, w) {
  return resultPanel(result, {
    title: 'Recent runs',
    sub: windowSub('The last 20, newest first', w.from, w.to),
    emptyMessage: 'No runs recorded.',
  }, (section, { current }) => {
    if (!current.rows.length) return false;
    section.appendChild(table([
      { name: 'Finished', value: (r) => el('span', null,
        r.finishedAt ? bkkStamp(r.finishedAt.toISOString()) : 'unfinished') },
      /* An unknown status renders amber with the literal string shown, so a
         fourth value the collector starts writing surfaces instead of quietly
         reading as green. */
      { name: 'Status', value: (r) => pill(
        r.status === 'ok' ? 'ok' : r.status === 'failed' ? 'bad' : 'warn', r.status) },
      { name: 'Rows', key: 'rowsWritten', num: true, format: full },
      { name: 'Took', value: (r) => el('span', null,
        r.finishedAt && r.startedAt ? duration((r.finishedAt - r.startedAt) / 1000) : '—') },
      { name: 'Notes', wide: true, value: (r) => el('span', null, describeNotes(r.notes) || '—') },
    ], current.rows));
    return true;
  });
}

/* --- row counts ------------------------------------------------------------ */

function countsPanel(result, w) {
  return resultPanel(result, {
    title: 'Row counts',
    sub: windowSub('Every table the dashboard reads', w.from, w.to),
    emptyMessage: 'Could not count any table.',
  }, (section, { current }) => {
    const rows = Object.entries(current.counts).map(([name, count]) => ({ name, count }));
    if (!rows.length) return false;
    section.appendChild(table([
      { name: 'Table', key: 'name' },
      /* null is "we could not count", not "there is nothing there". The table
         renders null as an em dash and the two stay distinguishable. */
      { name: 'Rows', key: 'count', num: true, format: full },
    ], rows));
    section.appendChild(el('p', 'a-note',
      'A dash means the count could not be read, which is not the same as zero. '
      + 'Counts come from PostgREST’s Content-Range header, so they are exact '
      + 'rather than estimated.'));
    return true;
  });
}
