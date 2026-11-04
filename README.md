# NovelSpark

**Write with characters who remember.**

NovelSpark is a writing studio where every character in your novel is their own AI agent. They remember only the scenes they lived through, answer you in their own voice, and push back when a chapter asks them to act against who they've become. A Director agent plans each chapter with you, and you can type or simply talk.

Built with Streamlit, plain JSON files for storage, and the `openai` Python SDK pointed at Meta's API (`muse-spark-1.3`).

## Setup

You need Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then put your key in .env
```

`.env` should contain:

```
META_API_KEY=your-meta-api-key-here
```

`.env` is in `.gitignore`, so your key won't be committed.

## Run

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

## What's in the app

Three panels:

- **Left:** chapters on top and characters below. Each character shows the chapter they were last seen in, or a **Forgotten** badge after 3+ chapters away.
- **Center:** the manuscript. Read or edit chapters, write the next one (generate it with the cast, or write it yourself), or open a character's profile and memories.
- **Right:** one conversation, typed or spoken (mic button). Talk to the **Director**, who knows the whole story, or to any character, who knows only what they lived through. Say *"Hey Hale, ..."* to switch to a character from anywhere. The Director also acts on what you say:
  - *"Next chapter: Park visits the cemetery."* fills in the editor.
  - *"Park walks with a limp now."* suggests profile changes for you to Apply.
  - *"Add a new character: Joon..."* drafts a new profile.

Voice is transcribed by `muse-spark-1.3` itself (it accepts audio).

The app starts empty. Set your title and outline from the story link at the top left, add characters, and write your first chapter. Your story is saved in `data/`, which is git-ignored, so it stays on your machine.

## Files

| File | What it does |
| --- | --- |
| `app.py` | Page setup and the three-panel layout |
| `views.py` | Left panel and the center screens |
| `chat.py` | Right panel: the conversation with the Director and the cast |
| `ui.py` | Small shared UI helpers |
| `style.css` | The visual design |
| `storage.py` | Load/save JSON in `data/` |
| `llm.py` | `chat(messages, json_schema=None)`: calls the model, retries on errors, returns text or parsed JSON, and appends token usage to `usage.log` |
| `agents.py` | The agent functions |

## Data layout

```
data/story.json                 {title, outline}
data/characters/<name>.json     {name, card, profile_updates, memories, chat_history}
data/chapters/NN.json           {number, title, instruction, plan, reactions, text, summary, present, objections}
data/director_chat.json         your conversation with the Director
```

Memories and profile updates are stored as `{"chapter": N, "text": "..."}`. Objections are stored as `{"character", "objection", "status"}` where status is `accepted` or `overridden` (`pending` only exists in an unsaved draft). Each objection also records the `beat` number it was about.

## How chapter generation works

All prompts are constants at the top of `agents.py` (`DIRECTOR_PLAN_PROMPT`, `REACTION_RULES`, `WRITER_PROMPT`, `MEMORY_PROMPT`, ...), so you can tune them without touching code.

1. `plan_scene`: the director turns your instruction into beats. Each beat lists who is there to see it.
2. `character_reaction`: every present character sees **only the beats they are in** and reacts in character. They may object if a beat contradicts who they have become.
3. **You rule on objections before anything is saved.** Accept rewrites that beat; Override keeps it (the character plays it reluctantly).
4. `write_chapter_text`: the director writes about 1200 words.
5. `update_memory`: summary plus a memory for each character who was actually present. In code, memories and profile changes are appended **only** to those characters, so nobody knows about scenes they weren't in.

The app calls `draft_chapter()` (steps 1-2, saves nothing) and then `finish_chapter()` (steps 3-5). `generate_chapter()` runs both in one go and overrides any objections.

`character_reply` builds its prompt from the card, profile updates and memories, sends the last 10 chat messages, and saves the new exchange.

Note: the draft waiting on your objection decisions lives in the Streamlit session, so refreshing the page discards it.

## Resetting

Delete `data/chapters/*.json` to remove all chapters, and edit the files in `data/characters/` to clear memories and chat history. Token usage is logged in `usage.log` (one JSON line per call).
