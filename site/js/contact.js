/* The reply channel.
   The sponsor arrived from a LINE thread; a mail link inside LINE's in-app
   browser is where the journey used to end. site/data/contact.json carries the
   email and, once Sunny sends it, his LINE link. With a LINE link present every
   primary button becomes "Message us on LINE" and email steps back; without one
   the static mailto: in the markup stands, so the page works with the script
   off and before the file is ever edited. Home and the rate card share this so
   the two pages cannot disagree about where a reply goes. */

export async function wireContact({ buttons = [], nav = null, base } = {}) {
  try {
    const r = await fetch(new URL('../data/contact.json', base).href, { cache: 'force-cache' });
    if (!r.ok) return null;
    const c = await r.json();
    const mail = `mailto:${c.email}?subject=${encodeURIComponent('TSN Talks sponsorship')}`;
    for (const id of buttons) {
      const a = document.getElementById(id);
      if (!a) continue;
      if (c.line) {
        a.href = c.line;
        a.textContent = 'Message us on LINE';
        a.classList.add('line');
        a.target = '_blank';
        a.rel = 'noopener';
      } else {
        a.href = mail;
      }
    }
    if (nav && c.line) {
      const n = document.getElementById(nav);
      if (n) {
        n.href = c.line; n.textContent = 'LINE'; n.classList.add('line'); n.target = '_blank'; n.rel = 'noopener';
      }
    }
    return c;
  } catch {
    return null;                      // the static mailto stays
  }
}
