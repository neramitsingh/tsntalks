/* The privacy page. Only the nav button follows the reply channel; the mail
   links in the text stay email, because a privacy request needs an address. */
import { wireContact } from './contact.js';

wireContact({ nav: 'navcta', base: import.meta.url });
