import gemini_client
import config


RESEARCH_PROMPT = """Content idea: "{title}"
Hook: {hook}
Beats: {beats}
Keywords: {keywords}
Niche: {niche}
Duration: about {duration} seconds, {n_scenes} scenes.

Structure the scenes as a retention arc:
- Scene 1 = HOOK: the core question/claim in under 10 words, curiosity gap
  or number or contradiction. NO greetings, NO setup.
- Middle scenes = OPEN LOOP then ESCALATE: raise tension, add stakes,
  partial evidence. Never resolve early.
- Last scene = PAYOFF: clear resolution near the end (drives replays).
{HISTORY_RULES}

For each scene return:
- narration: 1-2 sentences of voiceover ({lang}, factual, no fluff)
- search: one stock-media search query ({search_lang}, concrete visual nouns).
  Describe what is literally ON SCREEN. Every scene MUST have a DIFFERENT
  search string - never repeat the same query across scenes.
- caption: on-screen caption max 12 words

Return JSON: {{"scenes":[{{"narration","search","caption"}}]}}
"""

# KHONG duoc dung "dark, vast, dramatic" o prompt chung. Cau do day day
# Gemini xuat "dark space stars galaxy cosmos nebula" cho ca 13 scene cua
# video ve anh sang xanh man hinh tivi.


HISTORY_RULES = """HISTORY MODE (strict):
- STRICTLY HUMAN history: empires, wars, rulers, figures, civilizations,
  artifacts, historical events. NEVER astronomy, space, planets, stars,
  physics, or cosmic topics (even "historical" ones like old supernovae).
- Arc: CONSEQUENCE (why it still matters) -> CONTEXT (place, date) ->
  DECISION (the pivotal action) -> RESULT -> LEGACY (return to opening).
- search queries must match the ERA honestly: oil painting / engraving /
  manuscript / old map for anything before 1840; archival photograph /
  newspaper only after 1840. Add the medium IN the query
  (e.g. "napoleon oil painting", "ww2 archival photo", "roman map engraving").
- Precise names + dates in narration. Never invent private thoughts,
  quotes, or dialogue for historical figures.
- When narration names a PERSON, search must target their likeness:
  "X portrait painting" / "X bust statue" / "X coin" (face close-up
  beats landscapes for figure episodes). Label reconstructions as
  illustration in caption, never as authentic photo."""

LIFESTYLE_RULES = """EVERYDAY-LIFE MODE (strict):
- Topics must be things people do daily: sleep, food, money, phone habits,
  body, brain, eyes, posture, hydration, temperature, screens, driving.
- NO space, NO astronomy, NO ancient wars/history, NO royal figures.
- search queries must look for MOTION footage, prefer animated/stylized:
  "3d animation", "motion graphics", "loop animation", "isometric render",
  "explainer animation", "cartoony 3d". Concretely show everyday objects
  (phone, bed, coffee, mirror, money, food, screen) - not landscapes.
- Curiosities of daily life, not generic self-help advice. Numbers beat
  adjectives. Hook = one surprising number or contradiction about the body
  or an everyday object."""

SCIENCE_RULES = ""


BATCH = 8


def _one_batch(client, base: dict, take: int, offset: int, total: int, prev: list) -> list:
    first = offset == 0
    last = offset + take >= total
    if first:
        role = "Scene 1 = HOOK (core question/claim under 10 words, no greetings). Others = OPEN LOOP."
    elif last:
        role = "Keep escalating, then the FINAL scene = PAYOFF (clear resolution, drives replays)."
    else:
        role = "Middle scenes = OPEN LOOP then ESCALATE. Never resolve early."
    ctx = ""
    if prev:
        ctx = "Previous scenes ended with:\n" + "\n".join(
            f"- {s['narration']}" for s in prev[-2:]
        )
    prompt = RESEARCH_PROMPT.format(
        HISTORY_RULES=base["rules"],
        lang=base["lang"],
        search_lang=base["search_lang"],
        title=base["title"],
        hook=base["hook"],
        beats=base["beats"],
        keywords=base["keywords"],
        niche=base["niche"],
        duration=base["duration"],
        n_scenes=take,
    )
    prompt += (
        f"\nThis is part {offset // BATCH + 1}: write scenes {offset + 1} to "
        f"{offset + take} of {total} total.\n{role}\n{ctx}"
    )
    data = client.generate_json(prompt, temperature=0.6)
    scenes = data.get("scenes", data if isinstance(data, list) else [])
    clean = []
    for s in scenes[:take]:
        if not isinstance(s, dict):
            continue
        narration = (s.get("narration") or "").strip()
        search = (s.get("search") or "").strip()
        if narration and search:
            clean.append(
                {
                    "narration": narration,
                    "search": search,
                    "caption": (s.get("caption") or "").strip(),
                }
            )
    return clean


