import gemini_client
import config


RESEARCH_PROMPT = """Content idea: "{title}"
Hook: {hook}
Beats: {beats}
Keywords: {keywords}
Niche: {niche}
Duration: about {duration} seconds, {n_scenes} scenes.

For each scene return:
- narration: 1-2 sentences of voiceover (English, factual, no fluff)
- search: one stock-media search query (English, concrete visual nouns)
- caption: on-screen caption max 12 words

Return JSON: {{"scenes":[{{"narration","search","caption"}}]}}
"""


def research(idea: dict, duration: int, scene_sec: int) -> list:
    import math

    n_scenes = max(3, math.ceil(duration / scene_sec))
    client = gemini_client.GeminiClient()
    prompt = RESEARCH_PROMPT.format(
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
