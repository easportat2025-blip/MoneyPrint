import re
from pathlib import Path
import requests
import config
from pipeline import bank as bank_mod


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


def from_pexels(
    query: str, vertical: bool, dest: Path, skip: set | None = None, page: int = 1
) -> tuple[Path | None, str]:
    skip = skip or set()
    if not config.PEXELS_API_KEY:
        return None, ""
    orientation = "portrait" if vertical else "landscape"
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={
                "query": query,
                "orientation": orientation,
                "per_page": 10,
                "page": page,
            },
            timeout=20,
        )
        if r.status_code != 200:
            return None, ""
        photos = r.json().get("photos", [])
        cands = []
        for p in photos:
            src = p.get("src", {}).get("large2x") or p.get("src", {}).get("large")
            if src:
                cands.append(src)
        for src in cands:
            if src in skip:
                continue
            got = _download(src, dest)
            if got:
                return got, src
        if cands:
            got = _download(cands[0], dest)
            if got:
                return got, cands[0]
        return None, ""
    except (requests.RequestException, ValueError):
        return None, ""


def from_pixabay(
    query: str, dest: Path, skip: set | None = None
) -> tuple[Path | None, str]:
    skip = skip or set()
    if not config.PIXABAY_API_KEY:
        return None, ""
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": config.PIXABAY_API_KEY,
                "q": query,
                "image_type": "photo",
                "orientation": "vertical",
                "safesearch": "true",
                "per_page": 8,
            },
            timeout=20,
        )
        if r.status_code != 200:
            return None, ""
        hits = r.json().get("hits", [])
        cands = []
        for h in hits:
            url = h.get("largeImageURL") or h.get("webformatURL")
            if url:
                cands.append(url)
        for url in cands:
            if url in skip:
                continue
            got = _download(url, dest)
            if got:
                return got, url
        if cands:
            got = _download(cands[0], dest)
            if got:
                return got, cands[0]
        return None, ""
    except (requests.RequestException, ValueError):
        return None, ""


def _strip_html(s: str) -> str:
    import html

    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()[:120]


def from_commons(
    query: str, dest: Path, skip: set | None = None
) -> tuple[Path | None, str, str]:
    skip = skip or set()
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
            return None, "", ""
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
            lic = _strip_html(meta.get("LicenseShortName", {}).get("value", ""))
            artist = _strip_html(meta.get("Artist", {}).get("value", ""))
            pd = "public domain" in lic.lower()
            cands.append((not pd, -w, url, artist, lic))
        cands.sort()
        ordered = [(u, a) for _, _, u, a, _ in cands]
        for url, artist in ordered:
            if url in skip:
                continue
            got = _download(url, dest)
            if got:
                return got, url, artist
        if ordered:
            got = _download(ordered[0][0], dest)
            if got:
                return got, ordered[0][0], ordered[0][1]
        return None, "", ""
    except (requests.RequestException, ValueError, KeyError):
        return None, "", ""


def from_pixabay_video(
    query: str, vertical: bool, dest: Path, need_sec: float, skip: set | None = None
) -> tuple[Path | None, str]:
    skip = skip or set()
    if not config.PIXABAY_API_KEY:
        return None, ""
    try:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": config.PIXABAY_API_KEY,
                "q": query,
                "per_page": 10,
                "safesearch": "true",
            },
            timeout=20,
        )
        if r.status_code != 200:
            return None, ""
        hits = r.json().get("hits", [])
        cands = []
        for h in hits:
            try:
                dur = float(h.get("duration", 0))
            except (TypeError, ValueError):
                dur = 0
            if dur < max(need_sec * 0.5, 1.5):
                continue
            vids = h.get("videos", {})
            for size in ("medium", "small", "large", "tiny"):
                f = vids.get(size, {})
                link = f.get("url", "")
                if link and link.endswith(".mp4"):
                    cands.append(link)
                    break
        for link in cands:
            if link in skip:
                continue
            got = _download(link, dest.with_suffix(".mp4"))
            if got and got.stat().st_size > 20000:
                return got, link
        if cands:
            got = _download(cands[0], dest.with_suffix(".mp4"))
            if got and got.stat().st_size > 20000:
                return got, cands[0]
        return None, ""
    except (requests.RequestException, ValueError, KeyError):
        return None, ""


