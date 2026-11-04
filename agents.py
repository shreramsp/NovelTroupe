"""The story agents.

All prompts live in the constants at the top of this file, so you can tune them
without touching any code. Every prompt is filled in with str.format(), so
avoid literal curly braces inside them.

Chapter generation is split in two so the author can rule on objections
before anything is saved:

    draft_chapter()   plan the scene, collect every character's reaction (nothing saved)
    finish_chapter()  rewrite accepted beats, write the text, update memories, save

generate_chapter() runs both in one go (unresolved objections are overridden).

Data shapes
-----------
story:      {"title": str, "outline": str}
character:  {"name", "card": {...}, "profile_updates": [], "memories": [], "chat_history": []}
beat:       {"text": str, "characters": [names who see/hear it]}
chapter:    {"number", "instruction", "plan", "reactions", "text", "summary", "present", "objections"}
"""

import base64
import copy

import llm
import storage

# =====================================================================
# PROMPTS - tune these
# =====================================================================

# Who a character is. Used for chatting with them AND for their reactions to a plan.
CHARACTER_IDENTITY = """You ARE {name}. You are a real person, not an assistant.

WHO YOU ARE
{card}

{profile}

{memories}"""

CHARACTER_REPLY_RULES = """RULES
- Stay in character, even over being helpful. Never mention being an AI, a model, a character or a story.
- You only know what is written above (who you are, how you have changed, what you remember). Anything else - scenes you were not in, other people's private thoughts, events that never happened to you - you do NOT know. Say so in your own way, deflect, or make a guess that is clearly just a guess. Never state it as fact.
- Speak in your own voice, exactly as described above.
- You can be stubborn, rude, evasive, or simply wrong. You do not have to be agreeable, and you do not have to give up your secret.
- Answer the way you would speak out loud: usually a few sentences."""

# plan_scene - the DIRECTOR plans the chapter.
DIRECTOR_PLAN_PROMPT = """You are the DIRECTOR of a serialized story. Plan the next chapter as a short list of beats.

STORY: {title}

OUTLINE
{outline}

PREVIOUS CHAPTERS (summaries)
{summaries}

CHARACTERS (you know everything about them)
{characters}

THE AUTHOR'S INSTRUCTION FOR THIS CHAPTER - follow it above everything else
{instruction}

Write 4 to 7 beats, in order. Each beat is one or two sentences about what happens. For each beat, list in "characters" exactly who is there to see or hear it. A character who is not listed in a beat will never know it happened, so choose deliberately. Use character names exactly as written above. "present" is everyone who appears in at least one beat."""

# character_reaction - one call per present character. Gets the character identity above plus this.
REACTION_RULES = """The director has planned some scenes. Here are the beats YOU will be part of (you know nothing about any other beat):

{beats}

React as yourself.
- "reaction": 2 to 4 sentences, in first person and in your own voice: how you feel about these scenes and what you intend to do in them.
- "objection": fill this in ONLY if a beat would make you do or say something that contradicts who you have become (your background, how you have changed, what you remember). Merely disliking a beat, or finding it hard, is not an objection. Write it in your own voice, as if arguing with the author. Otherwise null.
- "beat": the number of the beat you object to, or null if you have no objection."""

# rewrite_beat - used when the author ACCEPTS an objection.
REWRITE_BEAT_PROMPT = """You are the DIRECTOR of a serialized story. A character has objected to one beat of the plan, and the author has agreed with them.

ALL BEATS
{beats}

THE AUTHOR'S INSTRUCTION FOR THE CHAPTER
{instruction}

{character} OBJECTS TO BEAT {number}
{objection}

Rewrite beat {number} so {character} is no longer asked to act against who they are. Keep as much as you can of what the beat was for in the chapter and of the author's instruction. Keep it to one or two sentences, and do not change who is present. Return only the new beat text."""

# write_chapter_text - the DIRECTOR writes the chapter.
WRITER_PROMPT = """You are the DIRECTOR of a serialized story, now writing the chapter itself.

STORY: {title}

OUTLINE
{outline}

THE AUTHOR'S INSTRUCTION - respect this above everything else
{instruction}

CHARACTERS IN THIS CHAPTER
{characters}

BEATS (write them in this order)
{beats}

HOW EACH CHARACTER REACTED
{reactions}

Write the chapter: about 1200 words of polished prose in the third person, past tense, as a scene or a short run of scenes.
- Hit every beat. Do not add major events that are not in the beats.
- Keep each character's reaction and voice: their dialogue and choices must sound like them.
- Where a character objected and the author overrode it, the beat still happens, but show their resistance or reluctance.
- Do not reveal a character's secret unless a beat does.
- Only the characters listed for a beat are there for it.
- Output only the chapter text: no title, no headings, no notes."""

