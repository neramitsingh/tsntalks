"""Create the Supabase project for TSN Talks in Ney's org and store its keys locally.

Usage: python infra/supabase_create.py
Reads the Management PAT from ~/.secrets/secrets.md (line containing 'sbp_').
Writes url/anon/service keys + db password to ~/.secrets/secrets.md under the TSN Talks section.
Never prints any key.
"""
import json
import re
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path

SECRETS = Path.home() / ".secrets" / "secrets.md"
API = "https://api.supabase.com/v1"
ORG_ID = "sxjdvgmuuwtpdwmhnjop"
NAME = "tsntalks"
REGION = "ap-southeast-1"


def pat() -> str:
    m = re.search(r"sbp_[a-f0-9]{40}", SECRETS.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("no Supabase PAT in secrets store")
    return m.group(0)


def call(method: str, path: str, token: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Supabase API {method} {path} -> {e.code}: {e.read()[:300]!r}")


def find_project(token: str):
    for p in call("GET", "/projects", token):
        if p["name"] == NAME:
            return p
    return None


def main():
    token = pat()
    proj = find_project(token)
    db_pass = None
    if proj is None:
        db_pass = secrets.token_urlsafe(24)
        proj = call("POST", "/projects", token, {
            "name": NAME, "organization_id": ORG_ID, "region": REGION,
            "db_pass": db_pass, "plan": "free",
        })
        print("created project", proj["id"])
    ref = proj["id"]
    for _ in range(60):
        status = call("GET", f"/projects/{ref}", token)["status"]
        if status == "ACTIVE_HEALTHY":
            break
        print("status", status)
        time.sleep(10)
    else:
        raise SystemExit(f"project {ref} not healthy in time")
    keys = {k["name"]: k["api_key"] for k in call("GET", f"/projects/{ref}/api-keys", token)}
    url = f"https://{ref}.supabase.co"
    block = (
        f"- Supabase project `{NAME}` ref `{ref}` (Ney's org, {REGION}); URL `{url}`\n"
        f"  - anon key: `{keys['anon']}`\n"
        f"  - service_role key (collector only, GitHub secret SUPABASE_SERVICE_ROLE_KEY): `{keys['service_role']}`\n"
        + (f"  - db password: `{db_pass}`\n" if db_pass else "")
    )
    text = SECRETS.read_text(encoding="utf-8")
    marker = "## TSN Talks (Sunny's podcast) / Zernio\n"
    if f"ref `{ref}`" not in text:
        text = text.replace(marker, marker + block)
        SECRETS.write_text(text, encoding="utf-8")
    print("project ready:", ref, url)


if __name__ == "__main__":
    main()
