/* The Supabase client, and the whole of auth.
   Nothing else in the dashboard touches `window.supabase` or a session. */

export const SUPABASE_URL = 'https://xygppcxxfggydlwgoadw.supabase.co';

/* TODO(nav): paste the anon key here.
   It is on Nav's machine in ~/.secrets/secrets.md, TSN Talks section, as
   "anon key". The worktree that wrote this page had no access to it, by
   design — a headless agent with skipped permissions should not hold keys.

   The anon key is PUBLIC and belongs in this file as a literal. It is safe
   because db/002_rls.sql gives anonymous users nothing on any table and
   db/004_analytics.sql revokes execute on every function from public and anon.
   Publishing it grants exactly the ability to attempt a sign-in.

   The SERVICE-ROLE key must never appear anywhere under site/. It bypasses
   RLS entirely. tests/analytics/test_auth.py asserts that it does not.

   Until this is filled in the page shows a named "not configured" panel rather
   than a login form that cannot work. */
export const SUPABASE_ANON_KEY = '';

/* Every table the dashboard reads. Used by the Health tab's row counts, and by
   the access probe, so it lives with the client rather than in a tab. */
export const TABLES = [
  'accounts', 'account_snapshots', 'posts', 'post_snapshots',
  'metric_daily', 'demographics', 'episodes', 'collector_runs', 'account_health',
];

let client = null;

/** Why the client cannot be built, or null if it can. */
export function configProblem() {
  if (!SUPABASE_ANON_KEY) {
    return 'The Supabase anon key is missing from site/js/analytics/supa.js.';
  }
  if (!globalThis.supabase?.createClient) {
    return 'The Supabase client library did not load. Check the cdnjs script tag '
         + 'in site/analytics/index.html, and whether the network allows cdnjs.';
  }
  return null;
}

/**
 * The one client. Throws only if you call it without checking configProblem()
 * first — every caller in the dashboard checks.
 */
export function sb() {
  if (client) return client;
  const problem = configProblem();
  if (problem) throw new Error(problem);
  client = globalThis.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      /* The magic link lands back on this page with the session in the URL
         fragment; supabase-js reads it, stores it and strips it. */
      detectSessionInUrl: true,
      persistSession: true,
      autoRefreshToken: true,
    },
  });
  return client;
}

/**
 * Send a magic link.
 *
 * Supabase does not say whether the address is known, and it should not — that
 * would make the login form an email-enumeration oracle. So a success here means
 * "a link was sent if that address exists", not "you have access". Access is
 * enforced after sign-in, by RLS returning nothing.
 *
 * @returns {Promise<{ok: true} | {ok: false, reason: string}>}
 */
export async function sendLink(email) {
  const address = String(email || '').trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address)) {
    return { ok: false, reason: 'That does not look like an email address.' };
  }
  try {
    const { error } = await sb().auth.signInWithOtp({
      email: address,
      options: { emailRedirectTo: window.location.href.split('#')[0] },
    });
    if (error) return { ok: false, reason: friendly(error) };
    return { ok: true };
  } catch (err) {
    return { ok: false, reason: friendly(err) };
  }
}

export async function signOut() {
  try {
    await sb().auth.signOut();
  } catch (err) {
    console.warn('sign out failed', err);      // the UI resets regardless
  }
}

/** The current session, or null. Never throws. */
export async function currentSession() {
  try {
    const { data } = await sb().auth.getSession();
    return data?.session ?? null;
  } catch {
    return null;
  }
}

/**
 * Call `onChange(session | null)` now and on every later auth change.
 * @returns {() => void} unsubscribe
 */
export function watchSession(onChange) {
  const c = sb();
  let stopped = false;
  const { data } = c.auth.onAuthStateChange((_event, session) => {
    if (!stopped) onChange(session ?? null);
  });
  /* onAuthStateChange fires INITIAL_SESSION in supabase-js v2, but not in every
     patch release and not before the library has finished reading the URL
     fragment. Asking once directly is cheap and removes the timing question. */
  currentSession().then((s) => { if (!stopped) onChange(s); });
  return () => {
    stopped = true;
    data?.subscription?.unsubscribe?.();
  };
}

export function sessionEmail(session) {
  return session?.user?.email ?? '';
}

/* Supabase error objects are not written for people. These are the ones a user
   of this page can actually hit. */
export function friendly(error) {
  const msg = String(error?.message ?? error ?? '').toLowerCase();
  if (msg.includes('rate limit') || msg.includes('too many')) {
    return 'Too many sign-in attempts. Wait a minute and try again.';
  }
  if (msg.includes('failed to fetch') || msg.includes('networkerror')) {
    return 'Could not reach the database. Check the connection and try again.';
  }
  if (msg.includes('jwt') || msg.includes('expired')) {
    return 'That session has expired. Sign in again.';
  }
  return error?.message || 'Something went wrong talking to the database.';
}
