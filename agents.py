"""The story agents.

All prompts live in the constants at the top of this file, so you can tune them
without touching any code. Every prompt is filled in with str.format(), so
avoid literal curly braces inside them.

Chapter generation is split in two so the author can rule on objections
before anything is saved:

    draft_chapter()   plan the scene, collect every character's reaction (nothing saved)
    finish_chapter()  rewrite accepted beats, write the text, update memories, save

generate_chapter() runs both in one go (unresolved objections are overridden).

Also here: the character-fit check (characters read the author's own writing and say how
likely they would really act that way), who-knows-what tracking, and the Cast room (characters
talking to each other in a rehearsal).

Data shapes
-----------
story:      {"title": str, "outline": str, "format": a key of formats.FORMATS}
character:  {"name", "card": {...}, "profile_updates": [], "memories": [], "chat_history": []}
beat:       {"text": str, "characters": [names who see/hear it]}
chapter:    {"number", "place", "title", "instruction", "plan", "reactions", "text", "summary", "present",
             "objections"}    ("chapter" means one unit: a chapter, a film scene or an act of an episode;
                               "place" says where it sits in the format, see formats.py)
"""

import base64
import contextvars
import copy
import re
import secrets
from concurrent.futures import ThreadPoolExecutor

import formats
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
DIRECTOR_PLAN_PROMPT = """You are the DIRECTOR of a story. Plan the next part of it as a short list of beats.

STORY: {title}

FORMAT: {format_name}
{structure}

OUTLINE
{outline}

WHAT HAS HAPPENED SO FAR (summaries)
{summaries}

CHARACTERS (you know everything about them)
{characters}

YOU ARE PLANNING: {position}
{position_hint}

THE AUTHOR'S INSTRUCTION FOR IT - follow it above everything else
{instruction}

Write {beats_range} beats, in order. Each beat is one or two sentences about what happens. For each beat, list in "characters" exactly who is there to see or hear it. A character who is not listed in a beat will never know it happened, so choose deliberately. Use character names exactly as written above. "present" is everyone who appears in at least one beat."""

# character_reaction - one call per present character. Gets the character identity above plus this.
REACTION_RULES = """The director has planned some scenes. Here are the beats YOU will be part of (you know nothing about any other beat):

{beats}

React as yourself.
- "reaction": 2 to 4 sentences, in first person and in your own voice: how you feel about these scenes and what you intend to do in them.
- "objection": fill this in ONLY if a beat would make you do or say something that contradicts who you have become (your background, how you have changed, what you remember). Merely disliking a beat, or finding it hard, is not an objection. Write it in your own voice, as if arguing with the author. Otherwise null.
- "beat": the number of the beat you object to, or null if you have no objection.
- "likelihood": if you object, how likely (0 to 100) you would really do what that beat asks of you; otherwise null.
- "alternatives": if you object, the 3 things you would more likely do in that beat instead, most likely first, each with its own likelihood (together with "likelihood" they should add up to about 100); otherwise an empty list.
- "growth": if you object, one sentence saying how you would have to have changed for that beat to be true to you; otherwise null."""

# rewrite_beat - used when the author ACCEPTS an objection.
REWRITE_BEAT_PROMPT = """You are the DIRECTOR of a serialized story. A character has objected to one beat of the plan, and the author has agreed with them.

ALL BEATS
{beats}

THE AUTHOR'S INSTRUCTION
{instruction}

{character} OBJECTS TO BEAT {number}
{objection}

Rewrite beat {number} so {character} is no longer asked to act against who they are. Keep as much as you can of what the beat was for in the story and of the author's instruction. Keep it to one or two sentences, and do not change who is present. Return only the new beat text."""

# write_chapter_text - the DIRECTOR writes it. The format's style rules come from formats.py.
WRITER_PROMPT = """You are the DIRECTOR of a story, now writing it.

STORY: {title}
FORMAT: {format_name}
YOU ARE WRITING: {position}

OUTLINE
{outline}

THE AUTHOR'S INSTRUCTION - respect this above everything else
{instruction}

CHARACTERS IN IT
{characters}

BEATS (write them in this order)
{beats}

HOW EACH CHARACTER REACTED
{reactions}

HOW TO WRITE IT
{style}
Length: about {words} words.

- Hit every beat. Do not add major events that are not in the beats.
- Stay consistent with the outline, the character cards and everything that has already happened: names, places, relationships, what each character calls the others, and what each one knows. Never contradict them.
- Keep each character's reaction and voice: their dialogue and choices must sound like them.
- Where a character objected and the author overrode it, the beat still happens, but show their resistance or reluctance.
- Do not reveal a character's secret unless a beat does.
- Only the characters listed for a beat are there for it.
- Output only the text itself: no title, no notes, no markdown."""

# update_memory - what did each character live through?
MEMORY_PROMPT = """Read this part of a {format_name} ({position}) and work out what each character takes away from it.

CHARACTERS TO CONSIDER
{characters}

TEXT
{chapter_text}

Return:
- "title": {title_hint}.
- "summary": 2 to 4 neutral sentences saying what happened.
- "present": the names of the characters (from the list above) who were actually in the scene and saw or heard what happened. Someone who is only mentioned or talked about is NOT present.
- "per_character": one entry for each present character only:
  - "new_memory": 1 to 3 sentences, from that character's own point of view, of what THEY personally saw, heard, said and did. Include only what they witnessed. Never include anything from a scene they were not in, or anything they could not have known.
  - "profile_change": one sentence if this really changed who they are (a belief, a goal, a fear, a relationship), otherwise null."""

