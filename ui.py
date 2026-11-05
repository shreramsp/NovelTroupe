"""Shared UI helpers: navigation, sign-in, theme, avatars and safe HTML rendering."""

import html
import re
import secrets
import time
from pathlib import Path

import streamlit as st

import accounts
import agents
import formats

APP_NAME = "NovelTroupe"
TAGLINE = "Write with characters who remember."
DIRECTOR = "Director"
PALETTE = ["#2f6b5b", "#b5583a", "#2b4a6f", "#a7782a", "#7a3b3b", "#3f6e7a", "#66753a", "#5b6170"]
COVERS = [("#1f4d43", "#2b6356"), ("#7a2e2a", "#94403a"), ("#1f3a5a", "#2c4f78"), ("#8a6326", "#a77b36"),
          ("#3d4a3f", "#526354"), ("#5b3a29", "#7a4f37"), ("#2a5c66", "#3a7480"), ("#4a4f57", "#636a74")]
COOKIE = "ns_session"
HERE = Path(__file__).parent


# =====================================================================
# Page setup: CSS, theme, and small bits of browser JavaScript
# =====================================================================

def theme_type():
    """'light' or 'dark' - whatever the browser is showing."""
    return "dark" if st.context.theme.type == "dark" else "light"


def load_css():
    css_text = (HERE / "style.css").read_text(encoding="utf-8")
    if theme_type() == "dark":
        css_text += (HERE / "style-dark.css").read_text(encoding="utf-8")
    st.html(f"<style>{css_text}</style>")


def css(rules):
    """Inject a few extra CSS rules (per-page backgrounds, per-character avatar colours...)."""
    st.html(f"<style>{rules}</style>")


def browser_action(js):
    """Run a line of JavaScript in the browser on the next run (cookies, theme switch)."""
    st.session_state.setdefault("_js", []).append(js)


def run_browser_actions():
    scripts = st.session_state.pop("_js", [])
    if scripts:
        with st.container(key="browser_actions"):  # hidden by CSS
            st.html(f"<script>{' '.join(scripts)}</script><!-- {secrets.token_hex(4)} -->",
                    unsafe_allow_javascript=True)


def toggle_theme():
    """on_click: switch Streamlit's own light/dark theme (it is remembered by the browser)."""
    target = "Light" if theme_type() == "dark" else "Dark"
    browser_action('localStorage.setItem("stActiveTheme-" + window.location.pathname + "-v2", '
                   f'JSON.stringify("{target}")); window.location.reload();')


def theme_button(key):
    dark = theme_type() == "dark"
    st.button("", key=key, type="tertiary", on_click=toggle_theme,
              icon=":material/light_mode:" if dark else ":material/dark_mode:",
              help="Switch to light theme" if dark else "Switch to dark theme")


# =====================================================================
# Navigation (the page lives in the URL, so a reload keeps you where you were)
# =====================================================================

def nav(page="", **params):
    """Go to a page: "" (landing), "login", "signup", "library", "studio" (with story=<id>)."""
    st.query_params.clear()
    if page:
        st.query_params["page"] = page
    for key, value in params.items():
        st.query_params[key] = value


def page():
    return st.query_params.get("page", "")


# =====================================================================
# Signing in and out
# =====================================================================

def current_user():
    """The signed-in user, restoring the session from the browser cookie after a reload."""
    if "user" not in st.session_state:
        token = st.context.cookies.get(COOKIE)
        user = accounts.user_for_session(token)
        st.session_state["user"] = user
        st.session_state["token"] = token if user else None
    return st.session_state["user"]


def sign_in(user):
    token = accounts.start_session(user["id"])
    st.session_state["user"], st.session_state["token"] = user, token
    browser_action(f'document.cookie = "{COOKIE}={token}; path=/; max-age={accounts.SESSION_DAYS * 86400}; '
                   'SameSite=Lax";')


def sign_out():
    """on_click: end the session everywhere and go back to the landing page."""
    accounts.end_session(st.session_state.get("token"))
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state["user"] = None
    browser_action(f'document.cookie = "{COOKIE}=; path=/; max-age=0; SameSite=Lax";')
    nav()


def account_menu(user, key):
    with st.popover(user["name"].split()[0], icon=":material/account_circle:", key=key):
        st.markdown(f"**{user['name']}**  \n{user['email']}")
        st.button("Your library", icon=":material/library_books:", key=f"{key}_library", type="tertiary",
                  on_click=nav, args=("library",))
        st.button("Sign out", icon=":material/logout:", key=f"{key}_signout", type="tertiary", on_click=sign_out)


