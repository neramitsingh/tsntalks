"""Apply db/*.sql to the tsntalks Supabase project through the Management API.

Usage: python infra/apply_sql.py            # applies all files in order
       python infra/apply_sql.py db/003_functions.sql
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SECRETS = Path.home() / ".secrets" / "secrets.md"
API = "https://api.supabase.com/v1"


def read_secret(pattern: str) -> str:
    m = re.search(pattern, SECRETS.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"missing secret matching {pattern}")
    return m.group(1)


def run_sql(ref: str, token: str, sql: str):
    req = urllib.request.Request(
        f"{API}/projects/{ref}/database/query", data=json.dumps({"query": sql}).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"SQL failed {e.code}: {e.read()[:500]!r}")


def main(paths):
    token = read_secret(r"(sbp_[a-f0-9]{40})")
    ref = read_secret(r"Supabase project `tsntalks` ref `([a-z]+)`")
    for p in paths:
        sql = Path(p).read_text(encoding="utf-8")
        run_sql(ref, token, sql)
        print("applied", p)


if __name__ == "__main__":
    files = sys.argv[1:] or sorted(str(p) for p in Path("db").glob("*.sql"))
    main(files)