# transcribe - turns the author's voice recording into text.
TRANSCRIBE_PROMPT = """You are a speech-to-text engine. The user message contains an audio recording, and you can hear it. Write down exactly what is said, word for word. Output only the transcript.
Names that may come up: {names}."""

# route_command - the DIRECTOR in the chat panel: answers the author, or works out what they want done.
ROUTER_PROMPT = """You are the DIRECTOR, the author's creative partner inside a story-writing app. You know everything about the story.

STORY: {title}
FORMAT: {format_name}, written in {units}

OUTLINE
{outline}

SO FAR
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
- "chapter_instruction": the author is describing what should happen next in the story (the next {unit}). Set "instruction" to a clear, complete instruction for it, keeping every detail the author gave.
- "edit_character": the author is giving new facts about an EXISTING character ("Park walks with a limp now"). Set "character", and in "card" give the FULL new text of each field that should change: keep what the field already says and work the new fact in. Fields that do not change are null.
- "new_character": the author is describing a character who is not in the list. Set "character" to the new name and fill every "card" field you can from what they said (null if they said nothing about it).
- "unclear": you cannot tell what they want, or a character name matches no one. Set "reply" to one short, friendly question.

For actions other than "discuss", "reply" is one short sentence telling the author what you did. Every field that does not apply is null."""

# check_fit - a character reads the author's own writing and judges their moments in it.
FIT_RULES = """The author has written a passage of the story in which you appear. Read it as yourself and judge how true it is to you: would you really act and speak like this, given who you are, how you have changed and what you remember?

THE PASSAGE
{text}

Return "moments": the 1 to 4 most important things YOU do or say in it (skip small, everyday ones). For each:
- "quote": the exact sentence from the passage where you do or say it, copied word for word
- "likelihood": 0 to 100, how likely you would really do or say this
- "why": one or two sentences in your own voice saying why you would or wouldn't
- "alternatives": if "likelihood" is under 60, the 3 things you would more likely do instead, most likely first, each with its own likelihood (together with "likelihood" they should add up to about 100); otherwise an empty list
- "growth": if "likelihood" is under 60, one sentence saying how you would have to have changed for this to be true to you; otherwise null
If you do not appear in the passage, return an empty list."""

# rewrite_moment - the author picked one of a character's alternatives; rewrite just that passage.
REWRITE_MOMENT_PROMPT = """You are editing a {format_name}. At one moment the author wants {character} to do something different.

THE MOMENT AS WRITTEN
{quote}

WHAT {character} DOES INSTEAD
{action}

CONTEXT BEFORE (do not rewrite)
{before}

THE PASSAGE TO REWRITE
{passage}

CONTEXT AFTER (do not rewrite)
{after}

Rewrite only THE PASSAGE TO REWRITE so that {character} does what is described instead. Keep the style, voice, tense and layout ({layout}) of the original, change as little else as possible, and make it lead naturally into the context after. Return only the rewritten passage."""

# extract_knowledge - who learns, suspects or gets wrong which fact in a passage.
KNOWLEDGE_PROMPT = """Read this part of a {format_name} ({position}) and track who learns what.

CHARACTERS
{names}

FACTS AND SECRETS ALREADY TRACKED (id: fact)
{known}

TEXT
{text}

Return "facts": the important facts, secrets or revelations that someone in this passage comes to know, starts to suspect, or gets wrong (usually 1 to 4 of them). Skip everyday details, but do include what characters learn about each other's plans, goals, feelings and secrets. For each:
- "fact_id": the id of a tracked fact above if it is the same fact, otherwise null
- "label": a short label of 3 to 7 words, like a heading, using names rather than pronouns (for example "Hale altered the order")
- "text": one sentence stating the fact
- "learned": everyone in this passage who knows it (including the person it is about), starts to suspect it, or believes something false about it. Each has "name" (exactly as listed above), "state" ("knows", "suspects" or "believes_false") and "how" (a few words, such as "saw it", "told by Nora", "overheard", "worked it out")
- "reader_learns": true if the reader learns it in this passage"""

# label_facts - short headings for the who-knows-what map.
LABEL_PROMPT = """Give each of these numbered secrets a short label of 3 to 7 words that names it clearly, like a heading. Use names, not pronouns (for example "Hale altered the order", "Park kept a copy of the order"). Return one label per number.

{items}"""

# The Cast room - characters talk to each other in a rehearsal that never becomes a memory.
ROOM_SITUATIONS = {
    "talk": "The author has brought you together with {others} to talk something through. The question: {topic}\n"
            "Talk it through from your own point of view.",
    "scene": "Improvise this situation with {others}: {topic}\nAct and speak as you would in that moment.",
}
ROOM_RULES = """THIS IS A REHEARSAL
Nothing said here happens in the story, and you will not remember it afterwards. But stay completely in character.

{situation}

THE CONVERSATION SO FAR
{transcript}

It is your turn, {name}. Reply with what you say, plus a brief action in *italics* if it matters:
- 1 to 3 short sentences, in your own voice.
- React to what was just said: agree, push back, deflect, joke, or stay silent (*says nothing*).
- Use only what YOU know. Never reveal your secret unless you truly would, here and now.
- Speak only for yourself, and do not start with your name."""

