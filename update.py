import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

NEWSPAPERS = [
    {
        "name": "THE GOAN EVERYDAY",
        "description": "Goa's Leading English Daily Newspaper",
        "url": "https://epaper.thegoan.net/edition/THE-GOAN-EVERYDAY/10711",
    },
    {
        "name": "GOAN VARTA",
        "description": "Goa's Leading Marathi Daily Newspaper",
        "url": "https://epaper.thegoan.net/edition/GOAN-VARTA/9849",
    },
    {
        "name": "BHAANGARBHUIN",
        "description": "Goa's Konkani Daily Newspaper",
        "url": "https://epaper.thegoan.net/edition/BHAANGARBHUIN/23246",
    },
    {
        "name": "KONKANSAAD",
        "description": "KONKANSAAD Marathi Newspaper",
        "url": "https://epaper.thegoan.net/edition/KONKANSAAD/37473",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GoanEPaperUpdater/1.0; "
        "+https://github.com/)"
    )
}

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def get_latest(paper):
    r = requests.get(paper["url"], headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # The official edition page displays the current publication date.
    published = "Latest"
    for text in soup.stripped_strings:
        m = re.search(
            r"Published\s+On\s*:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            text,
            re.I,
        )
        if m:
            published = clean(m.group(1))
            break

    # Find the official "Read Now" destination.
    read_url = None
    for a in soup.find_all("a", href=True):
        label = clean(a.get_text(" ", strip=True)).lower()
        if label == "read now":
            read_url = a["href"]
            break

    if read_url:
        from urllib.parse import urljoin
        read_url = urljoin(paper["url"], read_url)

    # If the page doesn't expose a Read Now URL, safely fall back
    # to the official edition page rather than guessing a reader URL.
    if not read_url:
        read_url = paper["url"]

    return {
        "name": paper["name"],
        "description": paper["description"],
        "published": published,
        "edition_url": paper["url"],
        "read_url": read_url,
    }

def main():
    results = []

    for paper in NEWSPAPERS:
        try:
            results.append(get_latest(paper))
            print(f"OK: {paper['name']}")
        except Exception as e:
            print(f"ERROR: {paper['name']}: {e}")
            # Keep the old entry if one exists, so one temporary failure
            # doesn't destroy the website's working data.
            old_file = Path("data.json")
            if old_file.exists():
                try:
                    old = json.loads(old_file.read_text(encoding="utf-8"))
                    old_match = next(
                        (x for x in old.get("papers", [])
                         if x.get("name") == paper["name"]),
                        None
                    )
                    if old_match:
                        results.append(old_match)
                        continue
                except Exception:
                    pass

            results.append({
                "name": paper["name"],
                "description": paper["description"],
                "published": "Unavailable",
                "edition_url": paper["url"],
                "read_url": paper["url"],
            })

    output = {
        "updated": datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        ),
        "papers": results,
    }

    Path("data.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

if __name__ == "__main__":
    main()
