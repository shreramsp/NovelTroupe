"""The library (every story the author has) and the "New story" page where they pick a format."""

import html

import streamlit as st

import formats
import storage
import ui
from ui import APP_NAME, nav

COLUMNS = 3
PAGE_CSS = """
.stApp { background:
    radial-gradient(900px 420px at 0% -10%, var(--sa-glow-1), transparent 60%),
    radial-gradient(700px 380px at 100% 0%, var(--sa-glow-2), transparent 55%),
    var(--sa-bg) !important; }
[data-testid="stMainBlockContainer"] { max-width: 1180px !important; margin: 0 auto; padding-top: 18px !important; }
"""


def top_nav(user):
    with st.container(key="topnav", horizontal=True, vertical_alignment="center"):
        st.button(APP_NAME, key="nav_home", type="tertiary", on_click=nav, args=("library",))
        st.space("stretch")
        st.button("How it works", key="nav_about", type="tertiary", on_click=nav)
        ui.theme_button("theme_library")
        ui.account_menu(user, "account_library")


# =====================================================================
# Library
# =====================================================================

def _open(story_id):
    nav("studio", story=story_id)


def _delete(user_id, story_id):
    storage.delete_story(user_id, story_id)
    ui.toast("Story deleted.")


def library_page(user):
    ui.css(PAGE_CSS)
    top_nav(user)
    stories = storage.list_stories(user["id"])

    with st.container(key="library_head", horizontal=True, vertical_alignment="bottom"):
        st.html(f'<div><div class="sa-eyebrow">Your library</div>'
                f'<h1 class="lib-title">Welcome back, {html.escape(user["name"].split()[0])}.</h1>'
                f'<p class="lib-sub">{len(stories)} {"story" if len(stories) == 1 else "stories"}. '
                'Pick up where you left off, or begin something new.</p></div>')
        st.space("stretch")
        st.button("New story", type="primary", icon=":material/add:", key="new_story", on_click=nav, args=("new",))

    if not stories:
        with st.container(key="library_empty"):
            st.html('<div class="lib-empty"><span class="sa-icon lg">auto_stories</span>'
                    '<h2>Your first story starts here</h2>'
                    '<p>Pick a format (novel, light novel, film or TV series), add a few characters, '
                    'and talk to them before you write a word.</p></div>')
            with st.container(horizontal=True, horizontal_alignment="center"):
                st.button("Start your first story", type="primary", icon=":material/add:", key="first_story",
                          on_click=nav, args=("new",))
        return

    for row_start in range(0, len(stories), COLUMNS):
        columns = st.columns(COLUMNS, gap="medium")
        for column, story in zip(columns, stories[row_start:row_start + COLUMNS]):
            with column:
                _story_card(user, story)


def _story_card(user, story):
    fmt = formats.get(story["format"])
    start, end = ui.cover_for(story["id"])
    title = html.escape(story["title"])
    blurb = html.escape(story["outline"][:220]) or "<i>No premise yet.</i>"
    places = [p or formats.first_place(fmt) for p in story["places"]]
    stats = (f'{formats.summary(fmt, places, story["words"]) if places else "Not started"}'
             f' · {story["characters"]} characters')
    with st.container(key=f"story_{story['id']}"):
        st.html(f'<div class="lib-cover" style="background:linear-gradient(135deg,{start},{end})">'
                f'<span class="lib-format"><span class="sa-icon">{fmt["icon"]}</span>{fmt["name"]}</span>'
                f'<span class="lib-cover-title">{title}</span></div>'
                f'<div class="lib-card-body"><h3>{title}</h3><p class="lib-blurb">{blurb}</p>'
                f'<div class="lib-stats">{html.escape(stats)}</div>'
                f'<div class="lib-updated">Edited {ui.time_ago(story["updated"])}</div></div>')
        with st.container(horizontal=True, vertical_alignment="center", key=f"actions_{story['id']}"):
            st.button("Open", type="primary", icon=":material/edit_note:", key=f"open_{story['id']}",
                      on_click=_open, args=(story["id"],))
            st.button("Comic", icon=":material/view_day:", key=f"comic_{story['id']}", on_click=nav,
                      args=("studio",), kwargs={"story": story["id"], "view": "comics"},
                      help="Open this story's comic studio")
            st.space("stretch")
            with st.popover("", icon=":material/more_horiz:", key=f"more_{story['id']}"):
                st.caption("Delete this story and everything in it? This can't be undone.")
                st.button("Delete story", icon=":material/delete:", key=f"delete_{story['id']}",
                          on_click=_delete, args=(user["id"], story["id"]))