# update_memory - what did each character live through?
MEMORY_PROMPT = """Read this chapter and work out what each character takes away from it.

CHARACTERS TO CONSIDER
{characters}

CHAPTER TEXT
{chapter_text}

Return:
- "title": a short, evocative chapter title (2 to 5 words), like one in a published novel.
- "summary": 2 to 4 neutral sentences saying what happened in the chapter.
- "present": the names of the characters (from the list above) who were actually in the scene and saw or heard what happened. Someone who is only mentioned or talked about is NOT present.
- "per_character": one entry for each present character only:
  - "new_memory": 1 to 3 sentences, from that character's own point of view, of what THEY personally saw, heard, said and did. Include only what they witnessed. Never include anything from a scene they were not in, or anything they could not have known.
  - "profile_change": one sentence if this chapter really changed who they are (a belief, a goal, a fear, a relationship), otherwise null."""

# transcribe - turns the author's voice recording into text.
TRANSCRIBE_PROMPT = """You are a speech-to-text engine. The user message contains an audio recording, and you can hear it. Write down exactly what is said, word for word. Output only the transcript.
Names that may come up: {names}."""

# route_command - the DIRECTOR in the chat panel: answers the author, or works out what they want done.
ROUTER_PROMPT = """You are the DIRECTOR, the author's creative partner inside a story-writing app. You know everything about the story.

STORY: {title}

OUTLINE
{outline}

CHAPTERS SO FAR
{summaries}

CHARACTERS (current cards)
{characters}

CURRENTLY OPEN IN THE APP: {open_view}

RECENT CONVERSATION WITH THE AUTHOR
{history}

THE AUTHOR JUST SAID
{text}

Choose exactly one action:
- "discuss": the author wants to talk with you: brainstorm, get advice, ask about the story or a chapter. Put your full answer in "reply": specific, warm and useful, at most a few short paragraphs.
- "ask_character": the author is talking to a character or asking them something ("Hey Hale, what did you tell Nora?"). Set "character" to their exact name and "message" to what to say to them, in the author's words but without the greeting or name.
- "chapter_instruction": the author is describing what should happen in the next chapter. Set "instruction" to a clear, complete instruction for the chapter, keeping every detail the author gave.
- "edit_character": the author is giving new facts about an EXISTING character ("Park walks with a limp now"). Set "character", and in "card" give the FULL new text of each field that should change: keep what the field already says and work the new fact in. Fields that do not change are null.
- "new_character": the author is describing a character who is not in the list. Set "character" to the new name and fill every "card" field you can from what they said (null if they said nothing about it).
- "unclear": you cannot tell what they want, or a character name matches no one. Set "reply" to one short, friendly question.

For actions other than "discuss", "reply" is one short sentence telling the author what you did. Every field that does not apply is null."""

# =====================================================================
# JSON SCHEMAS for llm.chat(json_schema=...)
# =====================================================================

_NULLABLE_TEXT = {"type": ["string", "null"]}

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string",
                   "enum": ["discuss", "ask_character", "chapter_instruction", "edit_character", "new_character",
                            "unclear"]},
        "character": _NULLABLE_TEXT,
        "message": _NULLABLE_TEXT,
        "instruction": _NULLABLE_TEXT,
        "card": {
            "type": "object",
            "properties": {field: _NULLABLE_TEXT for field in storage.CARD_FIELDS},
            "required": storage.CARD_FIELDS,
            "additionalProperties": False,
        },
        "reply": {"type": "string"},
    },
    "required": ["action", "character", "message", "instruction", "card", "reply"],
    "additionalProperties": False,
}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "characters"],
                "additionalProperties": False,
            },
        },
        "present": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["beats", "present"],
    "additionalProperties": False,
}

REACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "reaction": {"type": "string"},
        "objection": {"type": ["string", "null"]},
        "beat": {"type": ["integer", "null"]},
    },
    "required": ["reaction", "objection", "beat"],
    "additionalProperties": False,
}

REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}

MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "present": {"type": "array", "items": {"type": "string"}},
        "per_character": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "new_memory": {"type": "string"},
                    "profile_change": {"type": ["string", "null"]},
                },
                "required": ["name", "new_memory", "profile_change"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "summary", "present", "per_character"],
    "additionalProperties": False,
}

