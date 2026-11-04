"""The left panel (chapters + characters) and the screens in the center panel."""

import html

import streamlit as st

import agents
import storage
import ui
from ui import go

WITH_AGENTS, MYSELF = "Write with the cast", "Write it myself"
PROFILE, MEMORIES = "Profile", "Memories"
READ, EDIT = "Read", "Edit"


def h(text):
    return html.escape(text)


# =====================================================================
# Left panel
# =====================================================================

def left_panel(app_name, story, chapters, characters):
    view = st.session_state["view"]
    st.html(f'<div class="sa-brand"><span class="sa-logo">{h(app_name[:1])}</span>'
            f'<span class="sa-brand-name">{h(app_name)}</span></div>')
    st.button(story["title"] or "Untitled story", key="nav_story", icon=":material/auto_stories:",
              type="tertiary", width="stretch", on_click=go, args=("story",), help="Story settings and outline")

    # --- chapters (top half) ---
    with st.container(key="head_chapters", horizontal=True, vertical_alignment="center"):
        st.html('<div class="sa-section-label">Chapters</div>')
        st.button("New", key="nav_compose", icon=":material/add:", type="tertiary", on_click=go, args=("compose",))
    with st.container(key="chapters_list"):
        if not chapters:
            st.html('<div class="sa-empty">No chapters yet. Start the first one.</div>')
        for ch in chapters:
            st.button(ui.chapter_title(ch), key=f"chap_{ch['number']}", type="tertiary", width="stretch",
                      on_click=go, args=("chapter",), kwargs={"number": ch["number"]}, help=ch["summary"])

    # --- characters (bottom half) ---
    with st.container(key="head_characters", horizontal=True, vertical_alignment="center"):
        st.html('<div class="sa-section-label">Characters</div>')
        st.button("New", key="nav_new_character", icon=":material/add:", type="tertiary",
                  on_click=go, args=("new_character",))
    with st.container(key="characters_list"):
        if not characters:
            st.html('<div class="sa-empty">No characters yet.</div>')
        for i, char in enumerate(characters):
            st.button(char["name"], key=f"char_{i}", type="tertiary", width="stretch",
                      on_click=ui.open_character, args=(char["name"],))

    # Per-row decoration (chapter numbers, avatars, last-seen badges, the selected row).
    rules = []
    for ch in chapters:
        number = ch["number"]
        rules.append(f".st-key-chap_{number} button::before {{ content: {ui.css_string(str(number).zfill(2))}; }}")
    for i, char in enumerate(characters):
        name = char["name"]
        last = ui.last_appearance(name, chapters)
        badge = "Forgotten" if ui.is_forgotten(name, chapters) else (f"Ch {last}" if last else "New")
        rules.append(f".st-key-char_{i} button::before {{ content: {ui.css_string(name[:1].upper())}; "
                     f"background: {ui.color_for(name)}; }}")
        rules.append(f".st-key-char_{i} button::after {{ content: {ui.css_string(badge)}; }}")
        if badge == "Forgotten":
            rules.append(f".st-key-char_{i} button::after {{ color: var(--sa-warn); background: var(--sa-warn-tint); "
                         f"padding: 1px 8px; border-radius: 999px; font-weight: 600; }}")
    selected = {
        "story": "nav_story",
        "compose": "nav_compose",
        "new_character": "nav_new_character",
        "chapter": f"chap_{view.get('number')}",
        "character": next((f"char_{i}" for i, c in enumerate(characters) if c["name"] == view.get("name")), None),
    }.get(view["kind"])
    if selected:
        rules.append(f".st-key-{selected} button {{ background: var(--sa-accent-tint) !important; }} "
                     f".st-key-{selected} button p {{ color: var(--sa-accent) !important; font-weight: 600; }}")
    ui.css("\n".join(rules))


# =====================================================================
# Center panel
# =====================================================================

def center_panel(story, chapters, characters):
    view = st.session_state["view"]
    by_number = {c["number"]: c for c in chapters}
    by_name = {c["name"]: c for c in characters}

    if view["kind"] == "chapter" and view.get("number") in by_number:
        chapter_view(by_number[view["number"]], chapters)
    elif view["kind"] == "character" and view.get("name") in by_name:
        character_view(by_name[view["name"]], chapters)
    elif view["kind"] == "new_character":
        new_character_view()
    elif view["kind"] == "story":
        story_view(story, characters, chapters)
    else:
        compose_view(story, chapters, characters)


