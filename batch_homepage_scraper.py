#!/usr/bin/env python3
"""
example: python batch_homepage_scraper.py urls.txt --out out/homepages.jsonl

- Reads a list of URLs (one per line) from a file or stdin
- Fetches each homepage
- Extracts readable text (strips nav/header/footer/scripts/styles)
- Writes one JSONL record per URL with: url, title, text, word_count, fetched_at, status
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple
from playwright.sync_api import sync_playwright # type: ignore


import requests # pyright: ignore[reportMissingModuleSource]
from bs4 import BeautifulSoup # pyright: ignore[reportMissingImports]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HomepageHarvester/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def read_urls(source: str | None) -> List[str]:
    urls: List[str] = []
    if source:
        with open(source, "r", encoding="utf-8") as f:
            urls.extend([ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")])
    else:
        urls.extend([ln.strip() for ln in sys.stdin if ln.strip() and not ln.strip().startswith("#")])
    # de-duplicate while preserving order
    seen = set()
    uniq = []
    for u in urls:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq

def clean_text(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)

def extract_text(html: str) -> Tuple[str | None, str]:
    soup = BeautifulSoup(html, "html.parser")
    # for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
    #     tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    text = soup.get_text(separator="\n")
    return title, clean_text(text)

def fetch(url: str, wait_ms: int = 3000, goto_timeout: int = 30000) -> tuple[int, str]:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError # type: ignore

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        response = None
        try:
            # waiting until the network is idle unless get a timeout
            response = page.goto(url, wait_until="networkidle", timeout=goto_timeout)
        except PlaywrightTimeoutError:
            print(f"[WARN] Timeout while loading {url}, continuing with current page content...", file=sys.stderr)
            try:
                # grab whatever loaded
                response = page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout)
            except PlaywrightTimeoutError:
                pass
        except Exception as e:
            print(f"[WARN] Error during page.goto for {url}: {e}", file=sys.stderr)

        # wait for JS stuff
        page.wait_for_timeout(wait_ms)

        html = page.content()
        status = response.status if response else 200

        browser.close()
        return status, html

def write_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def main() -> int:
    p = argparse.ArgumentParser(description="Fetch homepage text from a list of URLs and save as JSONL.")
    p.add_argument("url_list", nargs="?", help="Path to a file with one URL per line. If omitted, read from stdin.")
    p.add_argument("--out", default="out/homepages_5nov.jsonl", help="Output JSONL file path (default: out/homepages.jsonl)")
    p.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between requests (default: 1.0)")
    args = p.parse_args()

    urls = read_urls(args.url_list)
    if not urls:
        print("No URLs provided.", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    ok = 0
    for i, url in enumerate(urls, 1):
        try:
            status, html = fetch(url)
            title, text = extract_text(html)
            rec = {
                "url": url,
                "title": title,
                "text": text,
                "word_count": len(text.split()) if text else 0,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "status": status,
            }
            write_jsonl(out_path, rec)
            ok += 1
            print(f"[{i}/{len(urls)}] OK {url} -> {rec['word_count']} words")
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", "N/A")
            print(f"[{i}/{len(urls)}] HTTP {code} for {url}: {e}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"[{i}/{len(urls)}] Request error for {url}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[{i}/{len(urls)}] Unexpected error for {url}: {e}", file=sys.stderr)
        time.sleep(args.sleep)

    print(f"Done. {ok}/{len(urls)} succeeded. Output -> {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
