import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

THE_GOAN = [
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

HERALD = [
    {
        "name": "O HERALDO",
        "description": "Goa's English Daily Newspaper",
        "slug": "oheraldo",
    },
    {
        "name": "DAINIK HERALD",
        "description": "Goa's Marathi Daily Newspaper",
        "slug": "dainik-herald",
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

def get_the_goan_latest(paper):
    r = requests.get(paper["url"], headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

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

    read_url = None
    for a in soup.find_all("a", href=True):
        if clean(a.get_text(" ", strip=True)).lower() == "read now":
            read_url = urljoin(paper["url"], a["href"])
            break

    return {
        "name": paper["name"],
        "description": paper["description"],
        "published": published,
        "edition_url": paper["url"],
        "read_url": read_url or paper["url"],
    }

def get_herald_latest(paper):
    homepage = "https://epaper.heraldgoa.in/"
    r = requests.get(homepage, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    pattern = re.compile(
        rf"/epaper/{re.escape(paper['slug'])}/(\d{{2}}-\d{{2}}-\d{{4}})(?:/|$)",
        re.I,
    )

    matches = []
    for a in soup.find_all("a", href=True):
        href = urljoin(homepage, a["href"])
        m = pattern.search(href)
        if m:
            matches.append((m.group(1), href))

    # Also try today's date directly. This makes the updater work even
    # if the homepage has not yet refreshed its visible links.
    from datetime import timedelta
    today = datetime.now().astimezone()
    candidates = []

    for days_back in range(0, 8):
        d = today - timedelta(days=days_back)
        candidates.append(
            f"https://epaper.heraldgoa.in/epaper/{paper['slug']}/{d.strftime('%d-%m-%Y')}"
        )

    # Prefer the newest date discovered on the official homepage.
    dates = []
    for date_text, href in matches:
        try:
            d = datetime.strptime(date_text, "%d-%m-%Y")
            dates.append((d, href, date_text))
        except ValueError:
            pass

    dates.sort(reverse=True)

    if dates:
        _, edition_url, date_text = dates[0]
    else:
        edition_url = None
        date_text = None

        for candidate in candidates:
            test = requests.get(
                candidate,
                headers=HEADERS,
                timeout=20,
                allow_redirects=True,
            )
            if test.ok and "Page not found" not in test.text:
                edition_url = candidate
                date_text = candidate.rsplit("/", 1)[-1]
                break

        if not edition_url:
            raise RuntimeError(
                f"Could not find a current {paper['name']} edition."
            )

    parsed_date = datetime.strptime(date_text, "%d-%m-%Y")
    published = parsed_date.strftime("%b %d, %Y")

    return {
        "name": paper["name"],
        "description": paper["description"],
        "published": published,
        "edition_url": edition_url,
        "read_url": edition_url,
    }

def load_old():
    path = Path("data.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    old = load_old()
    old_papers = {
        p.get("name"): p for p in old.get("papers", [])
    }

    results = []

    for paper in THE_GOAN:
        try:
            item = get_the_goan_latest(paper)
            results.append(item)
            print(f"OK: {paper['name']}")
        except Exception as e:
            print(f"ERROR: {paper['name']}: {e}")
            results.append(old_papers.get(paper["name"], {
                "name": paper["name"],
                "description": paper["description"],
                "published": "Unavailable",
                "edition_url": paper["url"],
                "read_url": paper["url"],
            }))

    for paper in HERALD:
        try:
            item = get_herald_latest(paper)
            results.append(item)
            print(f"OK: {paper['name']}")
        except Exception as e:
            print(f"ERROR: {paper['name']}: {e}")
            results.append(old_papers.get(paper["name"], {
                "name": paper["name"],
                "description": paper["description"],
                "published": "Unavailable",
                "edition_url": f"https://epaper.heraldgoa.in/epaper/{paper['slug']}/",
                "read_url": f"https://epaper.heraldgoa.in/epaper/{paper['slug']}/",
            }))

    output = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "papers": results,
    }

    Path("data.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

if __name__ == "__main__":
    main()
