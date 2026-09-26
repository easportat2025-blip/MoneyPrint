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
- narration: 1-2 sentences of voiceover (English, factual, no fluff)
- search: one stock-media search query (English, concrete visual nouns,
  match the MOOD: dark, vast, dramatic)
- caption: on-screen caption max 12 words

Return JSON: {{"scenes":[{{"narration","search","caption"}}]}}
"""


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


def research(idea: dict, duration: int, scene_sec: int) -> list:
    import math

    n_scenes = max(3, math.ceil(duration / scene_sec))
    client = gemini_client.GeminiClient()
    niche = config.NICHE.lower()
    history = "history" in niche
    lifestyle = ("everyday life" in niche) or ("animation" in niche)
    rules = (
        HISTORY_RULES
        if history
        else (LIFESTYLE_RULES if lifestyle else SCIENCE_RULES)
    )
    prompt = RESEARCH_PROMPT.format(
        HISTORY_RULES=rules,
        title=idea.get("title", ""),
        hook=idea.get("hook", ""),
        beats=json_dumps(idea.get("beats", [])),
        keywords=json_dumps(idea.get("keywords", [])),
        niche=config.NICHE,
        duration=duration,
        n_scenes=n_scenes,
    )
    data = client.generate_json(prompt, temperature=0.6)
    scenes = data.get("scenes", data if isinstance(data, list) else [])
    clean = []
    for s in scenes[:n_scenes]:
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
    if not clean:
        raise RuntimeError("research returned no scenes")
    return clean


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
