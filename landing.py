"""The public front page and the sign-in / create-account page."""

import streamlit as st

import accounts
import storage
import ui
from ui import APP_NAME, nav

SIGN_IN, SIGN_UP = "Sign in", "Create account"


def _top_nav(user):
    with st.container(key="topnav", horizontal=True, vertical_alignment="center"):
        st.button(APP_NAME, key="nav_home", type="tertiary", on_click=nav)
        st.space("stretch")
        st.html('<nav class="lp-links"><a href="#how">How it works</a><a href="#features">Features</a></nav>')
        ui.theme_button("theme_landing")
        if user:
            st.button("Open your library", key="nav_library", type="primary", icon=":material/library_books:",
                      on_click=nav, args=("library",))
        else:
            st.button("Sign in", key="nav_signin", type="tertiary", on_click=nav, args=("login",))
            st.button("Start writing", key="nav_start", type="primary", on_click=nav, args=("signup",))


HERO_TEXT = """
<div class="lp-pill"><span class="lp-dot"></span>Built on Meta Muse Spark &amp; Muse Image</div>
<h1 class="lp-h1">Write with characters<br>who <em>remember.</em></h1>
<p class="lp-lead">NovelTroupe turns every character in your novel into an AI agent. They remember only
what they lived through, answer you in their own voice, and push back when your plot asks them to
betray who they are.</p>
"""

HERO_MOCK = """
<div class="lp-mock">
  <div class="lp-mock-bar"><i></i><i></i><i></i><span>The Last Muster</span></div>
  <div class="lp-mock-body">
    <div class="lp-mock-page">
      <div class="lp-mock-eyebrow">Chapter 2</div>
      <div class="lp-mock-title">Fractions and Silence</div>
      <p><b>T</b>he oil popped in the pan and Park moved it off the heat with a practiced wrist.
      The kitchen was small and warm and too full. On the table, Hana had spread her math out in a
      fan of paper, pencil, and eraser shavings.</p>
      <p>"Homework stays on the placemat, Miss Park," Park said.</p>
    </div>
    <div class="lp-mock-chat">
      <div class="lp-you">What did Hale say to Nora at the fundraiser?</div>
      <div class="lp-them"><span class="sa-avatar sm" style="background:#047857">P</span>
        <div><b>Park</b>Don't know. Wasn't there. Ask Hale.</div></div>
      <div class="lp-mock-note">Park wasn't in that scene, so he doesn't know.</div>
    </div>
  </div>
  <div class="lp-objection">
    <div class="lp-objection-head"><span class="sa-avatar sm" style="background:#047857">P</span>
      Park objects to beat 3</div>
    <div class="lp-objection-text">“You have the wrong man. I pack lunches. I leave them by the door.
    I do not walk out on my crying kids.”</div>
    <div class="lp-objection-actions"><span class="lp-btn-accept">Accept</span><span>Override</span></div>
  </div>
</div>
"""

HOW_IT_WORKS = """
<section class="lp-section" id="how">
  <div class="lp-eyebrow">How it works</div>
  <h2 class="lp-h2">From a premise to a living cast in minutes</h2>
  <div class="lp-steps">
    <div class="lp-step"><div class="lp-step-n">1</div><h3>Set the stage</h3>
      <p>Write your premise and give each character a background, wants, fears, a secret and a voice.</p></div>
    <div class="lp-step"><div class="lp-step-n">2</div><h3>Talk to your cast</h3>
      <p>Interview any character by text or voice. "Hey Hale, what are you hiding?" They answer in character.</p></div>
    <div class="lp-step"><div class="lp-step-n">3</div><h3>Direct a chapter</h3>
      <p>Describe what happens. The Director plans the beats, each character reacts, and anyone pushed out of character objects.</p></div>
    <div class="lp-step"><div class="lp-step-n">4</div><h3>They remember</h3>
      <p>After each chapter, characters keep memories of only the scenes they were in. Your story stays consistent.</p></div>
  </div>
</section>
"""

FORMATS_SECTION = """
<section class="lp-section" id="formats">
  <div class="lp-eyebrow">One studio, four formats</div>
  <h2 class="lp-h2">Write the story the way it will be told</h2>
  <div class="lp-features lp-formats">
    <div class="lp-feature"><span class="sa-icon">menu_book</span><h3>Novel</h3>
      <p>Chapters of rich prose, grouped into parts. A book-style page with drop caps.</p>
      <div class="ns-shape">Parts → Chapters</div></div>
    <div class="lp-feature"><span class="sa-icon">auto_stories</span><h3>Light novel</h3>
      <p>Fast, voice-driven chapters in volumes, each ending on a hook.</p>
      <div class="ns-shape">Volumes → Chapters</div></div>
    <div class="lp-feature"><span class="sa-icon">movie</span><h3>Feature film</h3>
      <p>A real screenplay in three acts, with beat guidance from setup to final image.</p>
      <div class="ns-shape">Acts → Scenes</div></div>
    <div class="lp-feature"><span class="sa-icon">live_tv</span><h3>TV series</h3>
      <p>Sitcoms and one-hour dramas: cold opens, acts and tags, season after season.</p>
      <div class="ns-shape">Seasons → Episodes → Acts</div></div>
  </div>
</section>
"""

