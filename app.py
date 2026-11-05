"""NovelTroupe - run with: streamlit run app.py

Pages (the current page is kept in the URL, e.g. ?page=studio&story=s_...):
  landing   the public front page              landing.landing_page
  login     sign in / create account           landing.auth_page
  library   your stories                       library.library_page
  new       start a story: pick its format     library.new_story_page
  studio    write one story (three panels)     studio.studio_page
"""

import streamlit as st

import landing
import library
import storage
import studio
import ui

st.set_page_config(page_title=f"{ui.APP_NAME} · {ui.TAGLINE}", page_icon=":material/auto_stories:",
                   layout="wide", initial_sidebar_state="collapsed")
ui.load_css()
ui.run_browser_actions()
ui.apply_pending()

user = ui.current_user()
page = ui.page()

if user is None:
    if page in ("login", "signup"):
        landing.auth_page(page)
    else:
        landing.landing_page(None)
elif page == "studio" and (story_dir := storage.find_story(user["id"], st.query_params.get("story"))):
    studio.studio_page(story_dir, st.query_params["story"])
elif page == "new":
    library.new_story_page(user)
elif page == "":
    landing.landing_page(user)
else:
    library.library_page(user)

ui.show_toast()