def _header(eyebrow, title, subtitle=None):
    st.html(f'<div class="sa-eyebrow">{h(eyebrow)}</div><div class="sa-title">{h(title)}</div>'
            + (f'<p class="sa-subtitle">{h(subtitle)}</p>' if subtitle else ""))


# ---------- reading and editing a chapter ----------

def chapter_view(ch, chapters):
    n = ch["number"]
    with st.container(horizontal=True, vertical_alignment="center"):
        st.html(f'<div class="sa-eyebrow">Chapter {n}</div>')
        st.space("stretch")
        st.session_state.setdefault(f"mode_{n}", READ)
        mode = st.segmented_control("Mode", [READ, EDIT], key=f"mode_{n}", required=True,
                                    label_visibility="collapsed")
        with st.popover("Notes", icon=":material/description:"):
            _chapter_notes(ch)

    words = len(ch["text"].split())
    chips = "".join(f'<span class="sa-chip">{ui.avatar(name, "sm")}{h(name)}</span>' for name in ch["present"])
    chips += f'<span class="sa-chip plain">{words:,} words · {max(1, round(words / 230))} min read</span>'
    st.html(f'<div class="sa-title">{h(ui.chapter_title(ch))}</div><div class="sa-meta">{chips}</div>')

    if mode == EDIT:
        with st.container(key="manuscript_editor"):
            new_text = st.text_area("Chapter text", value=ch["text"], height=620, key=f"text_{n}",
                                    label_visibility="collapsed")
        with st.container(horizontal=True):
            if st.button("Save changes", type="primary", icon=":material/check:", key=f"save_{n}"):
                ch["text"] = new_text
                storage.save_chapter(ch)
                ui.defer(f"mode_{n}", READ)
                ui.toast(f"Chapter {n} saved.")
                st.rerun()
            if st.button("Cancel", key=f"cancel_{n}"):
                ui.defer(f"mode_{n}", READ)
                st.rerun()
        return

    st.html(f'<article class="sa-manuscript">{ui.paragraphs(ch["text"])}</article>'
            '<div class="sa-divider">• • •</div>')
    numbers = [c["number"] for c in chapters]
    with st.container(horizontal=True):
        if n - 1 in numbers:
            st.button("Previous chapter", icon=":material/arrow_back:", key=f"prev_{n}",
                      on_click=go, args=("chapter",), kwargs={"number": n - 1})
        st.space("stretch")
        if n + 1 in numbers:
            st.button("Next chapter", icon=":material/arrow_forward:", key=f"next_{n}",
                      on_click=go, args=("chapter",), kwargs={"number": n + 1})
        else:
            st.button("Continue the story", icon=":material/edit_note:", type="primary", key=f"continue_{n}",
                      on_click=go, args=("compose",))


def _chapter_notes(ch):
    st.markdown("**Summary**")
    st.write(ch["summary"])
    st.markdown("**Your instruction**")
    st.caption(ch["instruction"])
    for o in ch["objections"]:
        verb = "accepted" if o["status"] == "accepted" else "overrode"
        st.markdown(f"**{o['character']}** objected, and you {verb} it: *{o['objection']}*")
    if ch["plan"]["beats"]:
        st.markdown("**Beats**")
        for number, beat in enumerate(ch["plan"]["beats"], start=1):
            st.markdown(f"{number}. {beat['text']}")
    if ch["reactions"]:
        st.markdown("**How the cast reacted**")
        for name, r in ch["reactions"].items():
            st.markdown(f"**{name}:** {r['reaction']}")


# ---------- writing the next chapter ----------

