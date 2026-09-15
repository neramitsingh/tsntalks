/* Shared boot for the print-designed artifact pages.
 *
 * Each of those pages is a real page at a real URL: you can bookmark it, send
 * the link to someone who also has access, and reload it. It is not a modal
 * over the dashboard, because the dashboard is dark and A4 is not, and because
 * a print dialog over a modal prints the modal.
 *
 * The session comes from localStorage on the same origin, so a page opened from
 * the dashboard is already signed in. Opened cold, it says so rather than
 * failing at the first fetch. */

import { configProblem, currentSession, sessionEmail } from '../supa.js';
import { sourceNote } from './index.js';

const el = (name, className, text) => {
  const node = document.createElement(name);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
};

export { el };

/** The page's own query string, as a plain object. */
export const params = () => Object.fromEntries(new URLSearchParams(window.location.search));

/**
 * Boot an artifact page.
 *
 * @param {object} spec
 * @param {string} spec.title        what to call it in the toolbar and the title
 * @param {(root: HTMLElement, params: object) => Promise<{filename?: string}>} spec.render
 * @param {boolean} [spec.autoPrint] open the print dialog once it has drawn
 */
export async function startArtifact(spec) {
  const root = document.getElementById('sheet');
  const toolbar = document.getElementById('toolbar');
  const status = document.getElementById('status');

  const problem = configProblem();
  if (problem) {
    status.textContent = problem;
    status.className = 'problem';
    return;
  }

  const session = await currentSession();
  if (!session) {
    status.className = 'problem';
    status.replaceChildren(
      document.createTextNode('Not signed in. Open the dashboard, sign in, and '
        + 'produce this from there — '),
    );
    const link = el('a', null, 'go to the dashboard');
    link.href = '../';
    status.appendChild(link);
    return;
  }
  status.textContent = `Signed in as ${sessionEmail(session)}`;

  try {
    const result = await spec.render(root, params());
    /* The browser's print-to-PDF names the file from document.title, so the
       title IS the filename. Setting it after the render means it can carry the
       subject — "tsn-episode-report-s2e10-2026-09-15". */
    if (result?.filename) document.title = result.filename.replace(/\.pdf$/, '');
    wirePrint(toolbar, result?.filename);
  } catch (err) {
    console.error('artifact failed', err);
    root.replaceChildren(el('p', 'problem',
      `This artifact could not be built: ${err?.message ?? err}`));
  }
}

function wirePrint(toolbar, filename) {
  const button = toolbar.querySelector('[data-print]');
  if (!button) return;
  button.disabled = false;
  button.addEventListener('click', () => window.print());
  const hint = toolbar.querySelector('[data-hint]');
  if (hint) {
    hint.textContent = filename
      ? `Print to PDF and save it as ${filename}. A4 portrait, margins default.`
      : 'Print to PDF. A4 portrait, margins default.';
  }
}

/**
 * The masthead every printed artifact carries.
 *
 * Antonio, because this is the brand leaving the building with the show's name
 * on it — the opposite of the dashboard's register, and deliberately so.
 */
export function masthead(kind, when) {
  const head = el('header', 'masthead');
  const mark = el('span', 'mark');
  mark.append(document.createTextNode('TSN '), el('em', null, 'Talks'));
  head.append(mark, el('span', 'eyebrow', kind), el('span', 'spacer'),
              el('span', 'when', when));
  return head;
}

/**
 * The source note, at the foot of every artifact.
 *
 * Which platforms, which window, which collector run. The whole point of
 * replacing the hand-typed media kit was that nobody should have to ask "as of
 * when?", and this paragraph is where that promise is kept on paper.
 */
export async function colophon(options, extra = []) {
  const foot = el('footer', 'colophon');
  foot.appendChild(el('p', null, await sourceNote(options)));
  for (const line of extra) foot.appendChild(el('p', null, line));
  return foot;
}

/** A labelled figure, print-side. */
export function fig(label, value, sub) {
  const box = el('div', 'fig');
  box.appendChild(el('span', 'k', label));
  box.appendChild(el('span', 'n', value));
  if (sub) box.appendChild(el('span', 'sub', sub));
  return box;
}

/** A table, print-side. Same column descriptors the dashboard uses. */
export function printTable(columns, rows) {
  const table = el('table');
  const thead = el('thead');
  const hr = el('tr');
  for (const c of columns) hr.appendChild(el('th', c.num ? 'num' : '', c.name));
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = el('tbody');
  for (const row of rows) {
    const tr = el('tr');
    for (const c of columns) {
      const td = el('td', c.num ? 'num' : '');
      const raw = c.value ? c.value(row) : row[c.key];
      if (raw == null) {
        td.textContent = c.missing ?? '—';
        td.classList.add('none');
      } else if (raw instanceof Node) {
        td.appendChild(raw);
      } else {
        td.textContent = c.format ? c.format(raw) : String(raw);
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

/**
 * A proportion bar with its numbers written underneath.
 *
 * On paper the colours flatten to three similar greys in a monochrome print, so
 * the legend carries the figure in text — which PRODUCT.md asks for anyway:
 * numbers are never only a bar length.
 */
export function proportionBar(parts, format) {
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  const wrap = el('div');
  const band = el('div', 'band');
  for (const part of parts) {
    if (!part.value) continue;
    const i = el('i');
    i.style.width = `${(part.value / total) * 100}%`;
    i.dataset.platform = part.id;
    band.appendChild(i);
  }
  const legend = el('div', 'band-legend');
  for (const part of parts) {
    const span = el('span');
    const swatch = el('i');
    swatch.dataset.platform = part.id;
    span.append(swatch, document.createTextNode(
      `${part.name} ${format(part.value)} · ${Math.round((part.value / total) * 100)}%`));
    legend.appendChild(span);
  }
  wrap.append(band, legend);
  return wrap;
}