# =====================================================================
# New story: 1. pick a format  2. name it
# =====================================================================

def _pick(choice):
    st.session_state["new_choice"] = choice


def new_story_page(user):
    ui.css(PAGE_CSS)
    top_nav(user)
    st.session_state.setdefault("new_choice", "novel")
    choice = st.session_state["new_choice"]

    st.html('<div class="ns-head"><div class="sa-eyebrow">New story</div>'
            '<h1 class="lib-title">What are you writing?</h1>'
            '<p class="lib-sub">Pick a format. NovelTroupe shapes the structure, the Director\'s planning and the '
            'page layout around it.</p></div>'
            '<div class="ns-step"><span>1</span>Choose a format</div>')

    # Four cards; the whole card is clickable (an invisible button covers it, see style.css).
    for column, (choice_id, card) in zip(st.columns(4, gap="medium"), formats.CHOICES.items()):
        with column, st.container(key=f"fmt_{choice_id}"):
            st.html(f'<div class="ns-card"><span class="ns-check sa-icon">check_circle</span>'
                    f'<span class="ns-icon sa-icon">{card["icon"]}</span>'
                    f'<h3>{card["name"]}</h3><p>{card["tagline"]}</p>'
                    f'<div class="ns-shape">{html.escape(card["shape"])}</div></div>')
            st.button(f"Choose {card['name']}", key=f"pick_{choice_id}", on_click=_pick, args=(choice_id,))
    ui.css(f".st-key-fmt_{choice} {{ border-color: var(--sa-accent) !important; "
           f"box-shadow: 0 0 0 3px var(--sa-accent-tint), var(--sa-shadow) !important; }} "
           f".st-key-fmt_{choice} .ns-check {{ opacity: 1; }}")

    format_id = choice
    if choice == "tv":
        st.session_state.setdefault("new_tv_kind", "tv_sitcom")
        format_id = st.segmented_control("Kind of show", list(formats.TV_KINDS), key="new_tv_kind", required=True,
                                         format_func=formats.TV_KINDS.get)
    _preview(format_id)

    st.html('<div class="ns-step"><span>2</span>Name your story</div>')
    with st.container(key="ns_details"):
        title = st.text_input("Title", placeholder="The Last Muster", key="new_title")
        outline = st.text_area("Premise", height=150, key="new_outline",
                               placeholder="Twenty years after the ambush at Ridge 614, a veteran raising two "
                                           "children is asked by a journalist about the night his unit died...",
                               help="A few sentences about the world and the conflict. The Director reads this "
                                    "before planning anything. You can change it later.")
        with st.container(horizontal=True, vertical_alignment="center"):
            create = st.button(f"Create {formats.display_name(formats.FORMATS[format_id])}", type="primary",
                               icon=":material/arrow_forward:", key="create_story")
            st.button("Cancel", key="cancel_new", type="tertiary", on_click=nav, args=("library",))
        if create:
            if not title.strip():
                st.error("Please give your story a title.")
            else:
                story_id = storage.create_story(user["id"], title.strip(), outline.strip(), format_id)
                for key in ("new_choice", "new_tv_kind", "new_title", "new_outline"):
                    st.session_state.pop(key, None)
                nav("studio", story=story_id)
                st.rerun()


def _preview(format_id):
    """How the chosen format is organised, a few facts, and what a page of it looks like."""
    fmt, preview = formats.FORMATS[format_id], formats.PREVIEWS[format_id]
    tree = "".join(
        f'<div class="ns-tree-group">{html.escape(group)}</div>'
        + "".join(f'<div class="ns-tree-item">{html.escape(item)}</div>' for item in items)
        for group, items in preview["tree"])
    facts = "".join(f'<span class="sa-chip plain">{html.escape(f)}</span>' for f in preview["facts"])
    if fmt["layout"] == "screenplay":
        sample = f'<div class="sa-script ns-sample-script">{ui.screenplay(preview["sample"])}</div>'
    else:
        sample = f'<div class="sa-manuscript ns-sample-prose">{ui.paragraphs(preview["sample"])}</div>'
    st.html(f'<div class="ns-preview">'
            f'<div class="ns-preview-col"><div class="ns-label">How it\'s organised</div>'
            f'<div class="ns-tree">{tree}</div><div class="sa-meta" style="margin-top:14px">{facts}</div>'
            f'<p class="ns-structure">{html.escape(fmt["structure"])}</p></div>'
            f'<div class="ns-preview-col"><div class="ns-label">How a page looks</div>'
            f'<div class="ns-page">{sample}</div></div></div>')
