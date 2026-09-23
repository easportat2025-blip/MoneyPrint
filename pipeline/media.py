import re
from pathlib import Path
import requests
import config


UA = {"User-Agent": "MoneyPrint-ReZain/1.0 (educational bot)"}


def _slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:40] or "scene"


def _pick_ext(url: str, default: str = "jpg") -> str:
    path = url.split("?")[0].lower()
    for ext in ("jpeg", "jpg", "png", "webp", "avif"):
        if path.endswith("." + ext):
            return "jpg" if ext == "jpeg" else ext
    return default


def _download(url: str, dest: Path) -> Path | None:
    try:
        r = requests.get(url, headers=UA, timeout=30, stream=True)
        if r.status_code != 200:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        if dest.stat().st_size < 5000:
            dest.unlink(missing_ok=True)
            return None
        return dest
    except requests.RequestException:
        return None


def from_pexels(query: str, vertical: bool, dest: Path) -> Path | None:
    if not config.PEXELS_API_KEY:
        return None
    orientation = "portrait" if vertical else "landscape"
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": query, "orientation": orientation, "per_page": 5},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        photos = r.json().get("photos", [])
        if not photos:
            return None
        src = photos[0].get("src", {}).get("large2x") or photos[0].get("src", {}).get("large")
        if not src:
            return None
        return _download(src, dest)
    except (requests.RequestException, ValueError):
        return None


def from_pixabay(query: str, dest: Path) -> Path | None:
    if not config.PIXABAY_API_KEY:
        return None
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": config.PIXABAY_API_KEY,
                "q": query,
                "image_type": "photo",
                "orientation": "vertical",
                "safesearch": "true",
                "per_page": 5,
            },
            timeout=20,
        )
        if r.status_code != 200:
            return None
        hits = r.json().get("hits", [])
        if not hits:
            return None
        url = hits[0].get("largeImageURL") or hits[0].get("webformatURL")
        if not url:
            return None
        return _download(url, dest)
    except (requests.RequestException, ValueError):
        return None


def from_nasa(query: str, dest: Path) -> Path | None:
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={"q": query, "media_type": "image"},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        items = r.json().get("collection", {}).get("items", [])
        if not items:
            return None
        hrefs = items[0].get("hrefs") or []
        for h in hrefs:
            if re.search(r"\.(jpg|jpeg|png)$", str(h), re.I):
                return _download(h, dest)
        assets_url = None
        links = items[0].get("links") or []
        if links:
            assets_url = links[0].get("href")
        if assets_url:
            ar = requests.get(assets_url, timeout=20)
            if ar.status_code == 200:
                for f in ar.json().get("files", []):
                    name = str(f.get("name", ""))
                    if re.search(r"\.(jpg|jpeg|png)$", name, re.I):
                        base = assets_url.rsplit("/", 1)[0]
                        return _download(f"{base}/{name}", dest)
        return None
    except (requests.RequestException, ValueError, KeyError):
        return None


def fetch_scene(query: str, scene_dir: Path, vertical: bool) -> Path:
    slug = _slug(query)
    dest = scene_dir / f"{slug}.jpg"
    if dest.exists() and dest.stat().st_size > 5000:
        return dest
    for source in (from_pexels, from_nasa, from_pixabay):
        try:
            if source is from_pexels:
                got = source(query, vertical, dest)
            else:
                got = source(query, dest)
        except Exception:
            got = None
        if got:
            return got
    placeholder = scene_dir / f"fallback_{slug}.jpg"
    if not placeholder.exists():
        _make_fallback(placeholder, query)
    return placeholder


def _make_fallback(dest: Path, label: str) -> None:
    import subprocess

    safe = label.replace("'", "").replace(":", "")[:40]
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0x0b1020:s=1600x1600",
        "-vf",
        f"drawtext=text='{safe}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2",
        "-frames:v",
        "1",
        str(dest),
    ]
    subprocess.run(cmd, capture_output=True, timeout=60)
    if not dest.exists():
        raise RuntimeError("fallback frame failed (is ffmpeg installed?)")


def fetch_all(scenes: list, cache_dir: Path, vertical: bool) -> list[Path]:
    paths = []
    for i, s in enumerate(scenes):
        if config.kill_requested():
            raise RuntimeError("kill switch on")
        p = fetch_scene(s["search"], cache_dir / f"scene_{i:02d}", vertical)
        paths.append(p)
    return paths
