/* The rate card carries no live numbers on purpose: prices are editorial, and
   the page must read the same with this script off. The one thing it wires is
   the reply channel, shared with home. */
import { wireContact } from './contact.js';

wireContact({ buttons: ['cta', 'cta2'], nav: 'navcta', base: import.meta.url });
