"""The right panel: Chat (the Director or any character) and the Cast room (see castroom.py).

- Talking to the Director: it answers questions, or acts on what you say (fills in the next
  chapter, suggests profile changes, drafts a new character, or passes a question to a character).
- Talking to a character: they answer in character, knowing only what they lived through.
- "Hey Hale, ..." / "@Hale ..." / "Hale: ..." switches straight to that character from anywhere.
"""

import html

import streamlit as st

import agents
import castroom
import storage
import ui
from ui import DIRECTOR

CHAT, ROOM = "Chat", "Cast room"


def right_panel(story, fmt, chapters, characters):
    """Draw the right panel. Returns (slot, value, kind): kind is "chat" or "room" for the handler."""
    st.session_state.setdefault("right_tab", CHAT)
    tab = st.segmented_control("Panel", [CHAT, ROOM], key="right_tab", required=True, label_visibility="collapsed",
                               width="stretch",
                               format_func=lambda t: f":material/{'forum' if t == CHAT else 'groups'}: {t}")
    if tab == ROOM:
        slot, value = castroom.room_panel(story, fmt, characters)
        return slot, value, "room"
    slot, value = chat_panel(fmt, chapters, characters)
    return slot, value, "chat"


def chat_panel(fmt, chapters, characters):
    """Draw the panel. Returns (slot, value): the chat_input value is handled later by handle()."""
    names = [c["name"] for c in characters]
    if st.session_state.get("chat_with") not in [DIRECTOR] + names:
        st.session_state["chat_with"] = DIRECTOR
    target = st.session_state["chat_with"]
    if note := st.session_state.pop("director_note", None):  # sent over from the Cast room
        storage.save_director_chat(storage.load_director_chat() + [{"role": "assistant", "content": note}])

    with st.container(key="chat_header", horizontal=True, vertical_alignment="center"):
        if target == DIRECTOR:
            sub = "Knows the whole story"
        else:
            seen = ui.last_seen_label(fmt, target, chapters, short=True)
            sub = "Knows only what they lived through" + (f" · last seen {seen}" if seen else "")
        st.html(f'<div class="sa-chat-head">{ui.avatar(target)}<div style="min-width:0">'
                f'<div class="sa-chat-name">{html.escape(target)}</div>'
                f'<div class="sa-chat-sub">{html.escape(sub)}</div></div></div>')
        st.selectbox("Talking to", [DIRECTOR] + names, key="chat_with", label_visibility="collapsed", width=150)

    messages = _thread(target, characters)
    st.html(_thread_html(target, messages))
    slot = st.container()
    placeholder = ("Ask the Director, or say “Hey Hale…”" if target == DIRECTOR
                   else f"Message {target}…")
    value = st.chat_input(placeholder, key="chat_box", accept_audio=True)
    return slot, value


def _thread(target, characters):
    if target == DIRECTOR:
        return storage.load_director_chat()
    return next(c for c in characters if c["name"] == target)["chat_history"]


def _bubble(name, text):
    if name is None:  # the author
        return f'<div class="sa-msg author"><div class="sa-bubble">{ui.rich(text)}</div></div>'
    return (f'<div class="sa-msg">{ui.avatar(name)}<div class="sa-body">'
            f'<div class="sa-name">{html.escape(name)}</div>'
            f'<div class="sa-bubble">{ui.rich(text)}</div></div></div>')


def _thread_html(target, messages):
    if not messages:
        if target == DIRECTOR:
            hint = ("<b>Your Director</b>Ask anything about the story, describe what happens next, "
                    "or update a character. Say “Hey Hale…” to talk to someone in your cast.")
        else:
            hint = (f"<b>{html.escape(target)}</b>Ask them anything. They answer in their own voice, "
                    "and only know the scenes they were in.")
        return f'<div class="sa-thread"><div class="sa-welcome">{ui.avatar(target, "lg")}<br>{hint}</div></div>'
    bubbles = [_bubble(None if m["role"] == "user" else target, m["content"]) for m in messages]
    return '<div class="sa-thread">' + "".join(reversed(bubbles)) + "</div>"  # column-reverse: newest at bottom


def handle(value, slot, story, chapters, characters):
    """Process one message from the chat box, then rerun so every panel shows the result."""
    by_name = {c["name"]: c for c in characters}
    try:
        text, _ = ui.read_input(value, list(by_name))
        if not text:
            return
        target = st.session_state["chat_with"]
        addressed = ui.addressed_to(text, [DIRECTOR] + list(by_name))
        if addressed and addressed != target:
            target = addressed
            ui.defer("chat_with", target)

        with slot:
            st.html(_bubble(None, text) + f'<div class="sa-typing">{html.escape(target)} is thinking…</div>')
            if target == DIRECTOR:
                _director_turn(text, story, chapters, characters, by_name)
            else:
                agents.character_reply(by_name[target], text)  # also saves the exchange
        st.rerun()
    except Exception as e:
        with slot:
            st.error(f"Something went wrong: {e}")


def _director_turn(text, story, chapters, characters, by_name):
    history = storage.load_director_chat()
    view = st.session_state["view"]
    open_character = view.get("name") if view["kind"] == "character" else None
    result = agents.route_command(text, story, chapters, characters, history, open_character)
    action, name = result["action"], result["character"]
    reply = result["reply"]

    if action == "ask_character":
        # Hand the question to the character and switch the conversation to them.
        agents.character_reply(by_name[name], result["message"] or text)
        ui.defer("chat_with", name)
        return

    if action == "chapter_instruction":
        ui.go("compose")
        if "draft" in st.session_state:
            reply = "There's a draft waiting for your review in the editor. Finish or discard it first."
        else:
            ui.defer("compose_mode", "Write with the cast")
            ui.defer("instruction", result["instruction"])
            reply = f"{reply} I've put it in the editor. Check it, then press Generate."

    elif action == "edit_character":
        char = by_name[name]
        changes = {f: v for f, v in result["card"].items() if v and v != char["card"][f]}
        ui.go("character", name=name)
        if changes:
            st.session_state["proposal"] = {"character": name, "changes": changes, "said": text}
            ui.defer(f"section_{name}", "Profile")
            reply = f"{reply} Review the suggested changes to {name}'s profile and press Apply."

    elif action == "new_character":
        ui.defer("new_name", name)
        for field in storage.CARD_FIELDS:
            ui.defer(f"new_{field}", result["card"][field] or "")
        ui.go("new_character")
        reply = f"{reply} I've drafted {name}'s profile in the editor. Check it and press Create character."

    history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply.strip()}]
    storage.save_director_chat(history)
