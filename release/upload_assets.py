#!/usr/bin/env python3
"""Upload the release archives to a GitHub release.

No `gh` CLI here, so talk to the uploads endpoint directly. The token is read
from the git credential manager rather than being written anywhere.

    python release/upload_assets.py <owner/repo> <release_id> <zip> [<zip> ...]
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

API = "https://api.github.com"
UPLOAD = "https://uploads.github.com"


def token() -> str:
    out = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, check=False,
    ).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line[len("password="):]
    raise SystemExit("no github credential available; run `git credential fill` first")


def upload(tok: str, repo: str, rid: str, path: str) -> None:
    name = os.path.basename(path)
    size = os.path.getsize(path)
    url = f"{UPLOAD}/repos/{repo}/releases/{rid}/assets?name={urllib.parse.quote(name)}"
    req = urllib.request.Request(
        url,
        data=open(path, "rb").read(),
        method="POST",
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/zip",
        },
    )
    with urllib.request.urlopen(req) as r:
        d = json.load(r)
    print(f"  uploaded {name}  {size/2**20:.1f} MB -> {d['browser_download_url']}", flush=True)


if __name__ == "__main__":
    repo, rid = sys.argv[1], sys.argv[2]
    tok = token()
    for p in sys.argv[3:]:
        print(f"--- {os.path.basename(p)} ({os.path.getsize(p)/2**20:.1f} MB) ---", flush=True)
        upload(tok, repo, rid, p)
    print("全部上传完成", flush=True)