def _niche_mode() -> str:
    """history | lifestyle | general.

    Phai lay theo CHANNEL, khong do chuoi trong NICHE: niche cua acc 3 viet
    bang tieng Viet ("doi song tieng Viet... hoat hinh") nen ham "everyday
    life" / "animation" khong bao gio khop -> slot 3 im lang dung LIFESTYLE_RULES
    va roi vao prompt chung.
    """
    explicit = config.env("NICHE_MODE", "").strip().lower()
    if explicit in ("history", "lifestyle", "general"):
        return explicit
    by_slot = {"1": "general", "2": "history", "3": "lifestyle"}
    mode = by_slot.get(config.CHANNEL, "")
    if mode:
        return mode
    niche = config.NICHE.lower()
    if "history" in niche:
        return "history"
    if "everyday life" in niche or "animation" in niche or "hoat hinh" in niche:
        return "lifestyle"
    return "general"


def research(idea: dict, duration: int, scene_sec: int) -> list:
    import math

    n_scenes = max(3, math.ceil(duration / scene_sec))
    client = gemini_client.GeminiClient()
    mode = _niche_mode()
    rules = {
        "history": HISTORY_RULES,
        "lifestyle": LIFESTYLE_RULES,
        "general": SCIENCE_RULES,
    }[mode]
    base = {
        "rules": rules,
        "lang": config.LANG_NAME,
        "search_lang": "Vietnamese, no diacritics" if config.LANG == "vi" else "English",
        "title": idea.get("title", ""),
        "hook": idea.get("hook", ""),
        "beats": json_dumps(idea.get("beats", [])),
        "keywords": json_dumps(idea.get("keywords", [])),
        "niche": config.NICHE,
        "duration": duration,
    }
    out: list = []
    offset = 0
    while offset < n_scenes:
        take = min(BATCH, n_scenes - offset)
        got = _one_batch(client, base, take, offset, n_scenes, out)
        if not got:
            if not out:
                raise RuntimeError("research returned no scenes")
            break
        out.extend(got)
        offset += len(got)
        if len(got) < take:
            break
    _diversify(out, idea)
    return out


def _diversify(scenes: list, idea: dict) -> None:
    """Scene nao trung query voi scene truoc -> gan query rieng tu caption.

    Gemini thinh thoang tra ve cung mot cum tu khoa cho ca loat scene. Hinh
    anh lap lai 13 lan thi nguoi xem chay ngay giay 3. Day la nguyen nhac
    video nao cung rut gon nhu nhau.
    """
    used_q: set[str] = set()
    used_kw: set[str] = set()
    fallback = [
        "close up", "wide shot", "slow motion", "handheld", "low angle",
        "detail view", "over the shoulder", "timelapse",
    ]
    for i, s in enumerate(scenes):
        q = " ".join((s.get("search") or "").lower().split())
        if q in used_q:
            picked = None
            for cand in _keywords_from(s, idea, used_kw):
                used_kw.add(cand)
                picked = cand
                break
            if picked is None:
                picked = fallback[i % len(fallback)]
            s["search"] = f"{s['search']} {picked}".strip()
            q = " ".join(s["search"].lower().split())
        else:
            for cand in _keywords_from(s, idea, used_kw)[:2]:
                used_kw.add(cand)
        used_q.add(q)


_VN_STOP = {
    "khong", "nguoi", "mot", "giac", "dung", "lam", "voi", "cua", "cho", "the",
    "trong", "nen", "bi", "va", "co", "la", "cac", "nhung", "khi", "thi", "de",
    "nay", "do", "ra", "se", "ma", "thi", "nen", "hon", "nhu", "voi", "thanh",
    "hieu", "biet", "khac", "nhieu", "it", "rat", "cung", "da", "duoc",
}


def _norm(w: str) -> str:
    import unicodedata

    w = "".join(
        c
        for c in unicodedata.normalize("NFD", w.lower())
        if unicodedata.category(c) != "Mn"
    )
    return "".join(c for c in w if c.isalnum() or c.isspace())


def _keywords_from(scene: dict, idea: dict, used: set) -> list:
    """Lay tu khoa rieng cho tung scene tu caption + keywords cua idea."""
    pool = [str(k) for k in (idea.get("keywords") or [])]
    words = str(scene.get("caption") or "").split()
    out = []
    for raw in words + pool:
        w = "".join(c for c in raw if c.isalnum() or c.isspace()).strip()
        low = _norm(w)
        if len(low) < 5 or low in _VN_STOP or low in used:
            continue
        used.add(low)
        out.append(low)
    return out


def research_long(idea: dict) -> dict:
    client = gemini_client.GeminiClient()
    prompt = f"""Expand this long-form YouTube idea into a full outline (video >5 minutes,
English, {config.NICHE}): {idea.get('title')}
Hook: {idea.get('hook')}
Beats: {json_dumps(idea.get('beats', []))}

Return JSON: {{"title","hook","beats":[8-14 items],"keywords":[8-12],"tags":[8-12],
"thumbnail_text":"max 30 chars"}}
"""
    data = client.generate_json(prompt, temperature=0.7)
    if isinstance(data, dict):
        return data
    return {}


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)
