/* The tab registry. app.js renders whichever of these matches the tab control. */

import { overview } from './overview.js';
import { postsTab } from './posts.js';
import { growth } from './growth.js';
import { episodesTab } from './episodes.js';
import { audienceTab } from './audience.js';
import { health } from './health.js';

export const TAB_RENDERERS = {
  overview,
  growth,
  posts: postsTab,
  episodes: episodesTab,
  audience: audienceTab,
  health,
};
