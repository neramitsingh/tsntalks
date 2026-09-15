/* A stand-in for @supabase/supabase-js v2 (UMD), served to the page under test
   in place of the cdnjs script.
 *
 * WHY THIS EXISTS. The dashboard was built in a worktree with no credentials
 * and no network path to Supabase, so the suite cannot talk to a real project.
 * It could not fetch the real UMD bundle either. What it can do is stub the
 * HTTP underneath — which is plain PostgREST and GoTrue — and this shim is the
 * thinnest thing that turns the supabase-js calls the dashboard makes into
 * those requests.
 *
 * WHAT THAT MEANS FOR THE TESTS. Everything below the shim is real: the
 * dashboard's own code, real `fetch`, real URLs, and `page.route` answering
 * with the fixtures. What is NOT tested is supabase-js itself — token refresh,
 * PKCE, and reading the magic-link fragment out of the URL. Those are the
 * library's job and they are on Nav's live-smoke list, not this suite's.
 *
 * It implements exactly the surface site/js/analytics/ uses, and throws loudly
 * on anything else, so the shim cannot quietly drift away from the real API by
 * silently accepting a call the dashboard has started making.
 */
(function (root) {
  'use strict';

  const SESSION_KEY = 'sb-test-session';

  function readSession() {
    try {
      const raw = root.localStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function notImplemented(name) {
    return function () {
      throw new Error(
        `supabase-shim: ${name}() is not implemented. The dashboard has started `
        + 'using part of supabase-js the test shim does not cover — extend '
        + 'tests/analytics/stubs/supabase-shim.js rather than working around it.');
    };
  }

  class Query {
    constructor(client, table) {
      this.client = client;
      this.table = table;
      this.params = new URLSearchParams();
      this.wantHead = false;
      this.wantCount = null;
    }

    select(columns = '*', opts = {}) {
      this.params.set('select', columns);
      this.wantHead = Boolean(opts.head);
      this.wantCount = opts.count || null;
      return this;
    }

    eq(column, value) { return this._filter(column, 'eq', value); }
    gt(column, value) { return this._filter(column, 'gt', value); }
    gte(column, value) { return this._filter(column, 'gte', value); }
    lt(column, value) { return this._filter(column, 'lt', value); }
    lte(column, value) { return this._filter(column, 'lte', value); }
    neq(column, value) { return this._filter(column, 'neq', value); }

    in(column, values) {
      this.params.append(column, `in.(${values.join(',')})`);
      return this;
    }

    order(column, opts = {}) {
      const dir = opts.ascending === false ? 'desc' : 'asc';
      this.params.append('order', `${column}.${dir}`);
      return this;
    }

    limit(n) {
      this.params.set('limit', String(n));
      return this;
    }

    _filter(column, op, value) {
      this.params.append(column, `${op}.${value}`);
      return this;
    }

    then(onDone, onFail) { return this._run().then(onDone, onFail); }
    catch(onFail) { return this._run().catch(onFail); }
    finally(fn) { return this._run().finally(fn); }

    async _run() {
      const url = `${this.client.url}/rest/v1/${this.table}?${this.params.toString()}`;
      const headers = this.client._headers();
      if (this.wantCount) headers.Prefer = `count=${this.wantCount}`;
      try {
        const res = await fetch(url, { method: this.wantHead ? 'HEAD' : 'GET', headers });
        const count = parseCount(res.headers.get('content-range'));
        if (!res.ok) {
          return { data: null, count: null, error: await asError(res) };
        }
        if (this.wantHead) return { data: null, count, error: null };
        return { data: await res.json(), count, error: null };
      } catch (err) {
        return { data: null, count: null, error: { message: String(err?.message || err) } };
      }
    }
  }

  function parseCount(contentRange) {
    if (!contentRange) return null;
    const total = contentRange.split('/')[1];
    return total && total !== '*' ? Number(total) : null;
  }

  async function asError(res) {
    let body = {};
    try { body = await res.json(); } catch { /* not every PostgREST error is JSON */ }
    return {
      message: body.message || body.error || `${res.status} ${res.statusText}`,
      code: body.code || String(res.status),
    };
  }

  class Auth {
    constructor(client) {
      this.client = client;
      this.listeners = new Set();
    }

    async getSession() {
      return { data: { session: readSession() }, error: null };
    }

    onAuthStateChange(callback) {
      this.listeners.add(callback);
      const self = this;
      return {
        data: { subscription: { unsubscribe() { self.listeners.delete(callback); } } },
      };
    }

    _emit(event, session) {
      for (const cb of [...this.listeners]) cb(event, session);
    }

    async signInWithOtp({ email, options }) {
      try {
        const res = await fetch(`${this.client.url}/auth/v1/otp`, {
          method: 'POST',
          headers: { ...this.client._headers(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, ...(options || {}) }),
        });
        if (!res.ok) return { data: null, error: await asError(res) };
        return { data: {}, error: null };
      } catch (err) {
        return { data: null, error: { message: String(err?.message || err) } };
      }
    }

    async signOut() {
      root.localStorage.removeItem(SESSION_KEY);
      this._emit('SIGNED_OUT', null);
      return { error: null };
    }

    signUp = notImplemented('signUp');
    signInWithPassword = notImplemented('signInWithPassword');
    verifyOtp = notImplemented('verifyOtp');
  }

  class Client {
    constructor(url, key) {
      this.url = String(url).replace(/\/+$/, '');
      this.key = key;
      this.auth = new Auth(this);
    }

    _headers() {
      const session = readSession();
      return {
        apikey: this.key,
        Authorization: `Bearer ${session?.access_token || this.key}`,
        Accept: 'application/json',
      };
    }

    from(table) { return new Query(this, table); }

    async rpc(fn, args = {}) {
      try {
        const res = await fetch(`${this.url}/rest/v1/rpc/${fn}`, {
          method: 'POST',
          headers: { ...this._headers(), 'Content-Type': 'application/json' },
          body: JSON.stringify(args),
        });
        if (!res.ok) return { data: null, error: await asError(res) };
        return { data: await res.json(), error: null };
      } catch (err) {
        return { data: null, error: { message: String(err?.message || err) } };
      }
    }

    channel = notImplemented('channel');
    storage = { from: notImplemented('storage.from') };
  }

  root.supabase = {
    createClient(url, key) { return new Client(url, key); },
    __shim: true,
  };
}(window));