def from_archive(
    query: str, dest: Path, need_sec: float, skip: set | None = None
) -> tuple[Path | None, str]:
    skip = skip or set()
    try:
        q = f"({query}) AND mediatype:movies"
        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": q,
                "fl[]": ["identifier", "title"],
                "rows": 8,
                "output": "json",
            },
            timeout=25,
        )
        if r.status_code != 200:
            return None, ""
        docs = r.json().get("response", {}).get("docs", [])
        for doc in docs:
            ident = doc.get("identifier", "")
            if not ident or ident in skip:
                continue
            try:
                m = requests.get(
                    f"https://archive.org/metadata/{ident}", timeout=25
                )
                if m.status_code != 200:
                    continue
                files = m.json().get("files", [])
                mp4s = []
                for f in files:
                    if not str(f.get("name", "")).lower().endswith(".mp4"):
                        continue
                    try:
                        size = int(f.get("size", 0) or 0)
                    except (TypeError, ValueError):
                        size = 0
                    if size < 150_000_000:
                        mp4s.append((size, f["name"]))
                if not mp4s:
                    continue
                mp4s.sort()
                name = mp4s[0][1]
                url = f"https://archive.org/download/{ident}/{name}"
                got = _download(url, dest.with_suffix(".mp4"))
                if got and got.stat().st_size > 20000:
                    return got, f"archive.org:{ident}/{name}"
            except requests.RequestException:
                continue
        return None, ""
    except (requests.RequestException, ValueError, KeyError):
        return None, ""


def from_nasa(query: str, dest: Path) -> Path | None:
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={"q": query, "media_type": "image"},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        items = r.json().get("collection", {}).get("items", [])[:6]
        if not items:
            return None
        for it in items:
            links = sorted(
                [ln for ln in (it.get("links") or []) if ln.get("href")],
                key=lambda ln: ln.get("width", 0) or 0,
                reverse=True,
            )
            for ln in links:
                h = ln["href"]
                if re.search(r"\.(jpg|jpeg|png)(\?|$)", str(h), re.I):
                    got = _download(h, dest)
                    if got:
                        return got
        return None
    except (requests.RequestException, ValueError, KeyError):
        return None


def from_pexels_video(
    query: str,
    vertical: bool,
    dest: Path,
    need_sec: float,
    skip: set | None = None,
    page: int = 1,
) -> tuple[Path | None, str]:
    skip = skip or set()
    if not config.PEXELS_API_KEY:
        return None, ""
    orientation = "portrait" if vertical else "landscape"
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={
                "query": query,
                "orientation": orientation,
                "per_page": 10,
                "page": page,
            },
            timeout=20,
        )
        if r.status_code != 200:
            return None, ""
        videos = r.json().get("videos", [])
        cands = []
        for v in videos:
            try:
                dur = float(v.get("duration", 0))
            except (TypeError, ValueError):
                dur = 0
            if dur < max(need_sec * 0.5, 1.5):
                continue
            files = []
            for f in v.get("video_files", []):
                link = f.get("link", "")
                w = f.get("width", 0) or 0
                if not link or "mp4" not in str(f.get("file_type", "mp4")):
                    continue
                if vertical and w < 600:
                    continue
                files.append((link, w))
            if files:
                files.sort(key=lambda x: x[1])
                cands.append(files[0][0])
        for link in cands:
            if link in skip:
                continue
            got = _download(link, dest.with_suffix(".mp4"))
            if got:
                return got, link
        if cands:
            got = _download(cands[0], dest.with_suffix(".mp4"))
            if got:
                return got, cands[0]
        return None, ""
    except (requests.RequestException, ValueError, KeyError):
        return None, ""


