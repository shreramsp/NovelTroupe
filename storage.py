"""Load/save stories as plain JSON files.

Every story has its own folder:

    data/users/<user id>/stories/<story id>/
        story.json            {title, outline, format}
        characters/<name>.json
        chapters/NN.json
        director_chat.json
        knowledge.json        who knows which secret (see agents.py "Who knows what")
        comics.json           comic episodes and each character's look
        comics/<episode>/panel_NN.jpg
        comics/_sheets/<name>_<style>.png   character reference sheets

The functions below work on the *current* story. app.py picks it with use_story(); it is
stored in a ContextVar, so every browser session (each runs in its own thread) has its own.
"""

import contextvars
import io
import json
import re
import secrets
import shutil
import time
from pathlib import Path

from PIL import Image

DATA_DIR = Path(__file__).parent / "data"
CARD_FIELDS = ["background", "wants", "fears", "contradiction", "voice", "secret"]

_story_dir = contextvars.ContextVar("story_dir", default=DATA_DIR)


def use_story(path):
    """Make `path` the story that all functions below read and write."""
    _story_dir.set(Path(path))


def _here(*parts):
    return _story_dir.get().joinpath(*parts)


def _read(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------- story ----------

def load_story():
    story = _read(_here("story.json"), {})
    return {"title": story.get("title", ""), "outline": story.get("outline", ""),
            "format": story.get("format", "novel")}


def save_story(story):
    _write(_here("story.json"), {"title": story["title"], "outline": story["outline"],
                                 "format": story.get("format", "novel")})


# ---------- the Director's chat with the author ----------

def load_director_chat():
    return _read(_here("director_chat.json"), [])


def save_director_chat(messages):
    _write(_here("director_chat.json"), messages)


# ---------- who knows what ----------

def load_knowledge():
    """{"facts": [{id, label, text, owner, events: [{who, state, chapter, how}]}], "scanned": last unit tracked}"""
    knowledge = _read(_here("knowledge.json"), {})
    return {"facts": knowledge.get("facts", []), "scanned": knowledge.get("scanned", 0)}


def save_knowledge(knowledge):
    _write(_here("knowledge.json"), knowledge)


# ---------- comics ----------

def load_comics():
    """{"looks": {name: appearance}, "episodes": [{id, title, style, chapters, created, panels: [...]}]}"""
    comics = _read(_here("comics.json"), {})
    return {"looks": comics.get("looks", {}), "episodes": comics.get("episodes", [])}


def save_comics(comics):
    _write(_here("comics.json"), comics)


def comic_image_path(episode_id, filename):
    return _here("comics", episode_id, filename)


def save_comic_image(episode_id, number, png_bytes, max_width=1100):
    """Store a drawn panel as a JPEG (smaller than the PNG the model returns). Returns its file name."""
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)), Image.LANCZOS)
    path = comic_image_path(episode_id, f"panel_{number:02d}.jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=88)
    return path.name


def _sheet_path(name, style):
    return _here("comics", "_sheets", f"{safe_name(name)}_{style}.png")


def save_comic_sheet(name, style, image_bytes, max_width=1024):
    """Store a character reference sheet as PNG (the image API takes PNG references)."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)), Image.LANCZOS)
    path = _sheet_path(name, style)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")


def load_comic_sheet(name, style):
    """PNG bytes of a character's sheet in this style, or None if it hasn't been drawn."""
    path = _sheet_path(name, style)
    return path.read_bytes() if path.exists() else None


def comic_sheet_path(name, style):
    path = _sheet_path(name, style)
    return path if path.exists() else None


def delete_comic_sheets(name):
    """Forget a character's sheets in every style (e.g. after their look changed)."""
    for path in _here("comics", "_sheets").glob(f"{safe_name(name)}_*.png"):
        path.unlink()


def delete_comic_images(episode_id):
    shutil.rmtree(_here("comics", episode_id), ignore_errors=True)


# ---------- characters ----------

def safe_name(name):
    """File-system friendly version of a character name ('' if nothing usable)."""
    return re.sub(r"[^\w\- ]", "", name).strip()


def _character_path(name):
    return _here("characters", f"{safe_name(name)}.json")


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
    folder = _here("characters")
    if not folder.exists():
        return []
    return [_fill_defaults(_read(p, {})) for p in sorted(folder.glob("*.json"))]


# ---------- chapters ----------

def save_chapter(chapter):
    _write(_here("chapters", f"{chapter['number']:02d}.json"), chapter)


def load_all_chapters():
    folder = _here("chapters")
    if not folder.exists():
        return []
    return sorted((_read(p, {}) for p in folder.glob("*.json")), key=lambda c: c["number"])


def next_chapter_number():
    chapters = load_all_chapters()
    return chapters[-1]["number"] + 1 if chapters else 1


# =====================================================================
# The library: each user's stories
# =====================================================================

STORY_ID = re.compile(r"^s_[0-9a-f]{10}$")


def _stories_dir(user_id):
    return DATA_DIR / "users" / user_id / "stories"


def find_story(user_id, story_id):
    """The folder of one of this user's stories, or None (also guards against odd ids in the URL)."""
    if not story_id or not STORY_ID.match(story_id):
        return None
    folder = _stories_dir(user_id) / story_id
    return folder if (folder / "story.json").exists() else None


def create_story(user_id, title, outline="", format_id="novel"):
    story_id = "s_" + secrets.token_hex(5)
    _write(_stories_dir(user_id) / story_id / "story.json",
           {"title": title, "outline": outline, "format": format_id})
    return story_id


def delete_story(user_id, story_id):
    if folder := find_story(user_id, story_id):
        shutil.rmtree(folder)


def list_stories(user_id):
    """Summaries of a user's stories, most recently edited first."""
    folder = _stories_dir(user_id)
    stories = []
    for path in folder.iterdir() if folder.exists() else []:
        if not find_story(user_id, path.name):
            continue
        story = _read(path / "story.json", {})
        chapters = [_read(p, {}) for p in (path / "chapters").glob("*.json")]
        files = [p for p in path.rglob("*.json")]
        stories.append({
            "id": path.name,
            "title": story.get("title") or "Untitled story",
            "outline": story.get("outline", ""),
            "format": story.get("format", "novel"),
            "places": [c.get("place") for c in chapters],
            "chapters": len(chapters),
            "characters": len(list((path / "characters").glob("*.json"))),
            "words": sum(len(c.get("text", "").split()) for c in chapters),
            "updated": max(p.stat().st_mtime for p in files) if files else time.time(),
        })
    return sorted(stories, key=lambda s: s["updated"], reverse=True)


def import_legacy_story(user_id):
    """Move a story saved by an older version of the app (directly in data/) into this user's library."""
    if not (DATA_DIR / "story.json").exists():
        return None
    story_id = "s_" + secrets.token_hex(5)
    target = _stories_dir(user_id) / story_id
    target.mkdir(parents=True)
    for name in ("story.json", "characters", "chapters", "director_chat.json"):
        if (DATA_DIR / name).exists():
            shutil.move(str(DATA_DIR / name), str(target / name))
    return story_id
