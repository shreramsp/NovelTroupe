"""Small shared UI helpers: navigation, state, avatars, and safe HTML rendering."""

import html
import re
from pathlib import Path

import streamlit as st

import agents

DIRECTOR = "Director"
FORGOTTEN_AFTER = 3  # chapters of absence before a character is flagged "Forgotten"
PALETTE = ["#5046e5", "#0f766e", "#b45309", "#be185d", "#1d4ed8", "#7c3aed", "#047857", "#c2410c"]
CSS_FILE = Path(__file__).parent / "style.css"


# ---------- page setup ----------

def load_css():
    st.html(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>")


def css(rules):
    """Inject a few extra CSS rules (used for per-character avatar colours)."""
    st.html(f"<style>{rules}</style>")


# ---------- navigation and state ----------

def go(kind, **params):
    """Open a screen in the center panel. Safe to use as an on_click callback."""
    st.session_state["view"] = {"kind": kind, **params}


def open_character(name):
    """Open a character's profile and switch the chat to them."""
    go("character", name=name)
    st.session_state["chat_with"] = name


def defer(key, value):
    """Set a widget's value on the next run (Streamlit forbids changing it after it was drawn)."""
    st.session_state.setdefault("_pending", {})[key] = value


def apply_pending():
    for key, value in st.session_state.pop("_pending", {}).items():
        st.session_state[key] = value


def toast(message):
    st.session_state["_toast"] = message


def show_toast():
    if message := st.session_state.pop("_toast", None):
        st.toast(message, icon=":material/check_circle:")


# ---------- story facts ----------

def last_appearance(name, chapters):
    numbers = [c["number"] for c in chapters if name in c["present"]]
    return max(numbers) if numbers else None


def is_forgotten(name, chapters):
    latest = max((c["number"] for c in chapters), default=0)
    return latest - (last_appearance(name, chapters) or 0) >= FORGOTTEN_AFTER


def chapter_title(ch):
    return ch.get("title") or f"Chapter {ch['number']}"


# ---------- avatars and HTML ----------

def color_for(name):
    return PALETTE[sum(map(ord, name)) % len(PALETTE)]


def avatar(name, size=""):
    if name == DIRECTOR:
        return f'<span class="sa-avatar director {size}">✦</span>'
    return (f'<span class="sa-avatar {size}" style="background:{color_for(name)}">'
            f'{html.escape(name[:1].upper())}</span>')


def rich(text):
    """Escape model/author text for HTML, keeping line breaks and *italics* / **bold**."""
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"\*(.+?)\*", r"<em>\1</em>", out)
    return out.replace("\n", "<br>")


def paragraphs(text):
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "".join(f"<p>{rich(p)}</p>" for p in parts)


def css_string(text):
    """A value that is safe inside a CSS content: "..." rule."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


# ---------- input ----------

def read_input(value, names):
    """Text from a st.chat_input(accept_audio=True) value, transcribing any voice recording.

    Returns (text, used_voice).
    """
    if not value:
        return "", False
    text = (value.text or "").strip()
    if value.audio is None:
        return text, False
    mime = value.audio.type or "audio/wav"
    audio_format = "mp3" if ("mpeg" in mime or "mp3" in mime) else "wav"
    with st.spinner("Listening..."):
        heard = agents.transcribe(value.audio.getvalue(), audio_format, names)
    return f"{text} {heard}".strip(), True


def addressed_to(text, names):
    """Who a message is explicitly addressed to: "Hey Hale, ...", "@Hale ...", "Hale: ...". Else None."""
    for name in sorted(names, key=len, reverse=True):
        n = re.escape(name)
        if re.match(rf"^\s*(?:(?:hey|hi|hello|ok|okay|yo)[\s,]+|@)\s*{n}\b", text, re.IGNORECASE):
            return name
        if re.match(rf"^\s*{n}\s*[,:]", text, re.IGNORECASE):
            return name
    return None
