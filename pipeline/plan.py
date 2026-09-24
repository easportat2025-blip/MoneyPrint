import json
import gemini_client
import state
import config


IDEA_PROMPT = """You are the content strategist for a faceless English YouTube channel
about {niche} (brand: {brand}).

Generate {n} short-form (<55 seconds, vertical) video ideas that are curiosity-driven,
fact-based, and suitable for {imagery}.

Requirements:
- Titles under 70 characters, high CTR, no clickbait lies
- Each idea: hook, 3-5 key beats, 5 search keywords for stock sites
- Skip ideas already used: {used}
{exclude}
- Return JSON array: [{{"title","hook","beats":[..],"keywords":[..],"tags":[..]}}]
"""


def generate_ideas(n: int = 5) -> list:
    client = gemini_client.GeminiClient()
    used = ", ".join(sorted(state.used_titles())) or "none"
    history = "history" in config.NICHE.lower()
    if history:
        imagery = "public-domain paintings, engravings, portraits, busts, old maps, archival photos"
        exclude = "- FORBIDDEN topics: space, astronomy, planets, stars, physics, cosmic events. HUMAN history only."
    else:
        imagery = "stock footage / public-domain space imagery"
        exclude = ""
    prompt = IDEA_PROMPT.format(
        niche=config.NICHE,
        brand=config.CHANNEL_NAME,
        n=n,
        used=used,
        imagery=imagery,
        exclude=exclude,
    )
    ideas = client.generate_json(prompt, temperature=0.9)
    if isinstance(ideas, dict):
        ideas = ideas.get("ideas", [ideas])
    out = []
    for idea in ideas:
        if not isinstance(idea, dict) or not idea.get("title"):
            continue
        if idea["title"].lower() in state.used_titles():
            continue
        out.append(idea)
    return out


def next_idea(kind: str = "short") -> dict:
    from pipeline.research import research_long

    ideas = generate_ideas(5)
    if not ideas:
        raise RuntimeError("no ideas returned")
    idea = ideas[0]
    idea["kind"] = kind
    if kind == "long":
        extra = research_long(idea)
        if isinstance(extra, dict):
            idea.update(extra)
    return idea


def run(count: int = 5) -> list:
    ideas = generate_ideas(count)
    bank = []
    path = config.ROOT / "ideas.json"
    if path.exists():
        try:
            bank = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            bank = []
    titles = {i.get("title", "").lower() for i in bank}
    for idea in ideas:
        if idea["title"].lower() not in titles:
            idea["kind"] = "short"
            bank.append(idea)
            titles.add(idea["title"].lower())
    path.write_text(json.dumps(bank, indent=2, ensure_ascii=False), encoding="utf-8")
    return ideas