def compose_view(story, chapters, characters):
    n = storage.next_chapter_number()
    draft = st.session_state.get("draft")
    if draft:
        _header(f"Chapter {n} · Review", "Your cast has objections",
                "Nothing is saved yet. Accept rewrites that moment to fit the character. "
                "Override keeps it, and they play it against their will.")
        _objection_review(story, characters, draft)
        return

    _header(f"Chapter {n}", "What happens next?",
            "Describe the chapter and your cast will plan it, react in character, and write it with you. "
            "You can also tell the Director in the chat.")
    st.session_state.setdefault("compose_mode", WITH_AGENTS)
    mode = st.segmented_control("How", [WITH_AGENTS, MYSELF], key="compose_mode", required=True,
                                label_visibility="collapsed")

    if mode == MYSELF:
        with st.container(key="manuscript_editor"):
            text = st.text_area("Chapter text", key="own_text", height=560, label_visibility="collapsed",
                                placeholder="Start writing...")
        st.caption(f"{len(text.split()):,} words. When you save, each character remembers only the scenes they were in.")
        if st.button("Save chapter", type="primary", icon=":material/check:", disabled=not text.strip()):
            try:
                with st.spinner("Saving and updating what each character remembers..."):
                    chapter = agents.add_author_chapter(characters, text.strip())
                go("chapter", number=chapter["number"])
                ui.toast(f"Chapter {chapter['number']} saved.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not save the chapter: {e}")
        return

    instruction = st.text_area("Instruction", key="instruction", height=170, label_visibility="collapsed",
                               placeholder="e.g. Nora visits Park's shop to ask about Ridge 614. Joon overhears.")
    if st.button("Generate chapter", type="primary", icon=":material/auto_awesome:"):
        if not characters:
            st.warning("Add at least one character first.")
        elif not instruction.strip():
            st.warning("Describe what should happen first.")
        else:
            try:
                with st.status(f"Directing chapter {n}...", expanded=True) as status:
                    st.write("The director is planning the scene and the cast is reacting...")
                    draft = agents.draft_chapter(story, chapters, characters, instruction.strip())
                    if draft["objections"]:
                        st.session_state["draft"] = draft  # wait for the author's decisions
                        status.update(label="Your cast has objections", state="complete")
                    else:
                        st.write("Writing the chapter and updating memories...")
                        _finish(story, characters, draft)
                st.rerun()
            except Exception as e:
                st.error(f"Could not generate the chapter: {e}")


def _finish(story, characters, draft):
    chapter = agents.finish_chapter(story, characters, draft)
    st.session_state.pop("draft", None)
    go("chapter", number=chapter["number"])
    ui.toast(f"Chapter {chapter['number']} is ready.")


def _objection_review(story, characters, draft):
    beats = draft["plan"]["beats"]
    for i, obj in enumerate(draft["objections"]):
        with st.container(border=True):
            st.html(f'<div class="sa-chat-head">{ui.avatar(obj["character"])}'
                    f'<div><div class="sa-chat-name">{h(obj["character"])}</div>'
                    f'<div class="sa-chat-sub">objects to moment {obj["beat"]}</div></div></div>'
                    f'<div class="sa-quote">“{ui.rich(obj["objection"])}”</div>'
                    f'<div class="sa-beat">The moment: {h(beats[obj["beat"] - 1]["text"])}</div>')
            choice = st.segmented_control("Decision", ["Accept", "Override"], key=f"decision_{i}",
                                          label_visibility="collapsed")
            obj["status"] = {"Accept": "accepted", "Override": "overridden"}.get(choice, "pending")

    with st.expander("See the whole plan"):
        for number, beat in enumerate(beats, start=1):
            st.markdown(f"{number}. {beat['text']} *({', '.join(beat['characters'])})*")

    undecided = any(o["status"] == "pending" for o in draft["objections"])
    with st.container(horizontal=True):
        if st.button("Write chapter", type="primary", icon=":material/auto_awesome:", disabled=undecided):
            try:
                with st.spinner("Writing the chapter and updating memories... (about a minute)"):
                    _finish(story, characters, draft)
                st.rerun()
            except Exception as e:
                st.error(f"Could not write the chapter: {e}")
        if st.button("Discard", icon=":material/close:"):
            del st.session_state["draft"]
            st.rerun()
    if undecided:
        st.caption("Decide on each objection to continue.")


# ---------- characters ----------

def character_view(char, chapters):
    name = char["name"]
    last = ui.last_appearance(name, chapters)
    chips = f'<span class="sa-chip plain">{"Last seen in chapter " + str(last) if last else "Not in a chapter yet"}</span>'
    if ui.is_forgotten(name, chapters):
        chips += f'<span class="sa-chip warn">Forgotten · absent {ui.FORGOTTEN_AFTER}+ chapters</span>'
    st.html(f'<div style="display:flex;gap:18px;align-items:center;margin-bottom:8px">{ui.avatar(name, "lg")}'
            f'<div><div class="sa-eyebrow">Character</div><div class="sa-title" style="margin:2px 0 8px">{h(name)}</div>'
            f'<div class="sa-meta">{chips}</div></div></div>')

    proposal = st.session_state.get("proposal")
    if proposal and proposal["character"] == name:
        _proposal_box(char, proposal)

    key = f"section_{name}"
    st.session_state.setdefault(key, PROFILE)
    section = st.segmented_control("Section", [PROFILE, MEMORIES], key=key, required=True,
                                   label_visibility="collapsed")
    if section == PROFILE:
        with st.form(f"card_form_{name}", border=False):
            card = _card_fields(f"card_{name}", char["card"])
            if st.form_submit_button("Save profile", type="primary", icon=":material/check:"):
                char["card"] = card
                storage.save_character(char)
                ui.toast(f"Saved {name}'s profile.")
                st.rerun()
    else:
        _memories(char)


