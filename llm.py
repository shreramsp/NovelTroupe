"""chat(), image() and edit_image(): the calls to Meta's API (mostly through the openai SDK)."""

import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import AuthenticationError, BadRequestError, OpenAI, PermissionDeniedError

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://api.meta.ai/v1"
MODEL = "muse-spark-1.3"
IMAGE_MODEL = "muse-image-1.0"
USAGE_LOG = Path(__file__).parent / "usage.log"
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT = 240  # seconds per attempt, so a hung request fails (and retries) instead of freezing the app


def _client():
    api_key = os.getenv("META_API_KEY")
    if not api_key:
        raise RuntimeError("META_API_KEY is not set. Copy .env.example to .env and add your key.")
    # max_retries=0: we do our own retrying in chat() so every failure is handled in one place.
    return OpenAI(api_key=api_key, base_url=BASE_URL, max_retries=0, timeout=REQUEST_TIMEOUT)


def _log_usage(usage, model=MODEL):
    if usage is None:
        return
    get = usage.get if isinstance(usage, dict) else (lambda key: getattr(usage, key, None))
    line = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        # chat calls report prompt/completion tokens; image calls report input/output tokens
        "prompt_tokens": get("prompt_tokens") or get("input_tokens"),
        "completion_tokens": get("completion_tokens") or get("output_tokens"),
        "total_tokens": get("total_tokens"),
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


def image(prompt, size="1024x1024"):
    """Draw one image with Meta's image model. Returns PNG bytes.

    size: "1024x1024" (square), "1536x1024" (wide) or "1024x1536" (tall). Retries like chat().
    """
    client = _client()
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.images.generate(model=IMAGE_MODEL, prompt=prompt, n=1, size=size)
            _log_usage(response.usage, IMAGE_MODEL)
            return base64.b64decode(response.data[0].b64_json)
        except (BadRequestError, AuthenticationError, PermissionDeniedError):
            raise
        except Exception as e:  # network error, rate limit...
            last_error = e
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"Image call failed after {MAX_ATTEMPTS} attempts: {last_error}")


def edit_image(prompt, references, size="1024x1024"):
    """Draw one image guided by reference pictures (PNG bytes), e.g. character sheets. Returns image bytes.

    Sent as a plain multipart request because the API expects the pictures as image[0], image[1], ...
    """
    api_key = os.getenv("META_API_KEY")
    if not api_key:
        raise RuntimeError("META_API_KEY is not set. Copy .env.example to .env and add your key.")
    files = [(f"image[{i}]", (f"ref{i}.png", data, "image/png")) for i, data in enumerate(references)]
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = requests.post(f"{BASE_URL}/images/edits", headers={"Authorization": f"Bearer {api_key}"},
                                     data={"model": IMAGE_MODEL, "prompt": prompt, "size": size}, files=files,
                                     timeout=REQUEST_TIMEOUT)
            if response.status_code in (400, 401, 403):
                raise ValueError(f"Image request rejected ({response.status_code}): {response.text[:300]}")
            response.raise_for_status()
            body = response.json()
            _log_usage(body.get("usage"), IMAGE_MODEL)
            return base64.b64decode(body["data"][0]["b64_json"])
        except ValueError:
            raise  # our request is wrong: retrying can't help
        except Exception as e:  # network error, rate limit...
            last_error = e
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"Image call failed after {MAX_ATTEMPTS} attempts: {last_error}")
