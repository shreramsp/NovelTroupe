"""The studio's left panel (structure + characters) and the screens in its center panel.

Everything here follows the story's format (formats.py): a novel lists chapters, a light novel
groups chapters into volumes, a film lists scenes by act, and a TV series lists episodes with
their acts. Film and TV are shown and edited as screenplays.
"""

import html

import streamlit as st

import agents
import comic
import formats
import knowledge
import storage
import ui
from ui import go

WITH_AGENTS, MYSELF = "Write with the cast", "Write it myself"
PROFILE, MEMORIES = "Profile", "Memories"
READ, EDIT = "Read", "Edit"
SCRIPT_PLACEHOLDER = "INT. LOCATION - DAY\n\nWhat we see.\n\nCHARACTER\nWhat they say."
# Character-fit bands: 60%+ is in character (not shown), 35-59% "unusual" (a soft note, kept by default),
# under 35% "out of character" (the author has to decide before saving).
FIT_OK, FIT_LOW = 60, 35


def h(text):
    return html.escape(text)


def _position(fmt, chapter):
    return formats.label(fmt, formats.place_of(fmt, chapter), chapter["number"])


# =====================================================================
# Left panel
# =====================================================================

def left_panel(story, chapters, characters):
    fmt = formats.get(story["format"])
    view = st.session_state["view"]
    with st.container(key="studio_brand", horizontal=True, vertical_alignment="center"):
        st.button("Library", key="nav_library", type="tertiary", icon=":material/arrow_back:",
                  on_click=ui.nav, args=("library",), help="All your stories")
        st.space("stretch")
        ui.theme_button("theme_studio")
        ui.account_menu(st.session_state["user"], "account_studio")
    st.button(story["title"] or "Untitled story", key="nav_story", icon=f":material/{fmt['icon']}:",
              type="tertiary", width="stretch", on_click=go, args=("story",),
              help=f"{fmt['name']} · story settings and outline")
    # Comic is a headline feature, so it gets a tile of its own (an invisible button covers the tile).
    with st.container(key="comic_tile"):
        st.html('<div class="cm-tile"><span class="cm-tile-icon sa-icon">view_day</span><div class="cm-tile-text">'
                '<div class="cm-tile-title">Comic studio</div><div class="cm-tile-sub">Chapters into webtoons'
                '</div></div><span class="cm-tile-go sa-icon">arrow_forward</span></div>')
        st.button("Open the comic studio", key="nav_comics", on_click=_open_comics)
    st.button("Who knows what", key="nav_knowledge", icon=":material/hub:", type="tertiary", width="stretch",
              on_click=go, args=("knowledge",), help="Every secret in the story, and who knows it")

    # --- the story's structure (top half) ---
    with st.container(key="head_chapters", horizontal=True, vertical_alignment="center"):
        st.html(f'<div class="sa-section-label">{fmt["section"]}</div>')
        st.button("New", key="nav_compose", icon=":material/add:", type="tertiary", on_click=go, args=("compose",))
    with st.container(key="chapters_list"):
        if not chapters:
            st.html(f'<div class="sa-empty">Nothing written yet. Start your first {fmt["unit"].lower()}.</div>')
        show_groups, current_group = formats.show_group_titles(fmt, chapters), None
        for ch in chapters:
            place = formats.place_of(fmt, ch)
            group = formats.group_title(fmt, place)
            if show_groups and group != current_group:
                st.html(f'<div class="sa-group">{h(group)}</div>')
                current_group = group
            name = ui.chapter_title(ch)
            if formats.is_tv(fmt):
                name = f"{formats.unit_label(fmt, place)} · {ch.get('title', '')}".rstrip(" ·")
            st.button(name, key=f"chap_{ch['number']}", type="tertiary", width="stretch",
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

    # Per-row decoration (unit numbers, avatars, last-seen badges, the selected row).
    rules = []
    for ch in chapters:
        badge = "" if formats.is_tv(fmt) else str(ch["number"]).zfill(2)
        rules.append(f".st-key-chap_{ch['number']} button::before {{ content: {ui.css_string(badge)}; "
                     f"{'width: 4px;' if not badge else ''} }}")
    for i, char in enumerate(characters):
        name = char["name"]
        seen = ui.last_seen_label(fmt, name, chapters, short=True)
        badge = "Forgotten" if ui.is_forgotten(name, chapters, fmt) else (seen or "New")
        rules.append(f".st-key-char_{i} button::before {{ content: {ui.css_string(name[:1].upper())}; "
                     f"background: {ui.color_for(name)}; }}")
        rules.append(f".st-key-char_{i} button::after {{ content: {ui.css_string(badge)}; }}")
        if badge == "Forgotten":
            rules.append(f".st-key-char_{i} button::after {{ color: var(--sa-warn); background: var(--sa-warn-tint); "
                         f"padding: 1px 8px; border-radius: 999px; font-weight: 600; }}")
    selected = {
        "story": "nav_story",
        "knowledge": "nav_knowledge",
        "comics": None,  # the Comic tile shows its own selected state (below)
        "compose": "nav_compose",
        "new_character": "nav_new_character",
        "chapter": f"chap_{view.get('number')}",
        "character": next((f"char_{i}" for i, c in enumerate(characters) if c["name"] == view.get("name")), None),
    }.get(view["kind"])
    if view["kind"] == "comics":
        rules.append(".st-key-comic_tile .cm-tile { box-shadow: 0 0 0 2px var(--sa-gold), var(--sa-shadow); }")
    if selected:
        rules.append(f".st-key-{selected} button {{ background: var(--sa-accent-tint) !important; }} "
                     f".st-key-{selected} button p {{ color: var(--sa-accent) !important; font-weight: 600; }}")
    ui.css("\n".join(rules))


# =====================================================================
# Center panel
# =====================================================================

def center_panel(story, chapters, characters):
    fmt = formats.get(story["format"])
    view = st.session_state["view"]
    by_number = {c["number"]: c for c in chapters}
    by_name = {c["name"]: c for c in characters}

    if view["kind"] == "chapter" and view.get("number") in by_number:
        chapter_view(by_number[view["number"]], chapters, fmt, story, characters)
    elif view["kind"] == "knowledge":
        knowledge.knowledge_view(story, chapters, characters, fmt)
    elif view["kind"] == "comics":
        comic.comic_view(story, chapters, characters, fmt)
    elif view["kind"] == "character" and view.get("name") in by_name:
        character_view(by_name[view["name"]], chapters, fmt)
    elif view["kind"] == "new_character":
        new_character_view()
    elif view["kind"] == "story":
        story_view(story, characters, chapters, fmt)
    else:
        compose_view(story, chapters, characters, fmt)


def _header(eyebrow, title, subtitle=None):
    st.html(f'<div class="sa-eyebrow">{h(eyebrow)}</div><div class="sa-title">{h(title)}</div>'
            + (f'<p class="sa-subtitle">{h(subtitle)}</p>' if subtitle else ""))


def _editor(fmt, label, key, height, **kwargs):
    """A big text area: serif for prose, typewriter font for screenplays."""
    container = "script_editor" if fmt["layout"] == "screenplay" else "manuscript_editor"
    with st.container(key=container):
        return st.text_area(label, key=key, height=height, label_visibility="collapsed", **kwargs)


# ---------- reading and editing ----------

def chapter_view(ch, chapters, fmt, story, characters):
    n = ch["number"]
    position = _position(fmt, ch)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.html(f'<div class="sa-eyebrow">{h(position)}</div>')
        st.space("stretch")
        st.session_state.setdefault(f"mode_{n}", READ)
        mode = st.segmented_control("Mode", [READ, EDIT], key=f"mode_{n}", required=True,
                                    label_visibility="collapsed")
        check = st.button("Cast check", icon=":material/fact_check:", key=f"check_{n}",
                          help="Every character in it reads it and flags anything they wouldn't really do")
        with st.popover("Notes", icon=":material/description:"):
            _chapter_notes(ch)
    if check:
        _run_cast_check(characters, ch["text"], {"context": "chapter", "number": n}, f"Everyone in {position} is in character.")

    chips = "".join(f'<span class="sa-chip">{ui.avatar(name, "sm")}{h(name)}</span>' for name in ch["present"])
    chips += f'<span class="sa-chip plain">{formats.reading_meta(fmt, len(ch["text"].split()))}</span>'
    st.html(f'<div class="sa-title">{h(ui.chapter_title(ch))}</div><div class="sa-meta">{chips}</div>')
    st.button(f"Make this {formats.unit_label(fmt, formats.place_of(fmt, ch)).lower()} a comic",
              icon=":material/view_day:", key=f"to_comic_{n}", on_click=_open_comics, args=(n,),
              help="Open the comic studio with this one already picked")

    if mode == EDIT:
        new_text = _editor(fmt, "Text", f"text_{n}", 620, value=ch["text"])
        with st.container(horizontal=True):
            if st.button("Save changes", type="primary", icon=":material/check:", key=f"save_{n}"):
                ch["text"] = new_text
                storage.save_chapter(ch)
                ui.defer(f"mode_{n}", READ)
                ui.toast(f"{position} saved.")
                st.rerun()
            if st.button("Cancel", key=f"cancel_{n}"):
                ui.defer(f"mode_{n}", READ)
                st.rerun()
        return

    fit = st.session_state.get("fit")
    if fit and fit["context"] == "chapter" and fit["number"] == n:
        _chapter_fit_review(story, characters, ch, fit)

    if fmt["layout"] == "screenplay":
        st.html(f'<article class="sa-script">{ui.screenplay(ch["text"])}</article>')
    else:
        st.html(f'<article class="sa-manuscript">{ui.paragraphs(ch["text"])}</article>')
    st.html('<div class="sa-divider">• • •</div>')

    numbers = [c["number"] for c in chapters]
    unit = "" if formats.is_tv(fmt) else f" {fmt['unit'].lower()}"
    with st.container(horizontal=True):
        if n - 1 in numbers:
            st.button(f"Previous{unit}", icon=":material/arrow_back:", key=f"prev_{n}",
                      on_click=go, args=("chapter",), kwargs={"number": n - 1})
        st.space("stretch")
        if n + 1 in numbers:
            st.button(f"Next{unit}", icon=":material/arrow_forward:", key=f"next_{n}",
                      on_click=go, args=("chapter",), kwargs={"number": n + 1})
        else:
            st.button("Continue the story", icon=":material/edit_note:", type="primary", key=f"continue_{n}",
                      on_click=go, args=("compose",))


def _open_comics(number=None):
    """on_click: open the comic studio, optionally with one chapter already picked."""
    st.session_state.pop("comic_open", None)
    if number is not None:
        st.session_state["comic_from"] = st.session_state["comic_to"] = number
    go("comics")


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


# ---------- writing what comes next ----------

def compose_view(story, chapters, characters, fmt):
    n = storage.next_chapter_number()
    fit = st.session_state.get("fit")
    if fit and fit["context"] == "compose":
        _compose_fit_review(story, characters, fmt, fit)
        return
    draft = st.session_state.get("draft")
    if draft:
        _header(f"{formats.label(fmt, draft['place'], n)} · Review", "Your cast has objections",
                "Nothing is saved yet. For each moment, let the Director rewrite it, pick what the character "
                "would do instead, or keep it and they play it against their will.")
        _objection_review(story, characters, draft, fmt)
        return

    # Where does the next unit go? (continue this volume / move to Act II / start Episode 3 ...)
    options = formats.next_options(fmt, chapters)
    labels = [label for label, _ in options]
    if st.session_state.get("compose_place") not in labels:
        st.session_state["compose_place"] = labels[0]
    place = dict(options)[st.session_state["compose_place"]]
    unit = formats.unit_label(fmt, place)

    _header(formats.label(fmt, place, n), "What happens next?",
            f"Describe it, and your cast will plan it, react in character, and write it with you as a "
            f"{formats.display_name(fmt)}. You can also tell the Director in the chat.")
    if len(options) > 1:
        st.segmented_control("Where it goes", labels, key="compose_place", required=True)
    _guide(fmt, place, chapters)

    st.session_state.setdefault("compose_mode", WITH_AGENTS)
    mode = st.segmented_control("How", [WITH_AGENTS, MYSELF], key="compose_mode", required=True,
                                label_visibility="collapsed")

    if mode == MYSELF:
        screenplay = fmt["layout"] == "screenplay"
        text = _editor(fmt, "Text", "own_text", 560,
                       placeholder=SCRIPT_PLACEHOLDER if screenplay else "Start writing...")
        meta = formats.reading_meta(fmt, len(text.split()))
        st.caption(f"{meta}. When you save, each character remembers only the scenes they were in.")
        st.caption("Before saving, every character in it reads it and flags anything they wouldn't really do.")
        if st.button(f"Save {unit.lower()}", type="primary", icon=":material/check:", disabled=not text.strip()):
            pending = {"context": "compose", "text": text.strip(), "place": place}
            if _run_cast_check(characters, text.strip(), pending, None):
                try:
                    with st.spinner("Everyone is in character. Saving and updating what each character remembers..."):
                        chapter = agents.add_author_chapter(story, characters, text.strip(), place)
                    go("chapter", number=chapter["number"])
                    ui.toast(f"{_position(fmt, chapter)} saved. Everyone stayed in character.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not save it: {e}")
        return

    instruction = st.text_area("Instruction", key="instruction", height=150, label_visibility="collapsed",
                               placeholder=fmt["example"])
    if st.button(f"Generate {unit.lower()}", type="primary", icon=":material/auto_awesome:"):
        if not characters:
            st.warning("Add at least one character first.")
        elif not instruction.strip():
            st.warning("Describe what should happen first.")
        else:
            try:
                with st.status(f"Directing {formats.label(fmt, place, n)}...", expanded=True) as status:
                    st.write("The director is planning and the cast is reacting...")
                    draft = agents.draft_chapter(story, chapters, characters, instruction.strip(), place)
                    if draft["objections"]:
                        st.session_state["draft"] = draft  # wait for the author's decisions
                        status.update(label="Your cast has objections", state="complete")
                    else:
                        st.write("Writing it and updating memories...")
                        _finish(story, characters, draft, fmt)
                st.rerun()
            except Exception as e:
                st.error(f"Could not generate it: {e}")


def _guide(fmt, place, chapters):
    """A small card: where you are in the format's structure, and what usually happens there."""
    steps = formats.progress(fmt, place, chapters)
    strip = ""
    if steps:
        icons = {"done": "check_circle", "now": "radio_button_checked", "todo": "radio_button_unchecked"}
        strip = '<div class="sa-steps">' + "".join(
            f'<span class="sa-step {state}"><span class="sa-icon">{icons[state]}</span>{h(name)}</span>'
            for name, state in steps) + "</div>"
    st.html(f'<div class="sa-guide"><span class="sa-icon">{fmt["icon"]}</span><div>'
            f'<div class="sa-guide-title">{h(fmt["name"])} guide</div>'
            f'<div class="sa-guide-text">{h(formats.hint(fmt, place, chapters))}</div>{strip}</div></div>')


def _finish(story, characters, draft, fmt):
    chapter = agents.finish_chapter(story, characters, draft)
    st.session_state.pop("draft", None)
    go("chapter", number=chapter["number"])
    ui.toast(f"{_position(fmt, chapter)} is ready.")


def _objection_review(story, characters, draft, fmt):
    beats = draft["plan"]["beats"]
    for i, obj in enumerate(draft["objections"]):
        moment = {"character": obj["character"], "quote": beats[obj["beat"] - 1]["text"],
                  "likelihood": obj.get("likelihood"), "why": obj["objection"],
                  "alternatives": obj.get("alternatives", []), "growth": obj.get("growth")}
        decision = _fit_card(f"o{i}", moment, "Keep it as planned", director=True, require=True)
        if decision is None:
            obj["status"] = "pending"
        elif decision[0] == "director":
            obj["status"] = "accepted"
        elif decision[0] == "alt":
            obj["status"], obj["choice"] = "choice", decision[1]
        else:
            obj["status"], obj["remember"] = "overridden", decision[1]

    with st.expander("See the whole plan"):
        for number, beat in enumerate(beats, start=1):
            st.markdown(f"{number}. {beat['text']} *({', '.join(beat['characters'])})*")

    undecided = any(o["status"] == "pending" for o in draft["objections"])
    with st.container(horizontal=True):
        if st.button("Write it", type="primary", icon=":material/auto_awesome:", disabled=undecided):
            try:
                with st.spinner("Writing it and updating memories... (about a minute)"):
                    _finish(story, characters, draft, fmt)
                st.rerun()
            except Exception as e:
                st.error(f"Could not write it: {e}")
        if st.button("Discard", icon=":material/close:"):
            del st.session_state["draft"]
            st.rerun()
    if undecided:
        st.caption("Decide on each objection to continue.")


# ---------- character-fit check ----------

def _band(likelihood):
    if likelihood is None or likelihood < FIT_LOW:
        return "low", "Out of character"
    return ("ok", "In character") if likelihood >= FIT_OK else ("unusual", "Unusual for them")


def _names(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _run_cast_check(characters, text, pending, all_good_message):
    """Every character named in `text` reads it. Returns True if nobody doubts anything.

    Otherwise the doubtful moments are stored in st.session_state["fit"] (with `pending`) and the
    page reruns to show them.
    """
    cast = [c["name"] for c in characters if agents._mentions(text, c["name"])]
    if not cast:
        return True
    try:
        with st.status(f"{_names(cast)} {'is' if len(cast) == 1 else 'are'} reading it...", expanded=False) as status:
            result = agents.check_cast_fit(characters, text)
            doubts = [m for m in result["moments"] if m["likelihood"] < FIT_OK]
            status.update(label="Your cast has notes" if doubts else "Everyone is in character", state="complete")
    except Exception as e:
        st.error(f"The cast check failed: {e}")
        return False
    if not doubts:
        if all_good_message:
            ui.toast(all_good_message)
        return True
    st.session_state["fit"] = dict(pending, checked=result["checked"], moments=doubts)
    st.rerun()


def _fit_card(key, moment, keep_label, director=False, require=False):
    """One moment a character doubts: how likely they'd do it, why, and what they'd do instead.

    Returns the author's decision: ("keep", remember?), ("alt", action), ("director", None),
    or None while undecided.
    """
    name, likelihood = moment["character"], moment["likelihood"]
    band, band_text = _band(likelihood)
    pct = "?" if likelihood is None else f"{likelihood}%"
    with st.container(border=True, key=f"fitcard_{key}"):
        st.html(f'<div class="fit fit-{band}"><div class="fit-head">{ui.avatar(name)}'
                f'<div><div class="sa-chat-name">{h(name)}</div><div class="fit-band">{band_text}</div></div>'
                f'<div class="fit-score"><div class="fit-pct">{pct}</div><div class="fit-label">likely</div></div></div>'
                f'<div class="fit-bar"><span style="width:{max(3, likelihood or 0)}%"></span></div>'
                f'<div class="fit-moment">{ui.rich(moment["quote"])}</div>'
                f'<div class="fit-why"><b>{h(name)}:</b> “{ui.rich(moment["why"])}”</div></div>')
        options = ([("director", None, "Let the Director rewrite it to fit")] if director else [])
        options += [("alt", alt["action"], f"{alt['action']} · {alt['likelihood']}%") for alt in moment["alternatives"]]
        options.append(("keep", None, f"{keep_label} · {pct}"))
        choice = st.radio("What should happen here?", range(len(options)), key=f"fit_{key}",
                          index=None if band == "low" or require else len(options) - 1,
                          format_func=lambda i: options[i][2])
        if choice is None:
            return None
        kind, value, _ = options[choice]
        if kind == "keep":
            return ("keep", st.checkbox(f"This is {name} changing. Remember it.", key=f"grow_{key}",
                                        help="Saved to their profile, so from now on it counts as in character."))
        return (kind, value)


def _apply_fit(story, characters, text, moments, decisions):
    """Rewrite the moments where the author picked an alternative, and remember kept changes."""
    by_name = {c["name"]: c for c in characters}
    for moment, decision in zip(moments, decisions):
        if decision and decision[0] == "alt":
            text = agents.rewrite_moment(story, text, moment["quote"], moment["character"], decision[1])
    return text, [(by_name[m["character"]], m) for m, d in zip(moments, decisions)
                  if d and d[0] == "keep" and d[1] and m["character"] in by_name]


def _fit_buttons(save_label, decisions, back_label):
    undecided = any(d is None for d in decisions)
    with st.container(horizontal=True):
        save = st.button(save_label, type="primary", icon=":material/check:", disabled=undecided, key="fit_save")
        back = st.button(back_label, key="fit_back")
    if undecided:
        st.caption("Choose what happens at each moment marked out of character.")
    return save, back


def _compose_fit_review(story, characters, fmt, fit):
    n = storage.next_chapter_number()
    moments = fit["moments"]
    low = sum(1 for m in moments if _band(m["likelihood"])[0] == "low")
    _header(f"{formats.label(fmt, fit['place'], n)} · Cast review", "Your cast read it",
            f"{_names(fit['checked'])} read your draft: {low} out of character, {len(moments) - low} unusual. "
            "Choose what happens at each moment. Nothing is saved yet.")
    decisions = [_fit_card(f"c{i}", m, "Keep it as written") for i, m in enumerate(moments)]
    save, back = _fit_buttons(f"Save {formats.unit_label(fmt, fit['place']).lower()}", decisions, "Back to editing")
    if back:
        ui.defer("own_text", fit["text"])
        ui.defer("compose_mode", MYSELF)
        st.session_state.pop("fit")
        st.rerun()
    if save:
        try:
            with st.spinner("Rewriting the moments you changed, then saving..."):
                text, kept = _apply_fit(story, characters, fit["text"], moments, decisions)
                chapter = agents.add_author_chapter(story, characters, text, fit["place"])
                for character, moment in kept:
                    agents.remember_growth(character, chapter["number"], moment["growth"], moment["quote"])
            st.session_state.pop("fit")
            go("chapter", number=chapter["number"])
            ui.toast(f"{_position(fmt, chapter)} saved.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not save it: {e}")


def _chapter_fit_review(story, characters, ch, fit):
    moments = fit["moments"]
    with st.container(key="chapter_fit"):
        st.html(f'<div class="sa-guide"><span class="sa-icon">fact_check</span><div>'
                f'<div class="sa-guide-title">Cast check</div><div class="sa-guide-text">{h(_names(fit["checked"]))} '
                f'read this. {len(moments)} {"moment needs" if len(moments) == 1 else "moments need"} a look.'
                '</div></div></div>')
        decisions = [_fit_card(f"ch{ch['number']}_{i}", m, "Keep it as written") for i, m in enumerate(moments)]
        save, back = _fit_buttons("Apply changes", decisions, "Dismiss")
    if back:
        st.session_state.pop("fit")
        st.rerun()
    if save:
        try:
            with st.spinner("Rewriting the moments you changed..."):
                ch["text"], kept = _apply_fit(story, characters, ch["text"], moments, decisions)
                storage.save_chapter(ch)
                for character, moment in kept:
                    agents.remember_growth(character, ch["number"], moment["growth"], moment["quote"])
            st.session_state.pop("fit")
            ui.toast("Changes applied.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not apply the changes: {e}")


# ---------- characters ----------

def character_view(char, chapters, fmt):
    name = char["name"]
    seen = ui.last_seen_label(fmt, name, chapters)
    chips = f'<span class="sa-chip plain">{h("Last seen in " + seen) if seen else "Not in the story yet"}</span>'
    if ui.is_forgotten(name, chapters, fmt):
        chips += (f'<span class="sa-chip warn">Forgotten · absent {fmt["forgotten_after"]}+ '
                  f'{fmt["forgotten_unit"]}</span>')
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
        _memories(char, chapters, fmt)


def _card_fields(prefix, card=None):
    """Two columns of card fields. Returns {field: value}."""
    left, right = st.columns(2)
    values = {}
    for i, field in enumerate(storage.CARD_FIELDS):
        column = left if i % 2 == 0 else right
        kwargs = {"value": card[field]} if card is not None else {}
        values[field] = column.text_area(field.capitalize(), height=140, key=f"{prefix}_{field}", **kwargs)
    return values


def _memories(char, chapters, fmt):
    by_number = {c["number"]: c for c in chapters}
    events = {}
    for m in char["memories"]:
        events.setdefault(m["chapter"], {})["memory"] = m["text"]
    for u in char["profile_updates"]:
        events.setdefault(u["chapter"], {})["change"] = u["text"]
    if not events:
        st.html(f'<div class="sa-empty">{h(char["name"])} hasn\'t lived through any of the story yet. '
                'They only remember scenes they are in.</div>')
        return
    items = ""
    for number in sorted(events):
        e = events[number]
        where = _position(fmt, by_number[number]) if number in by_number else f"{fmt['unit']} {number}"
        items += f'<div class="sa-event"><div class="sa-event-label">{h(where)}</div>'
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

def story_view(story, characters, chapters, fmt):
    _header(f"Story · {fmt['name']}", story["title"] or "Untitled story")
    words = sum(len(ch["text"].split()) for ch in chapters)
    places = [formats.place_of(fmt, c) for c in chapters]
    with st.container(horizontal=True):
        st.metric(fmt["units"].capitalize(), len(chapters), border=True)
        st.metric("Characters", len(characters), border=True)
        if fmt["layout"] == "screenplay":
            st.metric("Pages", f"≈ {formats.pages(words)}", border=True)
        else:
            st.metric("Words", f"{words:,}", border=True)
    st.caption(formats.summary(fmt, places, words) if chapters else fmt["structure"])

    with st.form("story_form", border=False):
        title = st.text_input("Title", value=story["title"])
        outline = st.text_area("Outline", value=story["outline"], height=260,
                               help="The big picture. The director reads this before planning anything.")
        format_ids = list(formats.FORMATS)
        format_id = st.selectbox(
            "Format", format_ids, index=format_ids.index(fmt["id"]),
            format_func=lambda f: formats.FORMATS[f]["name"], disabled=bool(chapters),
            help="Can only be changed before anything is written." if chapters else None)
        if st.form_submit_button("Save", type="primary", icon=":material/check:"):
            storage.save_story({"title": title, "outline": outline, "format": format_id})
            ui.toast("Story saved.")
            st.rerun()
