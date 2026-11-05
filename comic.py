"""Comic: turn chapters into episodes of a vertical-scroll comic (a webtoon / manhwa), read top to bottom.

How it stays consistent:
1. Every character gets a written "look" and a reference sheet (full body + close-up), drawn once
   per art style. The author can redraw a sheet or change the look until it is right.
2. The Director storyboards the chosen chapter(s): shot, scene, narration and speech bubbles.
3. Every panel is drawn FROM the sheets of the characters in it (agents.draw_panel), in one fixed
   manhwa style, with the speech bubbles lettered into the picture like a real webtoon.
4. The reader shows the episode as one long borderless strip.
"""

import html
import secrets
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st

import agents
import formats
import storage
import ui

STYLES = {"webtoon": "Manhwa · color", "manga": "Manga · black & white", "graphic": "Graphic novel"}
CHAPTERS_PER_EPISODE = {"light_novel": 1, "novel": 1, "film": 2, "tv_sitcom": 4, "tv_drama": 6}
DRAW_AT_ONCE = 4          # pictures drawn in parallel
SECONDS_PER_BATCH = 45    # one batch of DRAW_AT_ONCE pictures, measured with the real model


def h(text):
    return html.escape(text or "")


def comic_view(story, chapters, characters, fmt):
    comics = storage.load_comics()
    # Clicks only leave a note; the files are changed here, once the current story is loaded.
    if deleting := st.session_state.pop("cm_delete_pending", None):
        storage.delete_comic_images(deleting)
        comics["episodes"] = [e for e in comics["episodes"] if e["id"] != deleting]
        storage.save_comics(comics)
        ui.toast("Episode deleted.")
    episode = next((e for e in comics["episodes"] if e["id"] == st.session_state.get("comic_open")), None)
    if episode:
        _reader(story, chapters, fmt, comics, episode)
        return

    st.html('<div class="sa-eyebrow">Comic</div><div class="sa-title">Your story as a webtoon</div>'
            '<p class="sa-subtitle">Turn a chapter into an episode of a vertical-scroll comic, read top to bottom. '
            'Every character is drawn from their own reference sheet, so they look the same in every panel.</p>')
    if not chapters:
        st.html('<div class="kw-empty"><span class="sa-icon lg">view_day</span><h3>Write a chapter first</h3>'
                '<p>Comic episodes are adapted from chapters you have already written.</p></div>')
        return
    _new_episode(story, chapters, characters, fmt, comics)
    _episode_list(comics, fmt, chapters)
    _cast_sheets(story, characters, comics)


def _short(fmt, chapters_by_number, number):
    chapter = chapters_by_number[number]
    place = formats.place_of(fmt, chapter)
    if formats.is_tv(fmt):
        return f"S{place['season']} E{place['episode']} · {formats.unit_label(fmt, place)}"
    return formats.short_label(fmt, place, number)


def _style():
    return st.session_state.get("comic_style") or "webtoon"


# =====================================================================
# Character sheets: the source of consistency
# =====================================================================

def _ensure_sheets(story, comics, characters, style, on_progress=None):
    """Make sure every character in `characters` has a look and a sheet in `style`. Draws missing ones in parallel."""
    missing_looks = [c for c in characters if c["name"] not in comics["looks"]]
    if missing_looks:
        comics["looks"].update(agents.describe_looks(story, missing_looks))
        storage.save_comics(comics)
    todo = [c["name"] for c in characters
            if c["name"] in comics["looks"] and storage.load_comic_sheet(c["name"], style) is None]
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=DRAW_AT_ONCE) as pool:
        futures = {pool.submit(agents.draw_sheet, name, comics["looks"][name], style): name for name in todo}
        for done, future in enumerate(as_completed(futures), start=1):
            try:
                storage.save_comic_sheet(futures[future], style, future.result())
            except Exception:
                pass  # this character is drawn from the written look only; the sheet can be redrawn
            if on_progress:
                on_progress(done, len(todo))


