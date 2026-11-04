"""One function, chat(), that talks to Meta's API through the openai SDK."""

import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import AuthenticationError, BadRequestError, OpenAI, PermissionDeniedError

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://api.meta.ai/v1"
MODEL = "muse-spark-1.3"
USAGE_LOG = Path(__file__).parent / "usage.log"
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT = 240  # seconds per attempt, so a hung request fails (and retries) instead of freezing the app


def _client():
    api_key = os.getenv("META_API_KEY")
    if not api_key:
        raise RuntimeError("META_API_KEY is not set. Copy .env.example to .env and add your key.")
    # max_retries=0: we do our own retrying in chat() so every failure is handled in one place.
    return OpenAI(api_key=api_key, base_url=BASE_URL, max_retries=0, timeout=REQUEST_TIMEOUT)


def _log_usage(usage):
    if usage is None:
        return
    line = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
    with USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def chat(messages, json_schema=None):
    """Send chat messages to the model.

    messages:    list of {"role": "system" | "user" | "assistant", "content": str}
    json_schema: optional JSON Schema dict. When given, the model is asked for JSON
                 matching it and the parsed result (dict/list) is returned instead of text.

    Retries up to MAX_ATTEMPTS times on API errors or unparseable JSON.
    """
    client = _client()
    kwargs = {"model": MODEL, "messages": messages}
    if json_schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "response", "strict": True, "schema": json_schema},
        }

    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.chat.completions.create(**kwargs)
            _log_usage(response.usage)  # log even if the JSON below turns out to be bad
            text = response.choices[0].message.content or ""
            return json.loads(text) if json_schema is not None else text
        except (BadRequestError, AuthenticationError, PermissionDeniedError):
            raise  # our request is wrong or the key is bad: retrying can't help
        except Exception as e:  # network error, rate limit, bad JSON...
            last_error = e
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(2**attempt)  # 1s, 2s
    raise RuntimeError(f"LLM call failed after {MAX_ATTEMPTS} attempts: {last_error}")
