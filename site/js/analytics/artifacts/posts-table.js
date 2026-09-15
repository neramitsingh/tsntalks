/* The posts table, as CSV and as XLSX.
 *
 * To whoever asked for a spreadsheet. It is THE TAB'S CURRENT VIEW — the rows
 * that are on screen, in the order they are on screen, after whatever filter is
 * in the box. Someone who has narrowed the table to one guest's clips and then
 * hits Export expects that file. Producing a fresh unsorted query instead would
 * be technically the same data and practically the wrong answer.
 *
 * The one place the file differs from the screen is precision: the screen shows
 * "69.9K" and "6.5%", the sheet gets 69900 and 0.065. A spreadsheet is for
 * arithmetic.
 */

import { downloadCsv, downloadXlsx } from './csv.js';
import { filename, sourceNote } from './index.js';
import { PLATFORM_NAME, rangeLabel } from '../format.js';

/** What the file is called: the platform, and whether a filter was applied. */
function subject(view) {
  const where = view.platform === 'all' ? 'all-platforms' : view.platform;
  return view.search.trim() ? `${where}-filtered` : where;
}

/**
 * The provenance sheet.
 *
 * A CSV cannot carry one, so the XLSX does — and the CSV's absence is why the
 * filename carries the date. Every artifact says where its numbers came from;
 * for a spreadsheet, "where" includes the sort and the filter that produced it,
 * because those are what make it this file rather than a different one.
 */
async function aboutRows(view) {
  const lines = [
    ['Artifact', 'TSN Talks — posts table'],
    ['Produced', new Date()],
    ['Window', view.window ? rangeLabel(view.window.from, view.window.to) : 'unknown'],
    ['Platform filter', view.platform === 'all' ? 'all three' : PLATFORM_NAME[view.platform]],
    ['Title filter', view.search.trim() || 'none'],
    ['Sorted by', `${view.sort.key}, ${view.sort.dir === 'asc' ? 'ascending' : 'descending'}`],
    ['Rows', view.rows.length],
    ['Note', 'Views gained is the change inside the window. Every other figure '
      + 'is lifetime as at the end of the window.'],
    ['Note', 'Reach is reported by Instagram only. An empty cell means the '
      + 'platform does not publish it, not that it was zero.'],
    ['Source', await sourceNote({
      platforms: view.platform,
      from: view.window?.from,
      to: view.window?.to,
    })],
  ];
  return lines.map(([field, value]) => ({ field, value }));
}

const ABOUT_COLUMNS = [
  { name: 'Field', raw: (r) => r.field },
  { name: 'Value', raw: (r) => r.value },
];

export async function buildPostsTable({ view, columns, format }) {
  if (!view?.rows?.length) {
    throw new Error('There are no rows to export. Widen the window or clear the filter.');
  }
  const name = filename('posts-table', subject(view), format === 'xlsx' ? 'xlsx' : 'csv');

  if (format === 'xlsx') {
    await downloadXlsx([
      { name: 'Posts', columns, rows: view.rows },
      { name: 'About', columns: ABOUT_COLUMNS, rows: await aboutRows(view) },
    ], name);
    return;
  }
  downloadCsv(columns, view.rows, name);
}