def _cast_sheets(story, characters, comics):
    style = _style()
    st.html(f'<div class="cm-section">Character sheets · {h(STYLES[style])}</div>')
    with_sheet = [c for c in characters if storage.comic_sheet_path(c["name"], style)]
    if len(with_sheet) < len(characters):
        st.caption("Each character is drawn once on a reference sheet, and every panel is drawn from it. "
                   "Sheets are made automatically with your first episode, or right now:")
        if st.button("Draw the character sheets", icon=":material/person_book:", key="cm_draw_sheets"):
            with st.spinner("Designing the cast and drawing their sheets..."):
                _ensure_sheets(story, comics, characters, style)
            st.rerun()
    for row in range(0, len(with_sheet), 3):
        for column, character in zip(st.columns(3, gap="medium"), with_sheet[row:row + 3]):
            name = character["name"]
            with column, st.container(key=f"cm_sheet_{storage.safe_name(name).replace(' ', '_')}"):
                st.image(str(storage.comic_sheet_path(name, style)), width="stretch")
                st.html(f'<div class="cm-sheet-name">{h(name)}</div>')
                if st.button("Redraw", icon=":material/refresh:", type="tertiary", key=f"cm_resheet_{name}",
                             help="Draw this character's sheet again"):
                    with st.spinner(f"Redrawing {name}..."):
                        storage.save_comic_sheet(name, style, agents.draw_sheet(name, comics["looks"][name], style))
                    st.rerun()
    _looks(comics, characters)


def _looks(comics, characters):
    names = [c["name"] for c in characters if c["name"] in comics["looks"]]
    if not names:
        return
    with st.expander("Change how a character looks"):
        st.caption("Saving a change redraws that character's sheets the next time they are needed.")
        with st.form("cm_looks", border=False):
            looks = {name: st.text_area(name, value=comics["looks"][name], height=80, key=f"cm_look_{name}")
                     for name in names}
            if st.form_submit_button("Save looks", icon=":material/check:"):
                for name, look in looks.items():
                    if look.strip() and look.strip() != comics["looks"][name]:
                        comics["looks"][name] = look.strip()
                        storage.delete_comic_sheets(name)
                storage.save_comics(comics)
                ui.toast("Looks saved.")
                st.rerun()


# =====================================================================
# Making an episode
# =====================================================================

