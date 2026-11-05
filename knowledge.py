"""Who knows what: every secret and revelation in the story, and who knows each one.

The data comes from agents.py. Each character's card secret is a fact they know from the start;
after every chapter (or scene, or act) the model records who learned, suspected or got wrong
which fact, and only characters present in that part of the story can learn anything.

This page shows it three ways: a short brief (dramatic irony, kept secrets, suspicions), a grid
(secrets x characters) and a web (a drawn map linking characters to the secrets they hold).
A slider moves through the story to show who knew what at any point.
"""

import html

import streamlit as st

import agents
import formats
import storage
import ui
from agents import READER

GRID, WEB = "Grid", "Web"
STATE_TEXT = {"owner": "Keeps it", "knows": "Knows", "suspects": "Suspects", "believes_false": "Wrong idea"}
BRIEF_SIZE = 4
STATE_ICON = {"owner": "lock", "knows": "visibility", "suspects": "help", "believes_false": "report"}


def h(text):
    return html.escape(text or "")


def _cells(fact, upto):
    """Where everyone stands on a fact as of unit `upto`: {who: latest event}."""
    cells = {}
    for event in sorted(fact["events"], key=lambda e: e["chapter"]):  # stable: same-unit order is kept
        if event["chapter"] <= upto:
            cells[event["who"]] = event
    return cells


def _state(fact, event):
    if event["chapter"] == 0 and event["who"] == fact.get("owner"):
        return "owner"
    return event["state"]


def _label(fact):
    return fact.get("label") or fact["text"]


def _who(name):
    return "The reader" if name == READER else name


def _when(fmt, by_number, number, short=True):
    if number == 0:
        return "from the start"
    chapter = by_number.get(number)
    if chapter is None:
        return f"{fmt['unit']} {number}"
    place = formats.place_of(fmt, chapter)
    if formats.is_tv(fmt):
        return f"S{place['season']} E{place['episode']} · {formats.unit_label(fmt, place)}"
    return (formats.short_label if short else formats.label)(fmt, place, number)


# =====================================================================
# The page
# =====================================================================

def knowledge_view(story, chapters, characters, fmt):
    knowledge = agents.sync_secret_facts(storage.load_knowledge(), characters)
    if any(not f.get("label") for f in knowledge["facts"]):
        with st.spinner("Reading your cast's secrets..."):
            try:
                agents.label_facts(knowledge)
            except Exception:
                pass  # the full text is shown instead of a short label
        storage.save_knowledge(knowledge)

    st.html('<div class="sa-eyebrow">Who knows what</div><div class="sa-title">Secrets &amp; knowledge</div>'
            f'<p class="sa-subtitle">Every secret and revelation in {h(story["title"] or "your story")}, and who '
            'knows it. Characters only learn what happens in scenes they are in.</p>')

    unscanned = [c for c in chapters if c["number"] > knowledge.get("scanned", 0)]
    if unscanned:
        _scan_prompt(story, chapters, characters, fmt, len(unscanned))

    if not knowledge["facts"]:
        st.html('<div class="kw-empty"><span class="sa-icon lg">lock_open</span><h3>No secrets yet</h3>'
                '<p>Give your characters secrets in their profiles, or write a few chapters. This map fills in as '
                'secrets are kept, spread and revealed.</p></div>')
        return

    by_number = {c["number"]: c for c in chapters}
    with st.container(horizontal=True, vertical_alignment="bottom", key="kw_controls"):
        st.session_state.setdefault("kw_view", GRID)
        view = st.segmented_control("View", [GRID, WEB], key="kw_view", required=True,
                                    format_func=lambda v: f":material/{'grid_view' if v == GRID else 'hub'}: {v}")
        stops = [0] + [c["number"] for c in chapters]
        if len(stops) > 1:
            if st.session_state.get("kw_upto") not in stops:
                st.session_state["kw_upto"] = stops[-1]
            upto = st.select_slider("Who knew what, as of", stops, key="kw_upto",
                                    format_func=lambda n: "The beginning" if n == 0 else _when(fmt, by_number, n))
        else:
            upto = 0

    facts = sorted((f for f in knowledge["facts"] if _cells(f, upto)), key=lambda f: (f.get("owner") is None,))
    names = [c["name"] for c in characters]
    _brief(facts, names, upto, fmt, by_number)
    if view == GRID:
        st.html(_grid(facts, characters, upto, fmt, by_number))
    else:
        # st.html strips SVG, so the web is drawn with st.markdown (all of its text is escaped above).
        st.markdown(_web(facts, characters, upto), unsafe_allow_html=True)
    st.html(_legend())

    with st.popover("Rescan the whole story", icon=":material/refresh:"):
        st.caption("Reads every part of the story again to rebuild this map, for example after you edited "
                   "chapters. Takes about 15 seconds per part.")
        if st.button("Rescan now", key="kw_rescan"):
            _scan(story, chapters, characters, fmt, fresh=True)


