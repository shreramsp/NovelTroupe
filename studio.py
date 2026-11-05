"""The writing studio for one story: three panels.

  left    chapters (top) and characters (bottom)          views.left_panel
  center  the manuscript: read, write, generate, profiles  views.center_panel
  right   Chat (the Director or any character) and the Cast room   chat.right_panel
"""

import streamlit as st

import castroom
import chat
import formats
import storage
import ui
import views


def studio_page(story_dir, story_id):
    ui.enter_story(story_id)
    storage.use_story(story_dir)
    if st.query_params.get("view") == "comics":  # e.g. the Comic button on a library card
        st.session_state["view"] = {"kind": "comics"}
        del st.query_params["view"]
    ui.css(".stApp { background: var(--sa-bg) !important; }")

    story = storage.load_story()
    characters = storage.load_all_characters()
    chapters = storage.load_all_chapters()

    if "view" not in st.session_state:  # open the latest chapter, or the composer for a new story
        st.session_state["view"] = ({"kind": "chapter", "number": chapters[-1]["number"]} if chapters
                                    else {"kind": "compose"})

    left, center, right = st.columns([1, 2.5, 1.45], gap="small")
    with left, st.container(key="panel_left"):
        views.left_panel(story, chapters, characters)
    with center, st.container(key="panel_center"):
        views.center_panel(story, chapters, characters)
    with right, st.container(key="panel_right"):
        slot, message, kind = chat.right_panel(story, formats.get(story["format"]), chapters, characters)

    if message:
        handler = castroom.handle if kind == "room" else chat.handle
        handler(message, slot, story, chapters, characters)