# =====================================================================
# Small helpers for building prompt text
# =====================================================================

CHAT_HISTORY_LIMIT = 10  # messages of chat history sent to a character


def _card_text(character):
    return "\n".join(f"{field.capitalize()}: {value}" for field, value in character["card"].items() if value)


def _identity(character):
    """The 'You ARE <name>' block with the character's card, profile updates and memories."""
    updates = character["profile_updates"]
    profile = ("HOW YOU HAVE CHANGED\n" + "\n".join(f"- {u['text']}" for u in updates)) if updates else ""
    memories = character["memories"]
    if memories:
        memory_text = "WHAT YOU REMEMBER (everything you know about recent events)\n" + "\n".join(
            f"- (chapter {m['chapter']}) {m['text']}" for m in memories
        )
    else:
        memory_text = "WHAT YOU REMEMBER\nNothing in particular about recent events."
    return CHARACTER_IDENTITY.format(name=character["name"], card=_card_text(character),
                                     profile=profile, memories=memory_text)


def _beats_text(beats, only_for=None):
    """Numbered beats. With only_for=<name>, only the beats that character is part of."""
    lines = []
    for number, beat in enumerate(beats, start=1):
        if only_for is not None and only_for not in beat["characters"]:
            continue
        others = [n for n in beat["characters"] if n != only_for]
        who = f" (with: {', '.join(others)})" if only_for and others else ""
        if only_for is None:
            who = f" (present: {', '.join(beat['characters'])})"
        lines.append(f"Beat {number}: {beat['text']}{who}")
    return "\n".join(lines)


def _director_view(character):
    """What the director knows about a character: card plus how they have changed."""
    text = f"{character['name']}\n{_card_text(character)}"
    for update in character["profile_updates"]:
        text += f"\nChanged (chapter {update['chapter']}): {update['text']}"
    return text


# =====================================================================
# The agents
# =====================================================================

def character_reply(character, message):
    """Answer the author's chat message in the character's voice, and save the exchange."""
    system = _identity(character) + "\n\n" + CHARACTER_REPLY_RULES
    history = character["chat_history"][-CHAT_HISTORY_LIMIT:]
    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": message}]

    reply = llm.chat(messages).strip()

    character["chat_history"].append({"role": "user", "content": message})
    character["chat_history"].append({"role": "assistant", "content": reply})
    storage.save_character(character)
    return reply


def plan_scene(story, chapters, instruction):
    """The DIRECTOR plans the chapter. Returns {"beats": [{text, characters}], "present": [names]}."""
    characters = storage.load_all_characters()
    names = {c["name"] for c in characters}
    summaries = "\n".join(f"Chapter {c['number']}: {c['summary']}" for c in chapters) or "(none - this is chapter 1)"

    prompt = DIRECTOR_PLAN_PROMPT.format(
        title=story["title"],
        outline=story["outline"],
        summaries=summaries,
        characters="\n\n".join(_director_view(c) for c in characters),
        instruction=instruction,
    )
    plan = llm.chat([{"role": "user", "content": prompt}], json_schema=PLAN_SCHEMA)

    # Drop names the model invented, and make "present" match the beats.
    beats = [{"text": b["text"], "characters": [n for n in b["characters"] if n in names]} for b in plan["beats"]]
    in_beats = {n for b in beats for n in b["characters"]}
    present = [c["name"] for c in characters if c["name"] in in_beats or c["name"] in plan["present"]]
    if not beats or not present:
        raise ValueError("The director returned a plan with no beats or no known characters. Try again.")
    return {"beats": beats, "present": present}


def character_reaction(character, plan):
    """One character reacts to the beats THEY are part of. Returns {reaction, objection, beat}.

    `objection` is None unless a beat contradicts who they have become; `beat` is then the
    (1-based) number of that beat in plan["beats"].
    """
    name = character["name"]
    visible = [i for i, b in enumerate(plan["beats"], start=1) if name in b["characters"]]
    if not visible:
        return {"reaction": "", "objection": None, "beat": None}

    system = _identity(character) + "\n\n" + REACTION_RULES.format(beats=_beats_text(plan["beats"], only_for=name))
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": "Give your reaction to these scenes now."}]
    result = llm.chat(messages, json_schema=REACTION_SCHEMA)

    objection = (result["objection"] or "").strip() or None
    beat = result["beat"] if result["beat"] in visible else visible[0]  # fall back to their first beat
    return {"reaction": result["reaction"], "objection": objection, "beat": beat if objection else None}


