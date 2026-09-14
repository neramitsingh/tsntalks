"""Create the GitHub repo for this project using the token git already has cached.

Usage: python infra/github_repo.py neramitsingh tsntalks
Never prints the token.
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request


def cached_token(host: str = "github.com") -> str:
    out = subprocess.run(
        ["git", "credential", "fill"],
        input=f"protocol=https\nhost={host}\n\n",
        capture_output=True, text=True, check=True,
    ).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("no cached GitHub credential; run `git push` once by hand")


def create_repo(owner: str, name: str, token: str) -> str:
    body = json.dumps({
        "name": name,
        "description": "TSN Talks: live media kit and analytics",
        "private": False,
        "has_issues": True,
        "has_wiki": False,
        "auto_init": False,
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/user/repos", data=body, method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "tsntalks-setup"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)["clone_url"]
    except urllib.error.HTTPError as e:
        if e.code == 422:  # already exists
            return f"https://github.com/{owner}/{name}.git"
        raise SystemExit(f"GitHub API {e.code}: {e.read()[:200]!r}")


if __name__ == "__main__":
    owner, name = sys.argv[1], sys.argv[2]
    url = create_repo(owner, name, cached_token())
    print("repo:", url)
