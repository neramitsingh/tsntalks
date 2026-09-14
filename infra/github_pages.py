"""Enable GitHub Pages with the Actions build type, and report recent deploys.

Usage: python infra/github_pages.py neramitsingh tsntalks
       python infra/github_pages.py neramitsingh tsntalks runs

Idempotent. Never prints the token.
"""
import json
import sys
import urllib.error
import urllib.request

from github_repo import cached_token


def api(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, str]:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        data=json.dumps(body).encode() if body else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "tsntalks-setup"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def enable(owner: str, repo: str, token: str) -> None:
    status, body = api("POST", f"/repos/{owner}/{repo}/pages", token, {"build_type": "workflow"})
    if status == 409:                       # already enabled: switch it to the workflow source
        status, body = api("PUT", f"/repos/{owner}/{repo}/pages", token, {"build_type": "workflow"})
    if status >= 300 and status != 204:
        raise SystemExit(f"pages setup failed {status}: {body[:300]}")
    status, body = api("GET", f"/repos/{owner}/{repo}/pages", token)
    info = json.loads(body)
    print(json.dumps({k: info.get(k) for k in ("html_url", "status", "build_type")}, indent=1))


def runs(owner: str, repo: str, token: str) -> None:
    status, body = api("GET", f"/repos/{owner}/{repo}/actions/workflows/pages.yml/runs?per_page=3", token)
    if status >= 300:
        raise SystemExit(f"runs lookup failed {status}: {body[:300]}")
    for r in json.loads(body)["workflow_runs"]:
        print(r["created_at"], r["status"], r["conclusion"], r["html_url"])


def main(owner: str, repo: str, what: str = "enable") -> None:
    token = cached_token()
    (runs if what == "runs" else enable)(owner, repo, token)


if __name__ == "__main__":
    main(*sys.argv[1:4])