def rewrite_beat(plan, instruction, character, objection, number):
    """Rewrite one beat (1-based `number`) after the author accepts a character's objection."""
    prompt = REWRITE_BEAT_PROMPT.format(
        beats=_beats_text(plan["beats"]), instruction=instruction,
        character=character, number=number, objection=objection,
    )
    return llm.chat([{"role": "user", "content": prompt}], json_schema=REWRITE_SCHEMA)["text"].strip()


def write_chapter_text(story, plan, reactions, instruction=""):
    """The DIRECTOR writes the chapter (~1200 words) from the beats and the characters' reactions."""
    present = [c for c in storage.load_all_characters() if c["name"] in plan["present"]]

    lines = []
    for name, r in reactions.items():
        line = f"{name}: {r['reaction']}"
        if r.get("objection"):
            outcome = {"overridden": "the author OVERRODE this - the beat stays as written",
                       "accepted": "the author ACCEPTED this - the beat was rewritten"}.get(r.get("objection_status"), "")
            line += f"\n  {name} objected: {r['objection']} ({outcome})"
        lines.append(line)

    prompt = WRITER_PROMPT.format(
        title=story["title"],
        outline=story["outline"],
        instruction=instruction or "(none given - follow the beats)",
        characters="\n\n".join(_director_view(c) for c in present),
        beats=_beats_text(plan["beats"]),
        reactions="\n".join(lines),
    )
    return llm.chat([{"role": "user", "content": prompt}]).strip()


def update_memory(chapter_text, characters):
    """Work out what happened and what each character in `characters` personally lived through.

    Returns {"title", "summary", "present", "per_character": {name: {"new_memory", "profile_change"}}}.
    Only characters who were actually present end up in `present` and `per_character`.
    """
    names = [c["name"] for c in characters]
    prompt = MEMORY_PROMPT.format(
        characters="\n\n".join(_director_view(c) for c in characters),
        chapter_text=chapter_text,
    )
    result = llm.chat([{"role": "user", "content": prompt}], json_schema=MEMORY_SCHEMA)

    present = [n for n in names if n in result["present"]]
    per_character = {
        entry["name"]: {"new_memory": entry["new_memory"], "profile_change": entry["profile_change"]}
        for entry in result["per_character"]
        if entry["name"] in present
    }
    return {"title": result["title"], "summary": result["summary"], "present": present,
            "per_character": per_character}


# =====================================================================
# Voice and the command bar
# =====================================================================

def transcribe(audio_bytes, audio_format="wav", names=()):
    """Speech -> text. Meta's chat model accepts audio directly, so this is a normal chat call.

    `names` (character names) help the model spell them right. The model now and then claims it
    "can't hear audio", so we retry a couple of times before giving up.
    """
    messages = [
        {"role": "system", "content": TRANSCRIBE_PROMPT.format(names=", ".join(names) or "none")},
        {"role": "user", "content": [{"type": "input_audio", "input_audio": {
            "data": base64.b64encode(audio_bytes).decode(), "format": audio_format}}]},
    ]
    for _ in range(3):
        text = llm.chat(messages).strip()
        lowered = text.lower()
        refused = "audio" in lowered and any(w in lowered for w in ("can't", "cannot", "unable", "no "))
        if text and not refused:
            return text
    raise ValueError("Sorry, I didn't catch that. Please try recording again.")


def route_command(text, story, chapters, characters, history=(), open_character=None):
    """The Director's turn in the chat: answer, or work out what the author wants done.

    Returns {"action", "character", "message", "instruction", "card": {field: str|None}, "reply"}.
    action is one of: discuss, ask_character, chapter_instruction, edit_character, new_character, unclear.
    """
    names = {c["name"] for c in characters}
    recent = "\n".join(f"{'Author' if m['role'] == 'user' else 'Director'}: {m['content']}"
                       for m in list(history)[-CHAT_HISTORY_LIMIT:])
    prompt = ROUTER_PROMPT.format(
        title=story["title"],
        outline=story["outline"],
        summaries="\n".join(f"Chapter {c['number']}: {c['summary']}" for c in chapters) or "(no chapters yet)",
        characters="\n\n".join(_director_view(c) for c in characters) or "(no characters yet)",
        open_view=f"the character {open_character}" if open_character else "nothing in particular",
        history=recent or "(this is the start of the conversation)",
        text=text,
    )
    result = llm.chat([{"role": "user", "content": prompt}], json_schema=ROUTER_SCHEMA)

    # Don't trust names blindly: an ask/edit must point at a real character.
    if result["action"] in ("ask_character", "edit_character") and result["character"] not in names:
        result["action"] = "unclear"
        result["reply"] = f"I couldn't tell which character you meant. Try starting with their name ({', '.join(sorted(names))})."
    if result["action"] == "new_character" and (not result["character"] or result["character"] in names):
        result["action"] = "unclear"
        result["reply"] = "That character already exists, or I didn't catch a name for the new one."
    return result