def _new_episode(story, chapters, characters, fmt, comics):
    by_number = {c["number"]: c for c in chapters}
    numbers = list(by_number)
    adapted = max((n for e in comics["episodes"] for n in e["chapters"]), default=0)
    start = next((n for n in numbers if n > adapted), numbers[0])
    end = numbers[min(numbers.index(start) + CHAPTERS_PER_EPISODE.get(fmt["id"], 1) - 1, len(numbers) - 1)]
    for key, default in (("comic_from", start), ("comic_to", end)):
        if st.session_state.get(key) not in numbers:
            st.session_state[key] = default  # first visit, or the chapters changed

    with st.container(border=True, key="comic_new"):
        st.html(f'<div class="sa-guide-title" style="font-size:13px">NEW EPISODE {len(comics["episodes"]) + 1}</div>')
        first_col, last_col = st.columns(2, gap="medium")
        label = lambda n: f"{_short(fmt, by_number, n)} · {by_number[n].get('title', '')}"
        low = first_col.selectbox("From", numbers, key="comic_from", format_func=label)
        to_options = [n for n in numbers if n >= low]
        if st.session_state.get("comic_to") not in to_options:
            st.session_state["comic_to"] = low
        high = last_col.selectbox("To", to_options, key="comic_to", format_func=label)
        style = st.segmented_control("Art style", list(STYLES), key="comic_style", default="webtoon",
                                     format_func=STYLES.get, required=True, width="stretch")
        panels = st.slider("Panels", 6, 30, 15, key="comic_panels",
                           help="One chapter usually needs 12-20 panels. A weekly webtoon episode is often 30-60.")
        lettering = st.toggle("Letter the speech bubbles into the pictures", value=True, key="comic_lettering",
                              help="Like a real webtoon. Turn off to show the dialogue under each picture instead.")
        minutes = max(1, round((-(-panels // DRAW_AT_ONCE) * SECONDS_PER_BATCH + 40) / 60))
        st.caption(f"About {minutes} minutes for {panels} panels (plus a minute the first time, to draw the "
                   f"character sheets). About 1 cent per picture.")
        if st.button("Create episode", type="primary", icon=":material/brush:", key="comic_create"):
            selected = [c for c in chapters if low <= c["number"] <= high]
            _create(story, selected, characters, comics, panels, style, lettering)


def _create(story, selected, characters, comics, panels, style, lettering):
    present = {name for c in selected for name in c["present"]}
    cast = [c for c in characters if c["name"] in present] or characters
    try:
        with st.status("Making your episode...", expanded=True) as status:
            st.write("The Director is storyboarding the panels...")
            plan = agents.plan_comic(story, selected, cast, comics["looks"], panels)
            for name, look in plan["looks"].items():
                comics["looks"].setdefault(name, look)
            in_panels = {name for p in plan["panels"] for name in p["characters"]}
            st.write("Making sure every character has a reference sheet...")
            sheet_bar = st.progress(0.0)
            _ensure_sheets(story, comics, [c for c in characters if c["name"] in in_panels], style,
                           lambda done, total: sheet_bar.progress(done / total, text=f"{done} of {total} sheets drawn"))
            episode = {"id": "e" + secrets.token_hex(4), "title": plan["title"], "style": style, "lettering": lettering,
                       "chapters": [c["number"] for c in selected], "created": time.time(),
                       "panels": [dict(p, image=None) for p in plan["panels"]]}
            comics["episodes"].append(episode)
            storage.save_comics(comics)  # saved now, so leaving the page never loses drawn panels
            st.write(f"Drawing {len(episode['panels'])} panels from the sheets, {DRAW_AT_ONCE} at a time...")
            bar = st.progress(0.0, text="Starting...")
            _draw(comics, episode, range(len(episode["panels"])),
                  lambda done, total: bar.progress(done / total, text=f"{done} of {total} panels drawn"))
            missing = sum(1 for p in episode["panels"] if not p["image"])
            status.update(label="Episode ready" + (f" ({missing} panels to redraw)" if missing else ""),
                          state="complete")
        st.session_state["comic_open"] = episode["id"]
        for key in ("comic_from", "comic_to"):  # the next episode starts after this one
            st.session_state.pop(key, None)
        st.rerun()
    except Exception as e:
        st.error(f"Could not make the episode: {e}")


def _draw(comics, episode, indices, on_progress=None):
    """Draw panels side by side from the character sheets, saving each one as it arrives."""
    indices = list(indices)
    style, lettering = episode["style"], episode.get("lettering", False)
    names = {name for i in indices for name in episode["panels"][i]["characters"]}
    sheets = {name: sheet for name in names if (sheet := storage.load_comic_sheet(name, style))}
    with ThreadPoolExecutor(max_workers=DRAW_AT_ONCE) as pool:
        futures = {pool.submit(agents.draw_panel, episode["panels"][i], comics["looks"], style, sheets, lettering): i
                   for i in indices}
        for done, future in enumerate(as_completed(futures), start=1):
            i = futures[future]
            try:
                episode["panels"][i]["image"] = storage.save_comic_image(episode["id"], i + 1, future.result())
                storage.save_comics(comics)
            except Exception:
                pass  # stays empty; the reader offers to draw it again
            if on_progress:
                on_progress(done, len(indices))


# =====================================================================
# The list of episodes
# =====================================================================

def _open(episode_id):
    st.session_state["comic_open"] = episode_id


def _span_label(fmt, by_number, chapter_numbers):
    span = [n for n in chapter_numbers if n in by_number]
    if not span:
        return ""
    if len(span) == 1:
        return _short(fmt, by_number, span[0])
    return f"{_short(fmt, by_number, span[0])} – {_short(fmt, by_number, span[-1])}"


def _episode_list(comics, fmt, chapters):
    if not comics["episodes"]:
        return
    by_number = {c["number"]: c for c in chapters}
    st.html('<div class="cm-section">Episodes</div>')
    for row in range(0, len(comics["episodes"]), 3):
        for column, (number, episode) in zip(st.columns(3, gap="medium"),
                                             list(enumerate(comics["episodes"], start=1))[row:row + 3]):
            with column, st.container(key=f"cm_card_{episode['id']}"):
                cover = next((p["image"] for p in episode["panels"] if p["image"]), None)
                path = storage.comic_image_path(episode["id"], cover) if cover else None
                if path and path.exists():
                    st.image(str(path), width="stretch")
                st.html(f'<div class="cm-card-body"><div class="cm-card-eyebrow">Episode {number}</div>'
                        f'<div class="cm-card-title">{h(episode["title"])}</div>'
                        f'<div class="cm-card-meta">{h(_span_label(fmt, by_number, episode["chapters"]))} · '
                        f'{len(episode["panels"])} panels · {h(STYLES.get(episode["style"], ""))}</div></div>')
                st.button("Read", icon=":material/menu_book:", key=f"cm_read_{episode['id']}", width="stretch",
                          on_click=_open, args=(episode["id"],))


# =====================================================================
# The reader: one long borderless strip
# =====================================================================

def _close():
    st.session_state.pop("comic_open", None)


def _delete(episode_id):
    """on_click: comic_view() deletes it on the next run."""
    st.session_state["cm_delete_pending"] = episode_id
    st.session_state.pop("comic_open", None)


def _reader(story, chapters, fmt, comics, episode):
    by_number = {c["number"]: c for c in chapters}
    number = next(i for i, e in enumerate(comics["episodes"], start=1) if e["id"] == episode["id"])
    with st.container(horizontal=True, vertical_alignment="center"):
        st.button("All episodes", icon=":material/arrow_back:", type="tertiary", key="cm_back", on_click=_close)
        st.space("stretch")
        with st.popover("", icon=":material/more_horiz:", key="cm_more"):
            st.caption("Delete this episode and its pictures?")
            st.button("Delete episode", icon=":material/delete:", key="cm_delete", on_click=_delete,
                      args=(episode["id"],))

    missing = [i for i, p in enumerate(episode["panels"]) if not p.get("image")]
    if missing:
        with st.container(key="cm_missing_bar"):
            st.html(f'<div class="sa-guide"><span class="sa-icon">brush</span><div><div class="sa-guide-title">'
                    f'{len(missing)} panel{"s" if len(missing) > 1 else ""} still to draw</div><div class="sa-guide-text">'
                    'Drawing stopped before the episode was finished.</div></div></div>')
            if st.button("Draw the missing panels", type="primary", icon=":material/brush:", key="cm_draw_missing"):
                bar = st.progress(0.0, text="Drawing...")
                _draw(comics, episode, missing,
                      lambda done, total: bar.progress(done / total, text=f"{done} of {total} panels drawn"))
                st.rerun()

    lettered = episode.get("lettering", False)
    with st.container(key="comic_strip"):
        st.html(f'<div class="cm-title-card"><div class="cm-card-eyebrow">Episode {number} · '
                f'{h(_span_label(fmt, by_number, episode["chapters"]))}</div>'
                f'<div class="cm-episode-title">{h(episode["title"])}</div>'
                f'<div class="cm-card-meta">{h(story["title"])} · {h(STYLES.get(episode["style"], ""))}</div></div>')
        for i, panel in enumerate(episode["panels"]):
            if panel.get("caption"):
                st.html(f'<div class="cm-caption">{h(panel["caption"])}</div>')
            path = storage.comic_image_path(episode["id"], panel["image"]) if panel.get("image") else None
            if path and path.exists():
                st.image(str(path), width="stretch")
            else:
                st.html('<div class="cm-missing"><span class="sa-icon">broken_image</span>'
                        'This panel could not be drawn. Redraw it below.</div>')
            if panel.get("dialogue") and not lettered:
                bubbles = "".join(
                    f'<div class="cm-bubble {"right" if j % 2 else "left"}"><span class="cm-speaker">'
                    f'{h(line["speaker"])}</span>{h(line["text"])}</div>' for j, line in enumerate(panel["dialogue"]))
                st.html(f'<div class="cm-bubbles">{bubbles}</div>')
            if st.button("Redraw", icon=":material/refresh:", type="tertiary", key=f"cm_redraw_{episode['id']}_{i}",
                         help="Draw this panel again (same scene, a new picture)"):
                with st.spinner("Redrawing..."):
                    _draw(comics, episode, [i])
                st.rerun()
        st.html('<div class="cm-end">To be continued…</div>')
