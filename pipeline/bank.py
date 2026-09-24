import json
import re
from pathlib import Path
import requests
import config

BANK_FILE = config.ROOT / "bank" / "clips.json"
UA = {"User-Agent": "MoneyPrint-ReZain/1.0 (educational bot)"}

TOPICS = [
    "black hole",
    "mars surface",
    "galaxy",
    "nebula",
    "moon",
    "earth from space",
    "astronaut",
    "rocket launch",
    "solar system",
    "exoplanet",
    "james webb telescope",
    "saturn",
    "jupiter",
    "sun surface",
    "starfield",
]

HISTORY_TOPICS = [
    "pyramids of giza",
    "colosseum rome",
    "knight armor medieval",
    "viking ship",
    "samurai",
    "titanic ship",
    "napoleon bonaparte painting",
    "egyptian hieroglyphs",
    "great wall of china",
    "medieval castle",
    "world war 2 soldier",
    "aztec calendar stone",
    "roman statue",
    "joan of arc painting",
    "plague doctor engraving",
]


def load() -> dict:
    if BANK_FILE.exists():
        try:
            return json.loads(BANK_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"topics": {}}


def save(bank: dict) -> None:
    BANK_FILE.parent.mkdir(parents=True, exist_ok=True)
    BANK_FILE.write_text(json.dumps(bank, indent=2, ensure_ascii=False), encoding="utf-8")


def _words(s: str) -> set:
    return set(re.findall(r"[a-z]+", s.lower()))


def find(query: str, skip: set | None = None, vertical: bool = True) -> dict | None:
    skip = skip or set()
    bank = load()
    topics = bank.get("topics", {})
    if not topics:
        return None
    qw = _words(query)
    scored = []
    for topic, clips in topics.items():
        tw = _words(topic)
        overlap = len(qw & tw)
        if overlap or any(w in query.lower() for w in tw):
            scored.append((overlap, topic))
    scored.sort(reverse=True)
    for _, topic in scored:
        cands = topics.get(topic, [])
        fresh = [c for c in cands if c.get("url") and c["url"] not in skip]
        pool = fresh or cands
        if pool:
            return pool[0]
    return None


def _nasa_links(query: str, limit: int = 12) -> list:
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={"q": query, "media_type": "image"},
            timeout=25,
        )
        if r.status_code != 200:
            return []
        items = r.json().get("collection", {}).get("items", [])[:10]
        out = []
        for it in items:
            links = sorted(
                [ln for ln in (it.get("links") or []) if ln.get("href")],
                key=lambda ln: ln.get("width", 0) or 0,
                reverse=True,
            )
            for ln in links:
                h = ln["href"]
                if re.search(r"\.(jpg|jpeg|png)(\?|$)", str(h), re.I):
                    out.append(
                        {"url": h, "type": "image", "source": "nasa", "topic": query}
                    )
                    break
            if len(out) >= limit:
                break
        return out
    except requests.RequestException:
        return []


def _commons_links(query: str, limit: int = 12) -> list:
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": f"{query} filetype:bitmap",
                "gsrnamespace": 6,
                "gsrlimit": 15,
                "prop": "imageinfo",
                "iiprop": "url|size|extmetadata",
                "iiextmetadatafilter": "Artist|LicenseShortName",
            },
            timeout=25,
        )
        if r.status_code != 200:
            return []
        pages = r.json().get("query", {}).get("pages", {})
        cands = []
        for p in pages.values():
            ii = (p.get("imageinfo") or [{}])[0]
            url = ii.get("url", "")
            w = ii.get("width", 0) or 0
            size = ii.get("size", 0) or 0
            if not url or w < 900 or size > 25_000_000:
                continue
            meta = ii.get("extmetadata", {})
            lic = meta.get("LicenseShortName", {}).get("value", "")
            artist = meta.get("Artist", {}).get("value", "")
            pd = "public domain" in lic.lower()
            cands.append((not pd, -w, url, artist))
        cands.sort()
        out = []
        for _, _, url, artist in cands[:limit]:
            credit = ""
            a = re.sub(r"<[^>]+>", "", artist or "").strip()[:100]
            if a:
                out.append(
                    {
                        "url": url,
                        "type": "image",
                        "source": "commons",
                        "topic": query,
                        "credit": f"Image: {a} (Wikimedia Commons)",
                    }
                )
            else:
                out.append(
                    {"url": url, "type": "image", "source": "commons", "topic": query}
                )
        return out
    except requests.RequestException:
        return []


def build(
    topics: list | None = None, per_topic: int = 10, source: str = "nasa"
) -> dict:
    if topics is None:
        topics = HISTORY_TOPICS if source == "commons" else TOPICS
    bank = load()
    store = bank.setdefault("topics", {})
    for topic in topics:
        if config.kill_requested():
            break
        have = {c.get("url") for c in store.get(topic, [])}
        if source == "commons":
            fresh = [
                c for c in _commons_links(topic, per_topic) if c["url"] not in have
            ]
        else:
            fresh = [c for c in _nasa_links(topic, per_topic) if c["url"] not in have]
        store.setdefault(topic, []).extend(fresh)
        print(f"{topic}: +{len(fresh)} (total {len(store[topic])})")
    save(bank)
    return bank


def stats() -> dict:
    bank = load()
    topics = bank.get("topics", {})
    return {
        "topics": len(topics),
        "clips": sum(len(v) for v in topics.values()),
        "detail": {k: len(v) for k, v in topics.items()},
    }