# =====================================================================
# Studio state
# =====================================================================

def enter_story(story_id):
    """Opening a different story starts with a clean studio (no leftover drafts or chats)."""
    if st.session_state.get("_story") != story_id:
        keep = {"user", "token", "_js", "_toast"}
        for key in list(st.session_state):
            if key not in keep:
                del st.session_state[key]
        st.session_state["_story"] = story_id


def go(kind, **params):
    """Open a screen in the studio's center panel. Safe to use as an on_click callback."""
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


# =====================================================================
# Story facts and formatting
# =====================================================================

def last_seen(name, chapters):
    """The last unit (chapter, scene, act) the character was in, or None."""
    return next((c for c in reversed(chapters) if name in c["present"]), None)


def last_seen_label(fmt, name, chapters, short=False):
    chapter = last_seen(name, chapters)
    if chapter is None:
        return None
    place = formats.place_of(fmt, chapter)
    return (formats.short_label if short else formats.label)(fmt, place, chapter["number"])


def is_forgotten(name, chapters, fmt):
    """Absent for the format's limit: 3 chapters, 10 film scenes or 2 TV episodes."""
    if not chapters:
        return False
    steps = [formats.step(fmt, formats.place_of(fmt, c), c["number"]) for c in chapters]
    order = sorted(set(steps))
    seen = [steps[i] for i, c in enumerate(chapters) if name in c["present"]]
    last = order.index(max(seen)) if seen else -1
    return (len(order) - 1) - last >= fmt["forgotten_after"]


def chapter_title(ch):
    return ch.get("title") or f"Chapter {ch['number']}"


def time_ago(timestamp):
    seconds = max(0, time.time() - timestamp)
    for limit, size, unit in ((60, 1, None), (3600, 60, "min"), (86400, 3600, "h"), (86400 * 30, 86400, "d")):
        if seconds < limit:
            return "just now" if unit is None else f"{int(seconds // size)} {unit} ago"
    return time.strftime("%b %d, %Y", time.localtime(timestamp))


def color_for(name):
    return PALETTE[sum(map(ord, name)) % len(PALETTE)]


def cover_for(story_id):
    return COVERS[sum(map(ord, story_id)) % len(COVERS)]


def logo(size=""):
    return f'<span class="sa-logo {size}">N</span>'


def avatar(name, size=""):
    if name == DIRECTOR:
        return f'<span class="sa-avatar director {size}">D</span>'
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


SCENE_HEADING = re.compile(r"^(INT\.?/EXT|EXT\.?/INT|INT|EXT|EST|I/E)[\.\s]", re.IGNORECASE)
TRANSITION = re.compile(r"^[A-Z0-9 .'-]+(TO:|OUT\.|IN:)$")


def _is_cue(line):
    """A character name before dialogue: short, all capitals (extensions like (V.O.) allowed)."""
    letters = re.sub(r"\(.*?\)", "", line)
    return (any(ch.isalpha() for ch in letters) and line == line.upper() and len(line) <= 40
            and not SCENE_HEADING.match(line) and not TRANSITION.match(line))


def screenplay(text):
    """Render screenplay-format text (scene headings, action, character cues, dialogue) as HTML."""
    lines = text.replace("**", "").replace("\r", "").split("\n")
    out, in_dialogue = [], False
    for i, raw in enumerate(lines):
        line = raw.strip()
        following = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if not line:
            in_dialogue = False
        elif SCENE_HEADING.match(line) or (line.startswith(".") and len(line) > 1 and line[1] != "."):
            out.append(f'<div class="sp-scene">{html.escape(line.lstrip(".").upper())}</div>')
            in_dialogue = False
        elif TRANSITION.match(line):
            out.append(f'<div class="sp-transition">{html.escape(line)}</div>')
            in_dialogue = False
        elif _is_cue(line) and following and not _is_cue(following):
            out.append(f'<div class="sp-cue">{html.escape(line)}</div>')
            in_dialogue = True
        elif in_dialogue:
            kind = "sp-paren" if line.startswith("(") else "sp-dialogue"
            out.append(f'<div class="{kind}">{rich(line)}</div>')
        else:
            out.append(f'<div class="sp-action">{rich(line)}</div>')
    return "".join(out)


def css_string(text):
    """A value that is safe inside a CSS content: "..." rule."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


# =====================================================================
# Input
# =====================================================================

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
