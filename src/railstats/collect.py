"""Polite collector for train running history from etrain.info.

- One request at a time, 6-8 seconds apart; stops on HTTP 403/429 instead of retrying harder.
- Identifies itself with a descriptive User-Agent.
- Every page is cached in data/raw/, so a re-run never fetches the same page twice.
- robots.txt allows these pages; the site's terms limit use to personal, non-commercial purposes, so
  the raw pages and extracted data are kept local (data/ is git-ignored). Only code and aggregate
  findings are published.
"""

from __future__ import annotations

import random
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import certifi

BASE = "https://etrain.info"
USER_AGENT = ("Mozilla/5.0 (compatible; rail-punctuality-study/0.1; personal non-commercial research; "
              "+https://github.com/abpandey-dev)")
RAW = Path("data/raw")
# Some Python builds (e.g. python.org on macOS) ship without system CA certificates; use certifi's bundle.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class Blocked(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _get(url: str, follow: bool = True):
    https = urllib.request.HTTPSHandler(context=SSL_CONTEXT)
    opener = urllib.request.build_opener(https) if follow else urllib.request.build_opener(https, _NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, r.headers, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Blocked(f"HTTP {e.code} for {url}") from e
        return e.code, e.headers, ""


def canonical_path(number: int) -> str | None:
    """The site redirects /train/x-<number>/history to the train's canonical URL; read it without following."""
    status, headers, _ = _get(f"{BASE}/train/x-{number}/history", follow=False)
    loc = headers.get("Location") if headers else None
    if status in (301, 302) and loc and f"-{number}/history" in loc:
        return loc.replace(BASE, "")
    return None


def pause() -> None:
    time.sleep(6 + random.random() * 2)


def collect(numbers: list[int], period: str = "6m") -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    done, skipped, failed = [], [], []
    for i, n in enumerate(numbers, 1):
        out = RAW / f"{n}_{period}.html"
        if out.exists():
            done.append(n)
            continue
        try:
            path = canonical_path(n)
            pause()
            if not path:
                skipped.append(n)
                print(f"[{i}/{len(numbers)}] {n}: not found on source, skipped", file=sys.stderr)
                continue
            status, _, html = _get(f"{BASE}{path}?d={period}")
            pause()
            if status == 200 and "tooltipData" in html:
                out.write_text(html, encoding="utf-8")
                done.append(n)
                print(f"[{i}/{len(numbers)}] {n}: ok ({path})", file=sys.stderr)
            else:
                failed.append(n)
                print(f"[{i}/{len(numbers)}] {n}: HTTP {status}, no history data", file=sys.stderr)
        except Blocked as e:
            print(f"Stopping: {e}. The site asked us to slow down or stop.", file=sys.stderr)
            break
        except (urllib.error.URLError, TimeoutError) as e:
            failed.append(n)
            print(f"[{i}/{len(numbers)}] {n}: network error {e}", file=sys.stderr)
            pause()
    return {"done": done, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    from railstats.trains import TRAINS

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(TRAINS)
    r = collect(TRAINS[:limit])
    print(f"done {len(r['done'])}, skipped {r['skipped']}, failed {r['failed']}")
