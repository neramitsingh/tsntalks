/* The tab registry. app.js renders whichever of these matches the tab control;
   a tab that is not here yet draws a named placeholder rather than nothing. */

import { overview } from './overview.js';
import { postsTab } from './posts.js';

export const TAB_RENDERERS = {
  overview,
  posts: postsTab,
};
