/* Which artifacts actually exist.
 *
 * Kept apart from index.js so the registry has no import cycle: index.js knows
 * the five artifacts and their recipients, this file knows how to produce the
 * ones that have been built, and the buttons for the rest stay disabled with a
 * reason rather than absent.
 *
 * app.js imports this once, for the side effect. */

import { register, byId, openPage } from './index.js';

/** A print-designed page, opened in its own tab. */
const printPage = (id, params) => {
  const artifact = byId(id);
  return openPage(artifact, params);
};

register('episode-report', ({ episode }) => {
  if (!episode) throw new Error('No episode was chosen.');
  printPage('episode-report', { episode: episode.episodeId });
});
