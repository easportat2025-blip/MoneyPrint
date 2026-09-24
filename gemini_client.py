import time
from google import genai
from google.genai import errors
import config
import state


class GeminiError(Exception):
    pass


class GeminiClient:
    def __init__(self, keys=None, model=None, max_retries=4):
        self.keys = list(keys or config.GEMINI_KEYS)
        if model:
            self.models = [model]
            for m in config.model_chain():
                if m not in self.models:
                    self.models.append(m)
        else:
            self.models = config.model_chain()
        self.max_retries = max_retries
        if not self.keys:
            raise GeminiError("no GEMINI keys configured")

    @staticmethod
    def _model_dead(msg: str) -> bool:
        m = msg.lower()
        return any(
            s in m
            for s in (
                "not found",
                "not supported",
                "unsupported",
                "does not exist",
                "invalid model",
                "model is not",
            )
        )

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        failures = []
        for model in self.models:
            if config.kill_requested():
                raise GeminiError("kill switch on")
            attempts = 0
            idx = 0
            while attempts < self.max_retries:
                key = self.keys[idx % len(self.keys)]
                try:
                    state.bump_gemini()
                    client = genai.Client(api_key=key)
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config={"temperature": temperature},
                    )
                    text = (resp.text or "").strip()
                    if not text:
                        raise GeminiError("empty response")
                    return text
                except errors.APIError as e:
                    code = getattr(e, "code", None)
                    if self._model_dead(str(e)):
                        failures.append(f"{model}: dead ({e})")
                        break
                    if code in (429, 503, 500, None):
                        failures.append(f"{model}: {code}")
                        idx += 1
                        attempts += 1
                        time.sleep(min(2**attempts, 30))
                        continue
                    raise GeminiError(str(e)) from e
                except Exception as e:
                    failures.append(f"{model}: {e}")
                    idx += 1
                    attempts += 1
                    time.sleep(min(2**attempts, 30))
        raise GeminiError(f"all models failed: {' | '.join(failures[-8:])}")

    def generate_json(self, prompt: str, temperature: float = 0.5):
        import json
        import re

        text = self.generate(
            prompt + "\n\nReturn ONLY valid JSON. No markdown fences, no commentary.",
            temperature=temperature,
        )
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
        start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=0)
        end = max(text.rfind("}"), text.rfind("]"))
        if end > start:
            text = text[start : end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise GeminiError(f"invalid json: {e}: {text[:300]}") from e