def _card_fields(prefix, card=None):
    """Two columns of card fields. Returns {field: value}."""
    left, right = st.columns(2)
    values = {}
    for i, field in enumerate(storage.CARD_FIELDS):
        column = left if i % 2 == 0 else right
        kwargs = {"value": card[field]} if card is not None else {}
        values[field] = column.text_area(field.capitalize(), height=140, key=f"{prefix}_{field}", **kwargs)
    return values


def _memories(char):
    events = {}
    for m in char["memories"]:
        events.setdefault(m["chapter"], {})["memory"] = m["text"]
    for u in char["profile_updates"]:
        events.setdefault(u["chapter"], {})["change"] = u["text"]
    if not events:
        st.html(f'<div class="sa-empty">{h(char["name"])} hasn\'t lived through any chapters yet. '
                'They only remember scenes they are in.</div>')
        return
    items = ""
    for number in sorted(events):
        e = events[number]
        items += f'<div class="sa-event"><div class="sa-event-label">Chapter {number}</div>'
        if "memory" in e:
            items += f'<div class="sa-event-text">{ui.rich(e["memory"])}</div>'
        if "change" in e:
            items += f'<div class="sa-event-change">Changed: {ui.rich(e["change"])}</div>'
        items += "</div>"
    st.html(f'<div class="sa-timeline">{items}</div>')


def _proposal_box(char, proposal):
    """Profile changes suggested by the Director, waiting for Apply / Discard."""
    name = char["name"]
    with st.container(border=True):
        st.html(f'<div class="sa-chat-head">{ui.avatar(ui.DIRECTOR)}<div><div class="sa-chat-name">'
                f'Suggested changes to {h(name)}</div><div class="sa-chat-sub">From: “{h(proposal["said"])}”</div>'
                '</div></div>')
        for field, new in proposal["changes"].items():
            st.markdown(f"**{field.capitalize()}**")
            before, after = st.columns(2)
            before.caption("Before")
            before.write(char["card"][field] or "(empty)")
            after.caption("After")
            after.write(new)
        with st.container(horizontal=True):
            if st.button("Apply", type="primary", icon=":material/check:", key="apply_proposal"):
                char["card"].update(proposal["changes"])
                storage.save_character(char)
                for field in storage.CARD_FIELDS:  # so the profile form shows the new values
                    st.session_state.pop(f"card_{name}_{field}", None)
                del st.session_state["proposal"]
                ui.toast(f"Updated {name}'s profile.")
                st.rerun()
            if st.button("Discard", icon=":material/close:", key="discard_proposal"):
                del st.session_state["proposal"]
                st.rerun()


def new_character_view():
    _header("Cast", "New character",
            "Fill in what you know; you can change everything later. "
            "Or describe them to the Director in the chat and the profile is filled in for you.")
    with st.form("new_character_form", border=False):
        name = st.text_input("Name", key="new_name")
        card = _card_fields("new")
        if st.form_submit_button("Create character", type="primary", icon=":material/person_add:"):
            name = name.strip()
            if not storage.safe_name(name):
                st.error("Please give the character a name (letters, numbers, spaces).")
            elif storage.character_exists(name):
                st.error(f"A character named {name!r} already exists.")
            else:
                storage.save_character(storage.new_character(name, card))
                for key in ["new_name"] + [f"new_{f}" for f in storage.CARD_FIELDS]:
                    st.session_state.pop(key, None)
                ui.open_character(name)
                ui.toast(f"Created {name}.")
                st.rerun()


# ---------- story settings ----------

def story_view(story, characters, chapters):
    _header("Story", story["title"] or "Untitled story")
    words = sum(len(ch["text"].split()) for ch in chapters)
    with st.container(horizontal=True):
        st.metric("Chapters", len(chapters), border=True)
        st.metric("Characters", len(characters), border=True)
        st.metric("Words", f"{words:,}", border=True)
    with st.form("story_form", border=False):
        title = st.text_input("Title", value=story["title"])
        outline = st.text_area("Outline", value=story["outline"], height=300,
                               help="The big picture. The director reads this before planning every chapter.")
        if st.form_submit_button("Save", type="primary", icon=":material/check:"):
            storage.save_story({"title": title, "outline": outline})
            ui.toast("Story saved.")
            st.rerun()
