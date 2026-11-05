"""The Cast room ("let them talk"): characters talk to each other while the author watches.

Two modes:
  Talk it through   a question for the characters ("Should Park tell Nora about the order?")
  Play a scene      a situation to improvise ("Park and Nora at the diner, 9 p.m.")

Each character speaks as their own agent with only their own memories, so secrets stay secret.
The author can cut in at any time ("Hey Park, tell her"). It is a rehearsal: nothing said here
becomes a memory. When it is done, the Director sums it up and can turn it into the next chapter.
"""

import html
import re

import streamlit as st

import agents
import ui
from agents import AUTHOR
from ui import DIRECTOR

TALK, SCENE = "Talk it through", "Play a scene"
MODES = {TALK: "talk", SCENE: "scene"}
MAX_ROUND = 4  # lines per round, so a round takes about a minute


def _room():
    return st.session_state.setdefault("room", {"topic": "", "lines": [], "summary": None})


def next_speaker(cast, lines):
    """Whoever was just addressed by name; otherwise whoever has waited longest."""
    last = lines[-1] if lines else None
    if last:
        for name in cast:
            if name != last["speaker"] and re.search(rf"\b{re.escape(name)}\b", last["text"], re.IGNORECASE):
                return name
    spoken = [line["speaker"] for line in lines]

    def last_spoke(name):
        return max((i for i, s in enumerate(spoken) if s == name), default=-1)

    candidates = [n for n in cast if not last or n != last["speaker"]] or cast
    return min(candidates, key=last_spoke)


def _bubble(line):
    if line["speaker"] == AUTHOR:
        return f'<div class="sa-msg author"><div class="sa-bubble">{ui.rich(line["text"])}</div></div>'
    return (f'<div class="sa-msg">{ui.avatar(line["speaker"])}<div class="sa-body">'
            f'<div class="sa-name">{html.escape(line["speaker"])}</div>'
            f'<div class="sa-bubble">{ui.rich(line["text"])}</div></div></div>')


# =====================================================================
# The panel
# =====================================================================

def room_panel(story, fmt, characters):
    """Draw the Cast room. Returns (slot, value) like chat.chat_panel; handle() processes the value."""
    room, names = _room(), [c["name"] for c in characters]
    if len(names) < 2:
        st.html('<div class="sa-thread room"><div class="sa-welcome"><span class="sa-icon lg">groups</span><br>'
                '<b>Cast room</b>Add at least two characters to let them talk to each other.</div></div>')
        return None, None

    st.session_state.setdefault("room_mode", TALK)
    st.session_state["room_cast"] = [n for n in st.session_state.get("room_cast", names[:3]) if n in names]
    with st.container(key="room_setup"):
        st.segmented_control("Mode", [TALK, SCENE], key="room_mode", required=True, label_visibility="collapsed",
                             width="stretch")
        st.pills("Who's in the room", names, selection_mode="multi", key="room_cast", label_visibility="collapsed")

    st.html(_thread_html(room))
    if room["lines"] and not room["summary"]:
        with st.container(horizontal=True, key="room_actions"):
            st.button("Keep going", icon=":material/play_arrow:", key="room_more", on_click=_set_action,
                      args=("more",))
            st.button("Wrap up", icon=":material/summarize:", key="room_wrap", on_click=_set_action, args=("wrap",))
            st.button("Clear", icon=":material/restart_alt:", key="room_clear", type="tertiary", on_click=_clear)
    if room["summary"]:
        _summary_card(story, fmt, room)

    slot = st.container()
    placeholder = ("Ask them a question, or say “Hey Park…”" if st.session_state["room_mode"] == TALK
                   else "Describe a situation for them to play…")
    if room["lines"]:
        placeholder = "Cut in, or say “Hey Park…”"
    value = st.chat_input(placeholder, key="room_box", accept_audio=True)

    action = st.session_state.pop("room_action", None)
    if action == "more":
        _run_round(slot, characters)
    elif action == "wrap":
        _wrap_up(slot, story)
    return slot, value