def _scan_prompt(story, chapters, characters, fmt, count):
    with st.container(key="kw_scan"):
        st.html(f'<div class="sa-guide"><span class="sa-icon">travel_explore</span><div>'
                f'<div class="sa-guide-title">{count} {fmt["units"] if count != 1 else fmt["unit"].lower()} not '
                'tracked yet</div><div class="sa-guide-text">Written before this map existed, or while tracking was '
                'off. Scan them to see who learned what.</div></div></div>')
        if st.button(f"Scan {count} {fmt['units'] if count != 1 else fmt['unit'].lower()}", type="primary",
                     icon=":material/travel_explore:", key="kw_scan_btn"):
            _scan(story, chapters, characters, fmt, fresh=False)


def _scan(story, chapters, characters, fmt, fresh):
    try:
        progress = st.progress(0.0, text="Reading the story...")

        def on_progress(i, total, chapter):
            progress.progress(i / total, text=f"Reading {formats.label(fmt, formats.place_of(fmt, chapter), chapter['number'])}...")

        agents.scan_knowledge(story, chapters, characters, fresh=fresh, on_progress=on_progress)
        ui.toast("Who-knows-what map updated.")
        st.rerun()
    except Exception as e:
        st.error(f"Could not finish the scan: {e}")


# =====================================================================
# The brief
# =====================================================================

def _brief(facts, names, upto, fmt, by_number):
    """A few plain-language observations: dramatic irony, kept secrets, suspicions, wrong ideas."""
    notes = []
    for fact in facts:
        cells, label = _cells(fact, upto), f"<b>{h(_label(fact))}</b>"
        holders = [n for n in names if n in cells]
        # Only gaps that matter: everyone, for a secret; otherwise the people the fact is about.
        involved = names if fact.get("owner") else [n for n in names if n.lower() in (fact["text"] + " " + _label(fact)).lower()]
        subject = next((n for n in names if _label(fact).lower().startswith(n.lower())), None)  # "Park's silence..."
        unaware = [n for n in involved if n not in cells and n not in (fact.get("owner"), subject)]
        if READER in cells and unaware:
            who = ", ".join(unaware[:3]) + (" and others" if len(unaware) > 3 else "")
            notes.append(("theater_comedy", f"The reader knows {label}, but {h(who)} "
                                            f"{'doesn&#x27;t' if len(unaware) == 1 else 'don&#x27;t'}. Every scene "
                                            "with them has built-in tension."))
        if fact.get("owner") and holders == [fact["owner"]] and READER not in cells:
            notes.append(("lock", f"Only {h(fact['owner'])} knows {label}. Not revealed to anyone yet, "
                                  "not even the reader."))
        for name, event in cells.items():
            if name != READER and event["state"] == "suspects":
                notes.append(("help", f"{h(name)} suspects {label} ({h(event['how'])}, "
                                      f"{h(_when(fmt, by_number, event['chapter']))})."))
            if name != READER and event["state"] == "believes_false":
                notes.append(("report", f"{h(name)} has the wrong idea about {label}."))
    latest = [(f, e) for f in facts for e in _cells(f, upto).values() if e["chapter"] == upto and upto > 0]
    for fact, event in latest[:2]:
        verb = {"knows": "learned", "suspects": "started to suspect",
                "believes_false": "got the wrong idea about"}[event["state"]]
        notes.append(("bolt", f"In {h(_when(fmt, by_number, upto, short=False))}, {h(_who(event['who']))} {verb} "
                              f"<b>{h(_label(fact))}</b>."))
    if not notes:
        return
    priority = {"theater_comedy": 0, "report": 1, "help": 2, "bolt": 3, "lock": 4}
    notes.sort(key=lambda note: priority[note[0]])  # stable: story order within each kind
    items = "".join(f'<li><span class="sa-icon">{icon}</span><span>{text}</span></li>' for icon, text in notes[:BRIEF_SIZE])
    st.html(f'<div class="kw-brief"><div class="kw-brief-title"><span class="sa-icon">auto_awesome</span>'
            f'Brief</div><ul>{items}</ul></div>')


# =====================================================================
# The grid: one row per secret, one column per character (plus the reader)
# =====================================================================

def _pill(fact, event, fmt, by_number):
    state = _state(fact, event)
    when = "from the start" if event["chapter"] == 0 else _when(fmt, by_number, event["chapter"])
    detail = when if state in ("owner",) else f"{when} · {event['how']}" if event.get("how") else when
    return (f'<span class="kw-pill {state}"><span class="sa-icon">{STATE_ICON[state]}</span>{STATE_TEXT[state]}</span>'
            f'<div class="kw-detail">{h(detail)}</div>')