ROOM_SUMMARY_PROMPT = """You are the DIRECTOR of a {format_name}. The author just ran a rehearsal with part of the cast. Nothing in it has happened in the story yet.

STORY: {title}
{kind}: {topic}

THE REHEARSAL
{transcript}

Return:
- "summary": 2 to 4 sentences on what came out of it: where each character stood, the conflict, any surprise.
- "insights": up to 3 short things it revealed about the characters, one sentence each.
- "instruction": a clear instruction for writing the next {unit} of the story that uses the best of what happened here."""

# plan_comic - the DIRECTOR storyboards chapters as a vertical-scroll comic episode (webtoon).
COMIC_PLAN_PROMPT = """You are the DIRECTOR adapting part of a {format_name} into one episode of a vertical-scroll comic (a webtoon), read from top to bottom.

STORY: {title}

CHARACTERS
{characters}

THE TEXT TO ADAPT ({span})
{text}

Storyboard it as exactly {panels} panels, in reading order (a single chapter usually needs 12 to 20). Like a good webtoon: open with an establishing shot, vary shot sizes (wide, medium, close-up), slow down on emotional beats, and end on a hook. Condense: keep the moments that matter.
For each panel:
- "shape": "wide" for establishing shots and action, "tall" for dramatic or emotional moments, "square" otherwise
- "scene": what the picture shows, written for an illustrator: setting, time of day, lighting, who is where, expressions and body language. Name characters exactly as listed. Do not describe speech bubbles or text; they are added separately.
- "characters": the names (from the list) of everyone visible in the panel
- "caption": a short narration box of at most 20 words, or "" for none
- "dialogue": 0 to 2 speech bubbles in reading order, each with "speaker" and "text" (at most 12 words, taken or condensed from the text, in that character's voice)
Also return:
- "title": a title for this episode
- "looks": for every character who appears in a panel and has no LOOK above, one sentence describing how they look, consistently, in every panel: apparent age, build, face, hair, clothes and one distinctive detail. Base it on their card."""

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

ALTERNATIVES_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"action": {"type": "string"}, "likelihood": {"type": "integer"}},
        "required": ["action", "likelihood"],
        "additionalProperties": False,
    },
}

REACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "reaction": {"type": "string"},
        "objection": {"type": ["string", "null"]},
        "beat": {"type": ["integer", "null"]},
        "likelihood": {"type": ["integer", "null"]},
        "alternatives": ALTERNATIVES_SCHEMA,
        "growth": {"type": ["string", "null"]},
    },
    "required": ["reaction", "objection", "beat", "likelihood", "alternatives", "growth"],
    "additionalProperties": False,
}

FIT_SCHEMA = {
    "type": "object",
    "properties": {
        "moments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "likelihood": {"type": "integer"},
                    "why": {"type": "string"},
                    "alternatives": ALTERNATIVES_SCHEMA,
                    "growth": {"type": ["string", "null"]},
                },
                "required": ["quote", "likelihood", "why", "alternatives", "growth"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["moments"],
    "additionalProperties": False,
}

KNOWLEDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact_id": {"type": ["string", "null"]},
                    "label": {"type": "string"},
                    "text": {"type": "string"},
                    "learned": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "state": {"type": "string", "enum": ["knows", "suspects", "believes_false"]},
                                "how": {"type": "string"},
                            },
                            "required": ["name", "state", "how"],
                            "additionalProperties": False,
                        },
                    },
                    "reader_learns": {"type": "boolean"},
                },
                "required": ["fact_id", "label", "text", "learned", "reader_learns"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["facts"],
    "additionalProperties": False,
}

LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"number": {"type": "integer"}, "label": {"type": "string"}},
                "required": ["number", "label"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["labels"],
    "additionalProperties": False,
}

COMIC_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "looks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "look": {"type": "string"}},
                "required": ["name", "look"],
                "additionalProperties": False,
            },
        },
        "panels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "shape": {"type": "string", "enum": ["wide", "tall", "square"]},
                    "scene": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "caption": {"type": "string"},
                    "dialogue": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"speaker": {"type": "string"}, "text": {"type": "string"}},
                            "required": ["speaker", "text"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["shape", "scene", "characters", "caption", "dialogue"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "looks", "panels"],
    "additionalProperties": False,
}

ROOM_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "insights": {"type": "array", "items": {"type": "string"}},
        "instruction": {"type": "string"},
    },
    "required": ["summary", "insights", "instruction"],
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
READER = "READER"         # who-knows-what: the reader, next to the characters
AUTHOR = "You"            # Cast room: the author's own lines in a rehearsal