def _thread_html(room):
    if not room["lines"]:
        return ('<div class="sa-thread room"><div class="sa-welcome"><span class="sa-icon lg">groups</span><br>'
                '<b>Let them talk</b>Pick who\'s in the room, then ask them a question or set a scene. Each '
                'character speaks for themselves and only knows what they lived through. Nothing here becomes a '
                'memory.</div></div>')
    topic = (f'<div class="room-topic"><span class="sa-icon">'
             f'{"forum" if room.get("mode") == "talk" else "theaters"}</span>{ui.rich(room["topic"])}</div>')
    bubbles = [topic] + [_bubble(line) for line in room["lines"]]
    return '<div class="sa-thread room">' + "".join(reversed(bubbles)) + "</div>"  # column-reverse: newest last


def _set_action(action):
    st.session_state["room_action"] = action


def _clear():
    st.session_state["room"] = {"topic": "", "lines": [], "summary": None}


# =====================================================================
# Running the room
# =====================================================================

def handle(value, slot, story, chapters, characters):
    """A message typed or spoken in the Cast room: a new topic, or the author cutting in."""
    room = _room()
    try:
        text, _ = ui.read_input(value, [c["name"] for c in characters])
        if not text:
            return
        if len(st.session_state.get("room_cast", [])) < 2:
            with slot:
                st.warning("Pick at least two characters for the room.")
            return
        if not room["lines"] or room["summary"]:  # a fresh conversation
            room.update(topic=text, lines=[], summary=None, mode=MODES[st.session_state["room_mode"]])
            with slot:
                st.html(f'<div class="room-topic"><span class="sa-icon">forum</span>{ui.rich(text)}</div>')
        else:  # the author cuts in
            room["lines"].append({"speaker": AUTHOR, "text": text})
            with slot:
                st.html(_bubble(room["lines"][-1]))
        _run_round(slot, characters)
    except Exception as e:
        with slot:
            st.error(f"Something went wrong: {e}")


def _run_round(slot, characters):
    """Let up to MAX_ROUND characters speak, showing each line as soon as it arrives."""
    room = _room()
    by_name = {c["name"]: c for c in characters}
    cast = [n for n in st.session_state.get("room_cast", []) if n in by_name]
    room["mode"] = room.get("mode") or MODES[st.session_state["room_mode"]]
    for _ in range(min(MAX_ROUND, max(2, len(cast)))):
        speaker = next_speaker(cast, room["lines"])
        with slot:
            typing = st.empty()
            typing.html(f'<div class="sa-typing">{html.escape(speaker)} is thinking…</div>')
        others = [n for n in cast if n != speaker]
        line = agents.room_line(by_name[speaker], others, room["mode"], room["topic"], room["lines"])
        room["lines"].append({"speaker": speaker, "text": line})
        typing.html(_bubble(room["lines"][-1]))
    st.rerun()


def _wrap_up(slot, story):
    room = _room()
    with slot, st.spinner("The Director is summing it up..."):
        try:
            room["summary"] = agents.room_summary(story, room["mode"], room["topic"], room["lines"])
        except Exception as e:
            st.error(f"Could not sum it up: {e}")
            return
    st.rerun()


def _summary_card(story, fmt, room):
    summary = room["summary"]
    insights = "".join(f"<li>{ui.rich(i)}</li>" for i in summary["insights"])
    st.html(f'<div class="room-summary"><div class="room-summary-head">{ui.avatar(DIRECTOR, "sm")}Director\'s notes'
            f'</div><p>{ui.rich(summary["summary"])}</p>{f"<ul>{insights}</ul>" if insights else ""}</div>')
    with st.container(horizontal=True, key="room_next"):
        st.button(f"Write it as the next {fmt['unit'].lower()}", type="primary", icon=":material/edit_note:",
                  key="room_write", on_click=_write_next, args=(summary["instruction"],))
        st.button("Send to Director", icon=":material/forum:", key="room_send", on_click=_send_to_director,
                  args=(room,))
        st.button("New conversation", icon=":material/restart_alt:", key="room_new", type="tertiary", on_click=_clear)


def _write_next(instruction):
    """on_click: put the Director's instruction in the editor."""
    ui.go("compose")
    st.session_state["compose_mode"] = "Write with the cast"
    st.session_state["instruction"] = instruction
    ui.toast("The editor has the instruction. Check it, then press Generate.")


def _send_to_director(room):
    """on_click: switch to the Director chat; chat.py adds the note once the story is loaded."""
    kind = "talked through" if room["mode"] == "talk" else "played"
    st.session_state["director_note"] = f"From the Cast room ({kind}: {room['topic']})\n\n{room['summary']['summary']}"
    st.session_state["right_tab"] = "Chat"
    st.session_state["chat_with"] = DIRECTOR
