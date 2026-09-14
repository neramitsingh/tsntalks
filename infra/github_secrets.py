"""Set the GitHub Actions secrets for the collector from the local secrets store.

Usage: python infra/github_secrets.py neramitsingh tsntalks
Reads ~/.secrets/secrets.md, encrypts each value with the repo's public key (libsodium sealed box), PUTs it.
Never prints a value.
"""
import base64
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from nacl import encoding, public

from github_repo import cached_token

SECRETS = Path.home() / ".secrets" / "secrets.md"


def api(method: str, url: str, token: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "Content-Type": "application/json", "User-Agent": "tsntalks-setup"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r) if r.status != 204 else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GitHub API {method} {url} -> {e.code}: {e.read()[:200]!r}")


def encrypt(public_key_b64: str, value: str) -> str:
    pk = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


def main(owner: str, repo: str):
    t = SECRETS.read_text(encoding="utf-8")
    values = {
        "ZERNIO_API_KEY": re.search(r"Sunny's Zernio API key[^`]*`(sk_[a-f0-9]{64})`", t).group(1),
        "SUPABASE_URL": re.search(r"URL `(https://[a-z]+\.supabase\.co)`", t).group(1),
        "SUPABASE_SERVICE_ROLE_KEY": re.search(r"service_role key[^`]*`([^`]+)`", t).group(1),
    }
    token = cached_token()
    key = api("GET", f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key", token)
    for name, value in values.items():
        api("PUT", f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{name}", token,
            {"encrypted_value": encrypt(key["key"], value), "key_id": key["key_id"]})
        print("set", name)
    names = [s["name"] for s in api("GET", f"https://api.github.com/repos/{owner}/{repo}/actions/secrets", token)["secrets"]]
    print("repo secrets:", sorted(names))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