FEATURES = """
<section class="lp-section" id="features">
  <div class="lp-eyebrow">Why writers love it</div>
  <h2 class="lp-h2">A writing room that pushes back</h2>
  <div class="lp-features">
    <div class="lp-feature"><span class="sa-icon">psychology</span><h3>Honest memory</h3>
      <p>Each character knows only what they lived through. No more characters who magically know everything.</p></div>
    <div class="lp-feature"><span class="sa-icon">front_hand</span><h3>Characters that object</h3>
      <p>If a scene contradicts who a character has become, they tell you, in their own voice. Accept or override.</p></div>
    <div class="lp-feature"><span class="sa-icon">mic</span><h3>Just talk</h3>
      <p>Speak instead of typing. Ask a character a question, describe the next chapter, or update a profile.</p></div>
    <div class="lp-feature"><span class="sa-icon">auto_awesome</span><h3>A Director at your side</h3>
      <p>Brainstorm with an agent that knows your whole story, from the outline to every chapter.</p></div>
    <div class="lp-feature"><span class="sa-icon">edit_note</span><h3>Your words, your call</h3>
      <p>Generate a chapter with your cast or write it yourself. Edit everything; nothing is final until you say so.</p></div>
    <div class="lp-feature"><span class="sa-icon">view_day</span><h3>Chapters become comics</h3>
      <p>Turn any chapter into a vertical-scroll manhwa. Every character is drawn from their own reference sheet, so they look the same in every panel.</p></div>
  </div>
</section>
"""

CLOSING = """
<section class="lp-cta">
  <h2 class="lp-h2">Your characters are waiting to talk back.</h2>
  <p>Start your first story in under a minute. It's free.</p>
</section>
"""

FOOTER = f"""<footer class="lp-footer"><span>{ui.logo('sm')} {APP_NAME}</span>
<span>Built for the Meta hackathon on Muse Spark</span></footer>"""


def landing_page(user):
    ui.css("""
    .stApp { background:
        radial-gradient(1100px 520px at 12% -8%, var(--sa-glow-1), transparent 60%),
        radial-gradient(900px 520px at 95% 4%, var(--sa-glow-2), transparent 60%),
        var(--sa-bg) !important; }
    [data-testid="stMainBlockContainer"] { max-width: 1180px !important; margin: 0 auto; padding-top: 18px !important; }
    """)
    _top_nav(user)

    text, mock = st.columns([1.05, 1], gap="large", vertical_alignment="center")
    with text:
        st.html(HERO_TEXT)
        with st.container(horizontal=True, key="hero_ctas"):
            if user:
                st.button("Open your library", type="primary", icon=":material/arrow_forward:", key="hero_library",
                          on_click=nav, args=("library",))
            else:
                st.button("Start writing free", type="primary", icon=":material/arrow_forward:", key="hero_start",
                          on_click=nav, args=("signup",))
                st.button("I have an account", key="hero_signin", on_click=nav, args=("login",))
        st.html('<p class="lp-fineprint">No credit card. Your stories stay private to your account.</p>')
    with mock:
        st.html(HERO_MOCK)

    st.html(HOW_IT_WORKS + FORMATS_SECTION + FEATURES + CLOSING)
    with st.container(horizontal=True, horizontal_alignment="center", key="closing_cta"):
        st.button("Create your first story" if not user else "Go to your library", type="primary",
                  icon=":material/arrow_forward:", key="closing_start",
                  on_click=nav, args=("library" if user else "signup",))
    st.html(FOOTER)


# =====================================================================
# Sign in / create account
# =====================================================================

def auth_page(mode):
    ui.css("""
    .stApp { background:
        radial-gradient(800px 600px at 0% 0%, var(--sa-glow-1), transparent 60%),
        radial-gradient(700px 600px at 100% 100%, var(--sa-glow-2), transparent 60%),
        var(--sa-bg) !important; }
    [data-testid="stMainBlockContainer"] { max-width: 1180px !important; margin: 0 auto; padding-top: 18px !important; }
    """)
    with st.container(key="topnav", horizontal=True, vertical_alignment="center"):
        st.button(APP_NAME, key="nav_home", type="tertiary", on_click=nav)
        st.space("stretch")
        ui.theme_button("theme_auth")

    _, middle, _ = st.columns([1, 1.15, 1])
    with middle, st.container(key="auth_card"):
        st.session_state.setdefault("auth_mode", SIGN_UP if mode == "signup" else SIGN_IN)
        choice = st.session_state["auth_mode"]
        title = "Welcome back" if choice == SIGN_IN else "Start writing with your cast"
        sub = ("Sign in to continue your stories." if choice == SIGN_IN
               else "Create a free account. It takes ten seconds.")
        st.html(f'<div class="auth-head">{ui.logo("lg")}<h1>{title}</h1><p>{sub}</p></div>')
        choice = st.segmented_control("Mode", [SIGN_IN, SIGN_UP], key="auth_mode", required=True,
                                      label_visibility="collapsed", width="stretch")

        with st.form("auth_form", border=False):
            name = st.text_input("Your name", placeholder="Jane Austen") if choice == SIGN_UP else ""
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password",
                                     placeholder="At least 8 characters" if choice == SIGN_UP else "")
            submitted = st.form_submit_button(choice, type="primary", width="stretch")

        if submitted:
            if choice == SIGN_IN:
                user = accounts.authenticate(email, password)
                if user is None:
                    st.error("That email and password don't match an account.")
                    return
                ui.sign_in(user)
                nav("library")
                st.rerun()
            try:
                user = accounts.create_user(name, email, password)
            except ValueError as e:
                st.error(str(e))
                return
            # A story written with an earlier version of the app goes to the very first account.
            if accounts.is_first_user(user["id"]) and storage.import_legacy_story(user["id"]):
                ui.toast("We moved your existing story into your library.")
            ui.sign_in(user)
            nav("library")
            st.rerun()
        st.html('<p class="auth-fine">Your stories are private to your account.</p>')