# =====================================================================
# Putting it together
# =====================================================================

def draft_chapter(story, chapters, characters, instruction):
    """Steps 1-2: plan the scene and gather reactions. Saves NOTHING.

    Returns a draft {instruction, plan, reactions, objections}. Each objection is
    {character, beat, objection, status: "pending"}; set status to "accepted" or
    "overridden", then pass the draft to finish_chapter().
    """
    by_name = {c["name"]: c for c in characters}
    plan = plan_scene(story, chapters, instruction)
    reactions = {name: character_reaction(by_name[name], plan) for name in plan["present"] if name in by_name}
    objections = [
        {"character": name, "beat": r["beat"], "objection": r["objection"], "status": "pending"}
        for name, r in reactions.items()
        if r["objection"]
    ]
    return {"instruction": instruction, "plan": plan, "reactions": reactions, "objections": objections}


def finish_chapter(story, characters, draft):
    """Steps 3-5: rewrite accepted beats, write the text, update memories, and save everything.

    Objections still "pending" are treated as overridden. Returns the saved chapter.
    """
    by_name = {c["name"]: c for c in characters}
    plan = copy.deepcopy(draft["plan"])
    reactions = copy.deepcopy(draft["reactions"])
    objections = [dict(o, status="overridden" if o["status"] == "pending" else o["status"])
                  for o in draft["objections"]]

    for o in objections:
        reactions[o["character"]]["objection_status"] = o["status"]
        if o["status"] == "accepted":  # Accept rewrites that beat; Override keeps it.
            plan["beats"][o["beat"] - 1]["text"] = rewrite_beat(
                plan, draft["instruction"], o["character"], o["objection"], o["beat"])

    text = write_chapter_text(story, plan, reactions, draft["instruction"])

    # Memory: only characters the model confirms were present in the written chapter
    # (and who were in the plan) learn anything.
    planned = [by_name[n] for n in plan["present"] if n in by_name]
    memory = update_memory(text, planned)

    number = storage.next_chapter_number()
    chapter = {
        "number": number,
        "instruction": draft["instruction"],
        "plan": plan,
        "reactions": reactions,
        "title": memory["title"],
        "text": text,
        "summary": memory["summary"],
        "present": memory["present"],
        "objections": objections,
    }
    _save_with_memories(chapter, memory, by_name)
    return chapter


def add_author_chapter(characters, text):
    """Save a chapter the author wrote themselves, and update what each character remembers."""
    by_name = {c["name"]: c for c in characters}
    memory = update_memory(text, characters)
    chapter = {
        "number": storage.next_chapter_number(),
        "title": memory["title"],
        "instruction": "(written by the author)",
        "plan": {"beats": [], "present": memory["present"]},
        "reactions": {},
        "text": text,
        "summary": memory["summary"],
        "present": memory["present"],
        "objections": [],
    }
    _save_with_memories(chapter, memory, by_name)
    return chapter


def _save_with_memories(chapter, memory, by_name):
    """Save the chapter, then give each PRESENT character their new memory and profile change."""
    number = chapter["number"]
    storage.save_chapter(chapter)
    for name in memory["present"]:
        update = memory["per_character"].get(name)
        if update is None:
            continue
        character = by_name[name]
        if update["new_memory"]:
            character["memories"].append({"chapter": number, "text": update["new_memory"]})
        if update["profile_change"]:
            character["profile_updates"].append({"chapter": number, "text": update["profile_change"]})
        storage.save_character(character)


def generate_chapter(story, chapters, characters, instruction):
    """Draft and finish a chapter in one go, with no pause for objections (they are overridden).

    The Streamlit app calls draft_chapter() and finish_chapter() separately so you can rule on them.
    """
    return finish_chapter(story, characters, draft_chapter(story, chapters, characters, instruction))
