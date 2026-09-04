import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

THE_GOAN = [
    {
        "name": "THE GOAN EVERYDAY",
        "description": "Goa's Leading English Daily Newspaper",
        "language": "English",
        "url": "https://epaper.thegoan.net/edition/THE-GOAN-EVERYDAY/10711",
        "logo": "assets/logos/the-goan-everyday.svg",
    },
    {
        "name": "GOAN VARTA",
        "description": "Goa's Leading Marathi Daily Newspaper",
        "language": "Marathi",
        "url": "https://epaper.thegoan.net/edition/GOAN-VARTA/9849",
        "logo": "assets/logos/goan-varta.svg",
    },
    {
        "name": "BHAANGARBHUIN",
        "description": "Goa's Konkani Daily Newspaper",
        "language": "Konkani",
        "url": "https://epaper.thegoan.net/edition/BHAANGARBHUIN/23246",
        "logo": "assets/logos/bhaangar-bhuin.svg",
    },
    {
        "name": "KONKANSAAD",
        "description": "KONKANSAAD Marathi Newspaper",
        "language": "Marathi",
        "url": "https://epaper.thegoan.net/edition/KONKANSAAD/37473",
        "logo": "assets/logos/konkansaad.svg",
    },
]

HERALD = [
    {
        "name": "O HERALDO",
        "description": "Goa's English Daily Newspaper",
        "language": "English",
        "slug": "oheraldo",
        "logo": "assets/logos/o-heraldo.svg",
    },
    {
        "name": "DAINIK HERALD",
        "description": "Goa's Marathi Daily Newspaper",
        "language": "Marathi",
        "slug": "dainik-herald",
        "logo": "assets/logos/dainik-herald.svg",
    },
]

OTHER = [
    {
        "name": "NAVHIND TIMES",
        "description": "Goa's Trusted English Daily Newspaper",
        "language": "English",
        "url": "https://epaper.navhindtimes.in/mainpage.aspx",
        "logo": "assets/logos/navhind-times.svg",
    },
    {
        "name": "LOKMAT (GOA EDITION)",
        "description": "Marathi Daily Newspaper — Goa Edition",
        "language": "Marathi",
        "url": "https://epaper.lokmat.com/main-editions/Goa%20Main/-1/1",
        "logo": "assets/logos/lokmat-goa.svg",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GoanEPaperUpdater/2.0; +https://github.com/)"
    )
}

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def parse_date(text):
    patterns = [
        r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"(\d{1,2},\s+[A-Za-z]{3,9}\s+\d{4})",
        r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            value = m.group(1)
            for fmt in ("%b %d, %Y", "%B %d, %Y", "%d, %B %Y", "%d, %b %Y", "%d %B %Y", "%d %b %Y"):
                try:
                    return datetime.strptime(value, fmt).strftime("%b %d, %Y")
                except ValueError:
                    pass
    return None

def get_the_goan_latest(paper):
    r = requests.get(paper["url"], headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    published = None
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
        "id": re.sub(r"[^a-z0-9]+", "-", paper["name"].lower()).strip("-"),
        "name": paper["name"],
        "description": paper["description"],
        "language": paper["language"],
        "published": published or "Latest",
        "edition_url": paper["url"],
        "read_url": read_url or paper["url"],
        "logo": paper["logo"],
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

    today = datetime.now().astimezone()
    candidates = [
        f"https://epaper.heraldgoa.in/epaper/{paper['slug']}/"
        f"{(today - timedelta(days=i)).strftime('%d-%m-%Y')}"
        for i in range(0, 8)
    ]

    dates = []
    for date_text, href in matches:
        try:
            dates.append((datetime.strptime(date_text, "%d-%m-%Y"), href, date_text))
        except ValueError:
            pass
    dates.sort(reverse=True)

    if dates:
        _, edition_url, date_text = dates[0]
    else:
        edition_url = None
        date_text = None
        for candidate in candidates:
            test = requests.get(candidate, headers=HEADERS, timeout=20, allow_redirects=True)
            if test.ok and "Page not found" not in test.text:
                edition_url = candidate
                date_text = candidate.rsplit("/", 1)[-1]
                break
        if not edition_url:
            raise RuntimeError(f"Could not find a current {paper['name']} edition.")

    published = datetime.strptime(date_text, "%d-%m-%Y").strftime("%b %d, %Y")
    return {
        "id": re.sub(r"[^a-z0-9]+", "-", paper["name"].lower()).strip("-"),
        "name": paper["name"],
        "description": paper["description"],
        "language": paper["language"],
        "published": published,
        "edition_url": edition_url,
        "read_url": edition_url,
        "logo": paper["logo"],
    }

def get_simple_latest(paper):
    r = requests.get(paper["url"], headers=HEADERS, timeout=30)
    r.raise_for_status()
    text = clean(BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True))
    published = parse_date(text) or "Latest"
    return {
        "id": re.sub(r"[^a-z0-9]+", "-", paper["name"].lower()).strip("-"),
        "name": paper["name"],
        "description": paper["description"],
        "language": paper["language"],
        "published": published,
        "edition_url": paper["url"],
        "read_url": paper["url"],
        "logo": paper["logo"],
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
    old_papers = {p.get("name"): p for p in old.get("papers", [])}
    results = []

    for paper in THE_GOAN:
        try:
            item = get_the_goan_latest(paper)
            results.append(item)
            print(f"OK: {paper['name']}")
        except Exception as e:
            print(f"ERROR: {paper['name']}: {e}")
            results.append(old_papers.get(paper["name"], {
                "id": re.sub(r"[^a-z0-9]+", "-", paper["name"].lower()).strip("-"),
                "name": paper["name"],
                "description": paper["description"],
                "language": paper["language"],
                "published": "Unavailable",
                "edition_url": paper["url"],
                "read_url": paper["url"],
                "logo": paper["logo"],
            }))

    for paper in HERALD:
        try:
            item = get_herald_latest(paper)
            results.append(item)
            print(f"OK: {paper['name']}")
        except Exception as e:
            print(f"ERROR: {paper['name']}: {e}")
            results.append(old_papers.get(paper["name"], {
                "id": re.sub(r"[^a-z0-9]+", "-", paper["name"].lower()).strip("-"),
                "name": paper["name"],
                "description": paper["description"],
                "language": paper["language"],
                "published": "Unavailable",
                "edition_url": f"https://epaper.heraldgoa.in/epaper/{paper['slug']}/",
                "read_url": f"https://epaper.heraldgoa.in/epaper/{paper['slug']}/",
                "logo": paper["logo"],
            }))

    for paper in OTHER:
        try:
            item = get_simple_latest(paper)
            results.append(item)
            print(f"OK: {paper['name']}")
        except Exception as e:
            print(f"ERROR: {paper['name']}: {e}")
            results.append(old_papers.get(paper["name"], {
                "id": re.sub(r"[^a-z0-9]+", "-", paper["name"].lower()).strip("-"),
                "name": paper["name"],
                "description": paper["description"],
                "language": paper["language"],
                "published": "Latest",
                "edition_url": paper["url"],
                "read_url": paper["url"],
                "logo": paper["logo"],
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
