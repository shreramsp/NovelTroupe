"""Load/save the story, characters and chapters as plain JSON files in data/."""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
STORY_FILE = DATA_DIR / "story.json"
CHARACTERS_DIR = DATA_DIR / "characters"
CHAPTERS_DIR = DATA_DIR / "chapters"

CARD_FIELDS = ["background", "wants", "fears", "contradiction", "voice", "secret"]


def _read(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------- story ----------

def load_story():
    story = _read(STORY_FILE, {})
    return {"title": story.get("title", ""), "outline": story.get("outline", "")}


def save_story(story):
    _write(STORY_FILE, {"title": story["title"], "outline": story["outline"]})


# ---------- the Director's chat with the author ----------

DIRECTOR_CHAT_FILE = DATA_DIR / "director_chat.json"


def load_director_chat():
    return _read(DIRECTOR_CHAT_FILE, [])


def save_director_chat(messages):
    _write(DIRECTOR_CHAT_FILE, messages)


# ---------- characters ----------

def safe_name(name):
    """File-system friendly version of a character name ('' if nothing usable)."""
    return re.sub(r"[^\w\- ]", "", name).strip()


def _character_path(name):
    return CHARACTERS_DIR / f"{safe_name(name)}.json"


def character_exists(name):
    return bool(safe_name(name)) and _character_path(name).exists()


def new_character(name, card=None):
    card = card or {}
    return {
        "name": name,
        "card": {field: card.get(field, "") for field in CARD_FIELDS},
        "profile_updates": [],
        "memories": [],
        "chat_history": [],
    }


def _fill_defaults(raw):
    char = new_character(raw["name"], raw.get("card"))
    for key in ("profile_updates", "memories", "chat_history"):
        char[key] = raw.get(key, [])
    return char


def load_character(name):
    return _fill_defaults(_read(_character_path(name), {"name": name}))


def save_character(character):
    if not safe_name(character["name"]):
        raise ValueError("Character name is empty or has no usable characters.")
    _write(_character_path(character["name"]), character)


def load_all_characters():
    if not CHARACTERS_DIR.exists():
        return []
    chars = [_fill_defaults(_read(p, {})) for p in sorted(CHARACTERS_DIR.glob("*.json"))]
    return chars


# ---------- chapters ----------

def _chapter_path(number):
    return CHAPTERS_DIR / f"{number:02d}.json"


def save_chapter(chapter):
    _write(_chapter_path(chapter["number"]), chapter)


def load_all_chapters():
    if not CHAPTERS_DIR.exists():
        return []
    chapters = [_read(p, {}) for p in CHAPTERS_DIR.glob("*.json")]
    return sorted(chapters, key=lambda c: c["number"])


def next_chapter_number():
    chapters = load_all_chapters()
    return chapters[-1]["number"] + 1 if chapters else 1
