import json
import time
from pathlib import Path
import requests
import config
import state

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
STATUS_URL = "https://www.googleapis.com/youtube/v3/videos"
COMMENT_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
PLAYLIST_URL = "https://www.googleapis.com/youtube/v3/playlists"
PLAYLIST_ITEM_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
CAPTION_URL = "https://www.googleapis.com/upload/youtube/v3/captions"

COST = {"captions": 400, "comment": 50, "playlist": 50, "item": 50, "thumb": 50}


def _budget(cost: int, reserve: int = 0) -> bool:
    return state.units_left(reserve) >= cost


def _spend(kind: str) -> None:
    state.spend_units(COST.get(kind, 0))


def get_access_token() -> str:
    if not (config.YOUTUBE_CLIENT_ID and config.YOUTUBE_REFRESH_TOKEN):
        raise RuntimeError(
            "YOUTUBE_CLIENT_ID / YOUTUBE_REFRESH_TOKEN missing "
            "(kiem tra Secrets: dung ten + value khong duoc rong)"
        )
    data = {
        "client_id": config.YOUTUBE_CLIENT_ID,
        "client_secret": config.YOUTUBE_CLIENT_SECRET,
        "refresh_token": config.YOUTUBE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    r = requests.post(OAUTH_TOKEN_URL, data=data, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"token refresh failed: {r.status_code} {r.text[:300]}")
    return r.json()["access_token"]


def upload(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    kind: str,
) -> dict:
    token = get_access_token()
    privacy = "public"
    category = "28"
    if kind == "short":
        tags = list({*(tags or []), "shorts", "space", "science"})
        title = title[:90]
        if "#Shorts" not in title and not description.startswith("#Shorts"):
            description = "#Shorts " + description
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:30],
            "categoryId": category,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }
    size = video_path.stat().st_size
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(size),
        "X-Upload-Content-Type": "video/mp4",
    }
    init = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
        timeout=60,
    )
    if init.status_code not in (200, 201):
        raise RuntimeError(f"resumable init failed: {init.status_code} {init.text[:400]}")
    upload_url = init.headers.get("Location")
    if not upload_url:
        raise RuntimeError("no upload Location header")

    chunk = 8 * 1024 * 1024
    offset = 0
    with open(video_path, "rb") as f:
        while True:
            if config.kill_requested():
                raise RuntimeError("kill switch on")
            data = f.read(chunk)
            if not data:
                break
            end = offset + len(data) - 1
            h = {
                "Authorization": f"Bearer {token}",
                "Content-Range": f"bytes {offset}-{end}/{size}",
                "Content-Length": str(len(data)),
                "Content-Type": "video/mp4",
            }
            r = requests.put(upload_url, headers=h, data=data, timeout=300)
            if r.status_code in (200, 201):
                result = r.json()
                return _finalize(token, result)
            if r.status_code != 308:
                raise RuntimeError(f"chunk failed: {r.status_code} {r.text[:300]}")
            offset = end + 1
            time.sleep(0.3)
    raise RuntimeError("upload ended without final response")


CAPTION_URL = "https://www.googleapis.com/upload/youtube/v3/captions"


def upload_captions(
    video_id: str, srt_path: Path, language: str = "en", name: str = "English"
) -> str:
    if not _budget(COST["captions"], reserve=200):
        return ""
    token = get_access_token()
    body = {
        "snippet": {
            "videoId": video_id,
            "language": language,
            "name": name,
            "isDraft": False,
        }
    }
    data = srt_path.read_bytes()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(len(data)),
        "X-Upload-Content-Type": "text/plain",
    }
    init = requests.post(
        CAPTION_URL,
        params={"uploadType": "resumable", "part": "snippet"},
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
        timeout=60,
    )
    if init.status_code not in (200, 201):
        raise RuntimeError(
            f"caption init failed: {init.status_code} {init.text[:300]}"
        )
    location = init.headers.get("Location")
    if not location:
        raise RuntimeError("no caption upload Location")
    r = requests.put(
        location,
        headers={"Content-Length": str(len(data))},
        data=data,
        timeout=120,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"caption put failed: {r.status_code} {r.text[:300]}")
    _spend("captions")
    return r.json().get("id", "")


THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"


def set_thumbnail(video_id: str, png_path: Path) -> bool:
    if not _budget(COST["thumb"]):
        return False
    token = get_access_token()
    data = png_path.read_bytes()
    r = requests.post(
        THUMB_URL,
        params={"videoId": video_id},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/png",
            "Content-Length": str(len(data)),
        },
        data=data,
        timeout=120,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"thumbnail failed: {r.status_code} {r.text[:300]}")
    _spend("thumb")
    return True


def insert_comment(video_id: str, text: str) -> str:
    if not _budget(COST["comment"]):
        return ""
    token = get_access_token()
    body = {"snippet": {"videoId": video_id, "textOriginal": text[:500]}}
    r = requests.post(
        COMMENT_URL,
        params={"part": "snippet"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"comment failed: {r.status_code} {r.text[:200]}")
    _spend("comment")
    return r.json().get("id", "")


def ensure_playlist(title: str) -> str:
    if not _budget(COST["playlist"]):
        return ""
    cache = config.ROOT / "playlists.json"
    try:
        data = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    if data.get(title):
        return data[title]
    token = get_access_token()
    r = requests.post(
        PLAYLIST_URL,
        params={"part": "snippet,contentDetails"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "snippet": {"title": title, "description": "Auto series - ReZain pipeline"},
            "contentDetails": {"itemOrder": "dateAdded"},
        },
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"playlist failed: {r.status_code} {r.text[:200]}")
    pid = r.json().get("id", "")
    if pid:
        data[title] = pid
        try:
            cache.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass
        _spend("playlist")
    return pid


def add_to_playlist(playlist_id: str, video_id: str) -> bool:
    if not playlist_id or not _budget(COST["item"]):
        return False
    token = get_access_token()
    r = requests.post(
        PLAYLIST_ITEM_URL,
        params={"part": "snippet"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"snippet": {"playlistId": playlist_id, "resourceId": video_id}},
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"playlistItem failed: {r.status_code} {r.text[:200]}")
    _spend("item")
    return True


def delete_video(video_id: str) -> bool:
    token = get_access_token()
    r = requests.delete(
        STATUS_URL,
        params={"id": video_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code in (200, 204):
        return True
    raise RuntimeError(f"delete failed: {r.status_code} {r.text[:300]}")


def _finalize(token: str, result: dict) -> dict:
    vid = result.get("id", "")
    url = f"https://www.youtube.com/watch?v={vid}" if vid else ""
    return {
        "youtube_id": vid,
        "youtube_url": url,
        "title": result.get("snippet", {}).get("title", ""),
    }
