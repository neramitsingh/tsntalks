/* Which artifacts actually exist.
 *
 * Kept apart from index.js so the registry has no import cycle: index.js knows
 * the five artifacts and their recipients, this file knows how to produce the
 * ones that have been built, and the buttons for the rest stay disabled with a
 * reason rather than absent.
 *
 * app.js imports this once, for the side effect. */

import { register, byId, openPage, filename, sourceNote } from './index.js';
import { buildPostsTable } from './posts-table.js';
import { downloadXlsx } from './csv.js';
import { gatherMonth, monthKey, workbookSheets } from './monthly-review-data.js';

/** A print-designed page, opened in its own tab. */
const printPage = (id, params) => {
  const artifact = byId(id);
  return openPage(artifact, params);
};

register('episode-report', ({ episode }) => {
  if (!episode) throw new Error('No episode was chosen.');
  printPage('episode-report', { episode: episode.episodeId });
});

register('posts-table', buildPostsTable);

/* Two formats, one set of numbers. The PDF is a page, the XLSX is the tables
   underneath it, and both come out of monthly-review-data.js so that printing
   the review and opening the spreadsheet beside it cannot show two answers. */
register('monthly-review', async ({ window: w, format }) => {
  const key = monthKey(w?.to ?? new Date());
  if (format === 'xlsx') {
    const data = await gatherMonth(key);
    const note = await sourceNote({
      platforms: 'all',
      from: data.windows.current.from,
      to: data.windows.current.to,
    });
    await downloadXlsx(workbookSheets(data, note), filename('monthly-review', key, 'xlsx'));
    return;
  }
  printPage('monthly-review', { month: key });
});