def _grid(facts, characters, upto, fmt, by_number):
    people = [c["name"] for c in characters] + [READER]
    head = "".join(
        f'<th>{ui.avatar(name, "sm")}<span>{h(name)}</span></th>' if name != READER
        else '<th class="kw-reader-col"><span class="sa-icon">visibility</span><span>Reader</span></th>'
        for name in people)
    rows = []
    for fact in facts:
        cells = _cells(fact, upto)
        origin = (f'<span class="sa-icon">lock</span>{h(fact["owner"])}&#x27;s secret' if fact.get("owner")
                  else f'Came out {h(_when(fmt, by_number, min(e["chapter"] for e in fact["events"])))}')
        row = (f'<td class="kw-fact" title="{h(fact["text"])}"><div class="kw-fact-label">{h(_label(fact))}</div>'
               f'<div class="kw-fact-origin">{origin}</div></td>')
        for name in people:
            event = cells.get(name)
            row += (f'<td>{_pill(fact, event, fmt, by_number)}</td>' if event
                    else '<td><span class="kw-unknown" title="Doesn&#x27;t know">—</span></td>')
        rows.append(f"<tr>{row}</tr>")
    return (f'<div class="kw-grid-wrap"><table class="kw-grid"><thead><tr><th class="kw-fact-head">Secret</th>{head}'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


# =====================================================================
# The web: characters on the left, secrets on the right, a line for everyone who knows
# =====================================================================

def _web(facts, characters, upto):
    people = [c["name"] for c in characters] + [READER]
    width, pad, row = 640, 30, 62  # drawn at about the center panel's real width, so text stays readable
    height = pad * 2 + max(len(people), len(facts), 1) * row

    def spread(count):
        step = (height - 2 * pad) / count
        return [pad + step * (i + 0.5) for i in range(count)]

    person_y = dict(zip(people, spread(len(people))))
    fact_y = spread(len(facts)) if facts else []
    px, fx, fw = 132, 336, 300

    edges, nodes = [], []
    for fact, y2 in zip(facts, fact_y):
        for who, event in _cells(fact, upto).items():
            if who not in person_y:
                continue
            state, y1, x1 = _state(fact, event), person_y[who], px + 22
            mid = (x1 + fx) / 2
            edges.append(f'<path class="kw-edge {state}" d="M{x1},{y1:.1f} C{mid:.0f},{y1:.1f} {mid:.0f},{y2:.1f} '
                         f'{fx},{y2:.1f}"><title>{h(_who(who))}: {STATE_TEXT[state]} · {h(_label(fact))}</title></path>')
        label = _label(fact)
        short = label if len(label) <= 34 else label[:33] + "…"
        lock = (f'<text class="kw-icon" x="{fx + fw - 28}" y="{y2 + 6:.1f}">lock</text>' if fact.get("owner") else "")
        nodes.append(f'<g><title>{h(fact["text"])}</title><rect class="kw-box" x="{fx}" y="{y2 - 21:.1f}" '
                     f'width="{fw}" height="42" rx="12"/><text class="kw-fact-text" x="{fx + 16}" y="{y2 + 5:.1f}">'
                     f'{h(short)}</text>{lock}</g>')
    for name, y in person_y.items():
        if name == READER:
            nodes.append(f'<g><circle class="kw-reader" cx="{px}" cy="{y:.1f}" r="20"/>'
                         f'<text class="kw-icon" x="{px - 9}" y="{y + 6:.1f}">visibility</text>'
                         f'<text class="kw-name" x="{px - 32}" y="{y + 5:.1f}" text-anchor="end">Reader</text></g>')
        else:
            nodes.append(f'<g><circle cx="{px}" cy="{y:.1f}" r="20" fill="{ui.color_for(name)}"/>'
                         f'<text class="kw-initial" x="{px}" y="{y + 5:.1f}" text-anchor="middle">{h(name[:1].upper())}'
                         f'</text><text class="kw-name" x="{px - 32}" y="{y + 5:.1f}" text-anchor="end">{h(name)}</text></g>')
    return (f'<div class="kw-web-wrap"><svg class="kw-web" viewBox="0 0 {width} {height:.0f}" role="img" '
            f'aria-label="Who knows which secret">{"".join(edges)}{"".join(nodes)}</svg></div>')


def _legend():
    items = "".join(f'<span class="kw-pill {state}"><span class="sa-icon">{STATE_ICON[state]}</span>{text}</span>'
                    for state, text in STATE_TEXT.items())
    return f'<div class="kw-legend">{items}<span class="kw-unknown">— doesn&#x27;t know</span></div>'
