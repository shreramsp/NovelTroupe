"""NovelSpark - Streamlit UI. Run with: streamlit run app.py

Three panels:
  left    chapters (top) and characters (bottom)          views.left_panel
  center  the manuscript: read, write, generate, profiles  views.center_panel
  right   one conversation: the Director or any character  chat.chat_panel
"""

import streamlit as st

import chat
import storage
import ui
import views

APP_NAME = "NovelSpark"

st.set_page_config(page_title=APP_NAME, page_icon=":material/auto_stories:", layout="wide",
                   initial_sidebar_state="collapsed")
ui.load_css()
ui.apply_pending()

story = storage.load_story()
characters = storage.load_all_characters()
chapters = storage.load_all_chapters()

if "view" not in st.session_state:  # open the latest chapter, or the composer for a new story
    st.session_state["view"] = {"kind": "chapter", "number": chapters[-1]["number"]} if chapters else {"kind": "compose"}

left, center, right = st.columns([1, 2.5, 1.45], gap="small")
with left, st.container(key="panel_left"):
    views.left_panel(APP_NAME, story, chapters, characters)
with center, st.container(key="panel_center"):
    views.center_panel(story, chapters, characters)
with right, st.container(key="panel_right"):
    slot, message = chat.chat_panel(chapters, characters)

if message:
    chat.handle(message, slot, story, chapters, characters)
ui.show_toast()