def _parallel(jobs):
    """Run several model calls at the same time. Each job is a function with no arguments.

    Each worker gets a copy of the current context, so it still sees the story chosen with
    storage.use_story() (a ContextVar).
    """
    if len(jobs) <= 1:
        return [job() for job in jobs]
    with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as pool:
        futures = [pool.submit(contextvars.copy_context().run, job) for job in jobs]
        return [future.result() for future in futures]


def _pct(value):
    """A likelihood from the model as an int from 0 to 100, or None."""
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return None


def _alternatives(raw):
    return [{"action": a["action"].strip(), "likelihood": _pct(a.get("likelihood")) or 0}
            for a in (raw or []) if a.get("action", "").strip()][:3]


def _card_text(character):
    return "\n".join(f"{field.capitalize()}: {value}" for field, value in character["card"].items() if value)


def _identity(character):
    """The 'You ARE <name>' block with the character's card, profile updates and memories."""
    updates = character["profile_updates"]
    profile = ("HOW YOU HAVE CHANGED\n" + "\n".join(f"- {u['text']}" for u in updates)) if updates else ""
    memories = character["memories"]
    if memories:
        memory_text = "WHAT YOU REMEMBER (everything you know about recent events)\n" + "\n".join(
            f"- {m['text']}" for m in memories
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


def _summaries(fmt, chapters):
    """'Volume 1 · Chapter 3 (The Letter): summary' lines for everything written so far."""
    return "\n".join(f"{formats.label(fmt, formats.place_of(fmt, c), c['number'])} ({c.get('title', '')}): "
                     f"{c['summary']}" for c in chapters)


def _director_view(character):
    """What the director knows about a character: card plus how they have changed."""
    text = f"{character['name']}\n{_card_text(character)}"
    for update in character["profile_updates"]:
        text += f"\nHas changed: {update['text']}"
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


def plan_scene(story, chapters, instruction, place=None):
    """The DIRECTOR plans the next unit at `place`. Returns {"beats": [{text, characters}], "present": [names]}."""
    fmt = formats.get(story.get("format"))
    place = place or formats.next_options(fmt, chapters)[0][1]
    characters = storage.load_all_characters()
    names = {c["name"] for c in characters}

    prompt = DIRECTOR_PLAN_PROMPT.format(
        title=story["title"],
        format_name=fmt["name"],
        structure=fmt["structure"],
        outline=story["outline"],
        summaries=_summaries(fmt, chapters) or "(nothing yet - this is the beginning)",
        characters="\n\n".join(_director_view(c) for c in characters),
        position=formats.label(fmt, place, storage.next_chapter_number()),
        position_hint=formats.hint(fmt, place, chapters),
        instruction=instruction,
        beats_range=fmt["beats"],
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
        return {"reaction": "", "objection": None, "beat": None, "likelihood": None, "alternatives": [],
                "growth": None}

    system = _identity(character) + "\n\n" + REACTION_RULES.format(beats=_beats_text(plan["beats"], only_for=name))
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": "Give your reaction to these scenes now."}]
    result = llm.chat(messages, json_schema=REACTION_SCHEMA)

    objection = (result["objection"] or "").strip() or None
    beat = result["beat"] if result["beat"] in visible else visible[0]  # fall back to their first beat
    return {
        "reaction": result["reaction"],
        "objection": objection,
        "beat": beat if objection else None,
        "likelihood": _pct(result.get("likelihood")) if objection else None,
        "alternatives": _alternatives(result.get("alternatives")) if objection else [],
        "growth": (result.get("growth") or "").strip() or None if objection else None,
    }


def rewrite_beat(plan, instruction, character, objection, number, instead=None):
    """Rewrite one beat (1-based `number`) after the author accepts a character's objection.

    With `instead`, the author picked what the character does instead (one of their alternatives).
    """
    if instead:
        objection += (f"\nThe author has decided that, instead, {character} will: {instead}. "
                      "Rewrite the beat so that this is what happens.")
    prompt = REWRITE_BEAT_PROMPT.format(
        beats=_beats_text(plan["beats"]), instruction=instruction,
        character=character, number=number, objection=objection,
    )
    return llm.chat([{"role": "user", "content": prompt}], json_schema=REWRITE_SCHEMA)["text"].strip()


def write_chapter_text(story, plan, reactions, instruction="", place=None):
    """The DIRECTOR writes the unit at `place` from the beats and the characters' reactions.

    Prose for novels, screenplay format for film and TV (see formats.py).
    """
    fmt = formats.get(story.get("format"))
    place = place or formats.first_place(fmt)
    present = [c for c in storage.load_all_characters() if c["name"] in plan["present"]]

    lines = []
    for name, r in reactions.items():
        line = f"{name}: {r['reaction']}"
        if r.get("objection"):
            outcome = {"overridden": "the author OVERRODE this - the beat stays as written",
                       "accepted": "the author ACCEPTED this - the beat was rewritten",
                       "choice": f"the author chose what {name} does instead ({r.get('objection_choice', '')}) "
                                 "- the beat was rewritten"}.get(r.get("objection_status"), "")
            line += f"\n  {name} objected: {r['objection']} ({outcome})"
        lines.append(line)

    prompt = WRITER_PROMPT.format(
        title=story["title"],
        format_name=fmt["name"],
        position=formats.label(fmt, place, storage.next_chapter_number()),
        style=fmt["style"],
        words=formats.words_for(fmt, place),
        outline=story["outline"],
        instruction=instruction or "(none given - follow the beats)",
        characters="\n\n".join(_director_view(c) for c in present),
        beats=_beats_text(plan["beats"]),
        reactions="\n".join(lines),
    )
    return llm.chat([{"role": "user", "content": prompt}]).strip()


def update_memory(chapter_text, characters, fmt=None, position=""):
    """Work out what happened and what each character in `characters` personally lived through.

    Returns {"title", "summary", "present", "per_character": {name: {"new_memory", "profile_change"}}}.
    Only characters who were actually present end up in `present` and `per_character`.
    """
    names = [c["name"] for c in characters]
    fmt = fmt or formats.get("novel")
    prompt = MEMORY_PROMPT.format(
        format_name=fmt["name"].lower(),
        position=position or fmt["unit"].lower(),
        title_hint=fmt["title_hint"],
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
    fmt = formats.get(story.get("format"))
    prompt = ROUTER_PROMPT.format(
        title=story["title"],
        format_name=fmt["name"],
        units=fmt["units"],
        unit=fmt["unit"].lower(),
        outline=story["outline"],
        summaries=_summaries(fmt, chapters) or "(nothing written yet)",
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
# Character-fit check: does the author's own writing feel true to each character?
# =====================================================================

def _mentions(text, name):
    return re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE) is not None


def check_fit(character, text):
    """One character reads `text` and rates their own moments in it.

    Returns [{character, quote, likelihood, why, alternatives: [{action, likelihood}], growth}].
    """
    system = _identity(character) + "\n\n" + FIT_RULES.format(text=text)
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": "Read it and judge your moments now."}]
    moments = []
    for m in llm.chat(messages, json_schema=FIT_SCHEMA)["moments"]:
        likelihood = _pct(m.get("likelihood"))
        if m.get("quote", "").strip() and likelihood is not None:
            moments.append({"character": character["name"], "quote": m["quote"].strip(), "likelihood": likelihood,
                            "why": m.get("why", "").strip(), "alternatives": _alternatives(m.get("alternatives")),
                            "growth": (m.get("growth") or "").strip() or None})
    return moments


def check_cast_fit(characters, text):
    """Every character named in `text` reads it at the same time.

    Returns {"checked": [names], "moments": [...]} with the least likely moments first.
    """
    cast = [c for c in characters if _mentions(text, c["name"])]
    results = _parallel([lambda c=c: check_fit(c, text) for c in cast])
    moments = sorted((m for found in results for m in found), key=lambda m: m["likelihood"])
    return {"checked": [c["name"] for c in cast], "moments": moments}


def _blocks(text):
    return [block for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]


def _find_block(blocks, quote):
    """The paragraph (or screenplay block) that contains `quote`, or the one sharing most words with it."""
    for i, block in enumerate(blocks):
        if quote in block:
            return i
    words = set(re.findall(r"\w+", quote.lower()))
    return max(range(len(blocks)), key=lambda i: len(words & set(re.findall(r"\w+", blocks[i].lower()))))


def rewrite_moment(story, text, quote, character_name, action):
    """Rewrite only the passage around `quote` so the character does `action` instead. Returns the new text."""
    fmt = formats.get(story.get("format"))
    blocks = _blocks(text)
    if not blocks:
        return text
    i = _find_block(blocks, quote)
    prompt = REWRITE_MOMENT_PROMPT.format(
        format_name=formats.display_name(fmt), character=character_name, quote=quote, action=action,
        before="\n\n".join(blocks[max(0, i - 2):i]) or "(the start of the text)",
        passage=blocks[i],
        after="\n\n".join(blocks[i + 1:i + 3]) or "(the end of the text)",
        layout="screenplay format" if fmt["layout"] == "screenplay" else "prose",
    )
    new = llm.chat([{"role": "user", "content": prompt}]).strip()
    if new:
        blocks[i] = new
    return "\n\n".join(blocks)


def remember_growth(character, number, growth, moment):
    """The author kept something out of character on purpose: it becomes part of who they are now."""
    character["profile_updates"].append({"chapter": number, "text": growth or f"Has changed: {moment}"})
    storage.save_character(character)


# =====================================================================
# Who knows what
# =====================================================================

def sync_secret_facts(knowledge, characters):
    """Every character's card secret is a fact that character knows from the start (chapter 0)."""
    by_id = {f["id"]: f for f in knowledge["facts"]}
    for c in characters:
        secret, fact_id = c["card"].get("secret", "").strip(), f"secret:{c['name']}"
        if not secret:
            continue
        fact = by_id.get(fact_id)
        if fact is None:
            knowledge["facts"].append({"id": fact_id, "label": "", "text": secret, "owner": c["name"],
                                       "events": [{"who": c["name"], "state": "knows", "chapter": 0,
                                                   "how": "their own secret"}]})
        elif fact["text"] != secret:
            fact["text"], fact["label"] = secret, ""
    return knowledge


def label_facts(knowledge):
    """Give every fact without one a short heading (one model call for all of them)."""
    missing = [f for f in knowledge["facts"] if not f.get("label")]
    if not missing:
        return
    items = "\n".join(f"{i}. {f['text']}" for i, f in enumerate(missing, start=1))
    result = llm.chat([{"role": "user", "content": LABEL_PROMPT.format(items=items)}], json_schema=LABEL_SCHEMA)
    labels = {item["number"]: item["label"].strip() for item in result["labels"]}
    for i, fact in enumerate(missing, start=1):
        fact["label"] = labels.get(i) or (fact["text"][:46] + "…" if len(fact["text"]) > 46 else fact["text"])


def extract_knowledge(text, characters, knowledge, fmt, position):
    """Who learns, suspects or gets wrong which fact in this passage (raw model output)."""
    known = "\n".join(f"{f['id']}: {f.get('label') or f['text']}" for f in knowledge["facts"]) or "(none yet)"
    prompt = KNOWLEDGE_PROMPT.format(format_name=formats.display_name(fmt), position=position,
                                     names=", ".join(c["name"] for c in characters), known=known, text=text)
    return llm.chat([{"role": "user", "content": prompt}], json_schema=KNOWLEDGE_SCHEMA)["facts"]


def apply_knowledge(knowledge, updates, number, present):
    """Record what happened in unit `number`. Only characters present in it can learn anything."""
    by_id = {f["id"]: f for f in knowledge["facts"]}
    by_label = {f["label"].strip().lower(): f for f in knowledge["facts"] if f.get("label")}
    for update in updates:
        fact = by_id.get(update.get("fact_id") or "") or by_label.get(update["label"].strip().lower())
        if fact is None:
            fact = {"id": "f" + secrets.token_hex(3), "label": update["label"].strip(), "text": update["text"].strip(),
                    "owner": None, "events": []}
            # The person a new fact is about ("Nora investigates...") knows it, if they were there.
            subject = next((n for n in sorted(present, key=len, reverse=True)
                            if fact["label"].lower().startswith(n.lower())), None)
            if subject and subject not in [l["name"] for l in update["learned"]]:
                fact["events"].append({"who": subject, "state": "knows", "chapter": number, "how": "it's about them"})
            knowledge["facts"].append(fact)
            by_id[fact["id"]] = by_label[fact["label"].lower()] = fact
        for learned in update["learned"]:
            if learned["name"] in present:
                fact["events"].append({"who": learned["name"], "state": learned["state"], "chapter": number,
                                       "how": learned["how"].strip()})
        if update["reader_learns"]:
            fact["events"].append({"who": READER, "state": "knows", "chapter": number, "how": "shown on the page"})
    knowledge["facts"] = [f for f in knowledge["facts"] if f["events"]]  # drop facts nobody learned
    knowledge["scanned"] = max(knowledge.get("scanned", 0), number)
    return knowledge


def scan_knowledge(story, chapters, characters, fresh=False, on_progress=None):
    """Track who-knows-what for every unit not scanned yet (or all of them again with fresh=True)."""
    fmt = formats.get(story.get("format"))
    knowledge = storage.load_knowledge()
    if fresh:
        knowledge = {"facts": [dict(f, events=[e for e in f["events"] if e["chapter"] == 0])
                               for f in knowledge["facts"] if f.get("owner")], "scanned": 0}
    sync_secret_facts(knowledge, characters)
    todo = [c for c in chapters if c["number"] > knowledge.get("scanned", 0)]
    for i, chapter in enumerate(todo):
        if on_progress:
            on_progress(i, len(todo), chapter)
        position = formats.label(fmt, formats.place_of(fmt, chapter), chapter["number"])
        updates = extract_knowledge(chapter["text"], characters, knowledge, fmt, position)
        apply_knowledge(knowledge, updates, chapter["number"], chapter["present"])
        storage.save_knowledge(knowledge)  # keep progress even if a later unit fails
    return knowledge


def _knowledge_or_nothing(text, characters, knowledge, fmt, position):
    """Knowledge tracking is a bonus: if it fails, the chapter is still saved."""
    try:
        return extract_knowledge(text, characters, knowledge, fmt, position)
    except Exception:
        return None


# =====================================================================
# The Cast room
# =====================================================================

def _transcript(lines):
    return "\n".join(f"{'The author' if line['speaker'] == AUTHOR else line['speaker']}: {line['text']}"
                     for line in lines) or "(nobody has spoken yet)"


def room_line(character, others, mode, topic, lines):
    """One character's next line in a rehearsal. Nothing here is saved as a memory."""
    situation = ROOM_SITUATIONS[mode].format(others=", ".join(others) or "no one else", topic=topic)
    system = _identity(character) + "\n\n" + ROOM_RULES.format(situation=situation, transcript=_transcript(lines),
                                                                 name=character["name"])
    line = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": "Your turn."}]).strip()
    line = re.sub(rf"^\W*{re.escape(character['name'])}\W*:\s*", "", line)  # "Park: ..." -> "..."
    if len(line) > 1 and line[0] == line[-1] == '"':
        line = line[1:-1]
    return line.strip()


def room_summary(story, mode, topic, lines):
    """The Director sums up a rehearsal: {summary, insights, instruction}."""
    fmt = formats.get(story.get("format"))
    prompt = ROOM_SUMMARY_PROMPT.format(format_name=formats.display_name(fmt), title=story["title"],
                                        kind="Question" if mode == "talk" else "Scene", topic=topic,
                                        transcript=_transcript(lines), unit=fmt["unit"].lower())
    return llm.chat([{"role": "user", "content": prompt}], json_schema=ROOM_SUMMARY_SCHEMA)


# =====================================================================
# Comic: chapters -> a vertical-scroll episode drawn by Meta's image model
# =====================================================================

def plan_comic(story, chapters, characters, looks, panels):
    """The Director storyboards `chapters` as one episode of `panels` panels.

    Returns {"title", "looks": {name: look} (new ones only), "panels": [{shape, scene, characters, caption, dialogue}]}.
    """
    fmt = formats.get(story.get("format"))
    names = {c["name"] for c in characters}
    cast = "\n".join(f"- {c['name']}: {(c['card'].get('background') or '')[:300]}"
                     + (f"\n  LOOK: {looks[c['name']]}" if c["name"] in looks else "") for c in characters)
    first, last = chapters[0], chapters[-1]
    span = formats.label(fmt, formats.place_of(fmt, first), first["number"])
    if last is not first:
        span += " to " + formats.label(fmt, formats.place_of(fmt, last), last["number"])
    text = "\n\n".join(f"[{formats.label(fmt, formats.place_of(fmt, c), c['number'])}]\n{c['text']}" for c in chapters)
    prompt = COMIC_PLAN_PROMPT.format(format_name=formats.display_name(fmt), title=story["title"],
                                      characters=cast or "(none)", span=span, text=text, panels=panels)
    result = llm.chat([{"role": "user", "content": prompt}], json_schema=COMIC_SCHEMA)
    for panel in result["panels"]:
        panel["characters"] = [n for n in panel["characters"] if n in names]
    return {"title": result["title"], "panels": result["panels"],
            "looks": {item["name"]: item["look"] for item in result["looks"] if item["name"] in names}}


COMIC_STYLES = {
    "webtoon": "Korean manhwa (webtoon) art style: clean thin line art, flat cel shading with one shadow tone, simple "
               "backgrounds, bright clean colors, expressive anime-style faces. Not photorealistic, not painterly.",
    "manga": "Black-and-white Japanese manga art: clean ink line art, screentone shading, simple backgrounds, "
             "expressive faces. No color.",
    "graphic": "Western graphic-novel art: bold ink lines, flat muted colors, simple backgrounds, grounded "
               "proportions. Not photorealistic.",
}
PANEL_SIZES = {"wide": "1536x1024", "tall": "1024x1536", "square": "1024x1024"}
SHEET_PROMPT = ("{style} Character reference sheet on a plain white background: {name}, {look} The same person shown "
                "full body, front view, and as a head-and-shoulders close-up, side by side. No text.")
ORDINALS = ["first", "second", "third"]
MAX_REFERENCES = 3  # character sheets sent with one panel


LOOKS_PROMPT = """For a comic adaptation of this story, describe how each of these characters looks, so an illustrator can draw them the same way in every panel.

STORY: {title}
{outline}

CHARACTERS
{characters}

For each character, one sentence: apparent age, build, skin tone, face, hair, everyday clothes and one distinctive detail (glasses, a scar, a watch...). Fit the setting of the story."""


def describe_looks(story, characters):
    """{name: look} for these characters (one call), used to draw their reference sheets."""
    if not characters:
        return {}
    cast = "\n".join(f"- {c['name']}: {(c['card'].get('background') or '')[:300]}" for c in characters)
    prompt = LOOKS_PROMPT.format(title=story["title"], outline=story["outline"][:1500], characters=cast)
    schema = {"type": "object", "properties": {"looks": COMIC_SCHEMA["properties"]["looks"]},
              "required": ["looks"], "additionalProperties": False}
    names = {c["name"] for c in characters}
    result = llm.chat([{"role": "user", "content": prompt}], json_schema=schema)
    return {item["name"]: item["look"] for item in result["looks"] if item["name"] in names}


def draw_sheet(name, look, style):
    """A character reference sheet (full body + close-up) that every panel is drawn from. Returns image bytes."""
    look = look.strip().rstrip(".") + "."
    return llm.image(SHEET_PROMPT.format(style=COMIC_STYLES.get(style, COMIC_STYLES["webtoon"]), name=name, look=look),
                     "1536x1024")


def panel_prompt(panel, looks, style, sheet_names=(), lettering=True):
    """What the image model is asked to draw for one panel."""
    parts = [COMIC_STYLES.get(style, COMIC_STYLES["webtoon"]), "A single vertical-scroll comic panel."]
    if sheet_names:
        who = "; ".join(f"the {ORDINALS[i]} reference sheet is {name}" for i, name in enumerate(sheet_names))
        parts.append(f"Use the reference sheets ({who}) and draw each of them exactly as in their sheet: same face, "
                     "hair, clothes, accessories and colors.")
    others = [name for name in panel["characters"] if name not in sheet_names and name in looks]
    if others:
        parts.append("Also: " + "; ".join(f"{name}: {looks[name].strip().rstrip('.')}" for name in others) + ".")
    parts.append(panel["scene"])
    if lettering and panel.get("dialogue"):
        bubbles = "; ".join(f'{line["speaker"]} says "{line["text"]}"' for line in panel["dialogue"])
        parts.append(f"Speech bubbles: white oval bubbles with clean black lettering, tails pointing to the speaker, "
                     f"placed so they do not cover faces: {bubbles}. Spell the words exactly. No other text.")
    else:
        parts.append("No text, no lettering, no speech bubbles.")
    parts.append("No captions, no panel borders, no signature.")
    return " ".join(parts)


def draw_panel(panel, looks, style, sheets=None, lettering=True):
    """Image bytes for one panel, drawn from the sheets of the characters in it (when there are any)."""
    sheets = sheets or {}
    names = [name for name in panel["characters"] if name in sheets][:MAX_REFERENCES]
    prompt = panel_prompt(panel, looks, style, names, lettering)
    size = PANEL_SIZES.get(panel["shape"], "1024x1024")
    if names:
        return llm.edit_image(prompt, [sheets[name] for name in names], size)
    return llm.image(prompt, size)


# =====================================================================
# Putting it together
# =====================================================================

def draft_chapter(story, chapters, characters, instruction, place=None):
    """Steps 1-2: plan the next unit (at `place`) and gather reactions. Saves NOTHING.

    Returns a draft {instruction, place, plan, reactions, objections}. Each objection is
    {character, beat, objection, likelihood, alternatives, growth, status: "pending"}. Set status to
    "accepted" (the Director rewrites the beat), "choice" (with "choice": one of the alternatives) or
    "overridden"; "remember": True also saves "growth" to the character. Then call finish_chapter().
    """
    by_name = {c["name"]: c for c in characters}
    place = place or formats.next_options(formats.get(story.get("format")), chapters)[0][1]
    plan = plan_scene(story, chapters, instruction, place)
    names = [name for name in plan["present"] if name in by_name]
    reactions = dict(zip(names, _parallel([lambda n=n: character_reaction(by_name[n], plan) for n in names])))
    objections = [
        {"character": name, "beat": r["beat"], "objection": r["objection"], "likelihood": r["likelihood"],
         "alternatives": r["alternatives"], "growth": r["growth"], "status": "pending"}
        for name, r in reactions.items()
        if r["objection"]
    ]
    return {"instruction": instruction, "place": place, "plan": plan, "reactions": reactions,
            "objections": objections}


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
        reactions[o["character"]]["objection_choice"] = o.get("choice")
        if o["status"] in ("accepted", "choice"):  # Accept or a chosen alternative rewrites the beat.
            plan["beats"][o["beat"] - 1]["text"] = rewrite_beat(
                plan, draft["instruction"], o["character"], o["objection"], o["beat"],
                instead=o.get("choice") if o["status"] == "choice" else None)

    fmt = formats.get(story.get("format"))
    place = draft.get("place") or formats.first_place(fmt)
    number = storage.next_chapter_number()
    text = write_chapter_text(story, plan, reactions, draft["instruction"], place)

    # Memory: only characters the model confirms were present in the written text
    # (and who were in the plan) learn anything.
    planned = [by_name[n] for n in plan["present"] if n in by_name]
    memory, knowledge, updates = _analyse(text, planned, characters, fmt, formats.label(fmt, place, number))

    chapter = {
        "number": number,
        "place": place,
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
    _save_knowledge(knowledge, updates, chapter)
    for o in objections:
        if o["status"] == "overridden" and o.get("remember"):
            remember_growth(by_name[o["character"]], number, o.get("growth"), plan["beats"][o["beat"] - 1]["text"])
    return chapter


def add_author_chapter(story, characters, text, place):
    """Save a unit the author wrote themselves, and update what each character remembers."""
    by_name = {c["name"]: c for c in characters}
    fmt = formats.get(story.get("format"))
    number = storage.next_chapter_number()
    memory, knowledge, updates = _analyse(text, characters, characters, fmt, formats.label(fmt, place, number))
    chapter = {
        "number": number,
        "place": place,
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
    _save_knowledge(knowledge, updates, chapter)
    return chapter


def _analyse(text, memory_characters, all_characters, fmt, position):
    """Work out memories and who-knows-what for a new unit at the same time (two parallel calls)."""
    knowledge = sync_secret_facts(storage.load_knowledge(), all_characters)
    memory, updates = _parallel([
        lambda: update_memory(text, memory_characters, fmt, position),
        lambda: _knowledge_or_nothing(text, all_characters, knowledge, fmt, position),
    ])
    return memory, knowledge, updates


def _save_knowledge(knowledge, updates, chapter):
    # Only track a unit if every earlier one was tracked too; otherwise the map offers to scan them.
    if updates is not None and knowledge.get("scanned", 0) >= chapter["number"] - 1:
        apply_knowledge(knowledge, updates, chapter["number"], chapter["present"])
        storage.save_knowledge(knowledge)


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


def generate_chapter(story, chapters, characters, instruction, place=None):
    """Draft and finish the next unit in one go, with no pause for objections (they are overridden).

    The Streamlit app calls draft_chapter() and finish_chapter() separately so you can rule on them.
    """
    return finish_chapter(story, characters, draft_chapter(story, chapters, characters, instruction, place))