QUERY_SUFFIX = ["", " cinematic", " close up", " slow motion", " aerial view"]
STILLS_SUFFIX = [" portrait", " painting", " old map", " engraving", " archival photo", " bust statue"]


def fetch_scene(
    query: str,
    scene_dir: Path,
    vertical: bool,
    need_sec: float = 4.0,
    skip: set | None = None,
    page: int = 1,
) -> tuple[Path, bool, str, str]:
    skip = skip or set()
    slug = _slug(query)
    stills = config.MEDIA_MODE == "stills"
    vid_dest = scene_dir / f"{slug}.mp4"
    if vid_dest.exists() and vid_dest.stat().st_size > 20000:
        return vid_dest, True, "", ""
    dest = scene_dir / f"{slug}.jpg"
    if dest.exists() and dest.stat().st_size > 5000:
        return dest, False, "", ""
    if not stills:
        try:
            got_vid, vid_url = from_pexels_video(
                query, vertical, vid_dest, need_sec, skip, page
            )
        except Exception:
            got_vid, vid_url = None, ""
        if got_vid:
            return got_vid, True, vid_url, ""
        try:
            got_pbv, pbv_url = from_pixabay_video(
                query, vertical, vid_dest, need_sec, skip
            )
        except Exception:
            got_pbv, pbv_url = None, ""
        if got_pbv:
            return got_pbv, True, pbv_url, ""
    try:
        hit = bank_mod.find(query, skip, vertical)
    except Exception:
        hit = None
    if hit and hit.get("url"):
        if hit.get("type") == "video" and stills:
            hit = None
        else:
            dest_b = scene_dir / f"{slug}_bank"
            got = _download(hit["url"], dest_b)
            if got:
                is_vid = hit.get("type") == "video" or str(got.suffix).lower() == ".mp4"
                if got.suffix.lower() not in (".mp4", ".jpg", ".jpeg", ".png", ".webp"):
                    got.unlink(missing_ok=True)
                else:
                    return got, is_vid, hit["url"], hit.get("credit", "")
    if not stills:
        try:
            got_ar, ar_url = from_archive(query, dest, need_sec, skip)
        except Exception:
            got_ar, ar_url = None, ""
        if got_ar:
            return got_ar, True, ar_url, ""
    try:
        got_img, img_url = from_pexels(query, vertical, dest, skip, page)
    except Exception:
        got_img, img_url = None, ""
    if got_img:
        return got_img, False, img_url, ""
    try:
        got_cm, cm_url, cm_credit = from_commons(query, dest, skip)
    except Exception:
        got_cm, cm_url, cm_credit = None, "", ""
    if got_cm:
        return got_cm, False, cm_url, cm_credit
    try:
        got_nasa = from_nasa(query, dest)
    except Exception:
        got_nasa = None
    if got_nasa:
        return got_nasa, False, "", ""
    try:
        got_pb, pb_url = from_pixabay(query, dest, skip)
    except Exception:
        got_pb, pb_url = None, ""
    if got_pb:
        return got_pb, False, pb_url, ""
    placeholder = scene_dir / f"fallback_{slug}.jpg"
    if not placeholder.exists():
        _make_fallback(placeholder, query)
    return placeholder, False, "", ""


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


def fetch_all(
    scenes: list,
    cache_dir: Path,
    vertical: bool,
    scene_sec: float = 4.0,
    skip: set | None = None,
) -> list[tuple[Path, bool, str, str]]:
    skip = set(skip or set())
    suffixes = STILLS_SUFFIX if config.MEDIA_MODE == "stills" else QUERY_SUFFIX
    paths = []
    for i, s in enumerate(scenes):
        if config.kill_requested():
            raise RuntimeError("kill switch on")
        query = s["search"] + suffixes[i % len(suffixes)]
        page = 1 + (i % 3)
        p = fetch_scene(
            query, cache_dir / f"scene_{i:02d}", vertical, scene_sec, skip, page
        )
        if p[2]:
            skip.add(p[2])
        paths.append(p)
    return paths
