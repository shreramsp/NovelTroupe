"""The story formats NovelTroupe supports, and everything that differs between them.

A story is a sequence of *units*: chapters (novel, light novel), scenes (film) or the parts of an
episode (TV). Each saved unit has a global `number` (its order in the story) and a `place` that
says where it sits in the format's structure:

    novel         {"part": 1}
    light_novel   {"volume": 1}
    film          {"act": 1}
    tv_sitcom     {"season": 1, "episode": 1, "part": 0}    part = index into the episode's parts
    tv_drama      (same as tv_sitcom)

The "structure", "style" and hint texts below are sent to the Director and the writer, so this
file is also where you tune how each format is planned and written.
"""

ROMAN = {1: "I", 2: "II", 3: "III"}
SCREENPLAY_WORDS_PER_PAGE = 180  # one screenplay page is roughly one minute on screen

SCREENPLAY_STYLE = """Write in standard screenplay format, as plain text:
- Start every scene with a scene heading in capitals: INT. or EXT., the location, a dash and the time of day (for example INT. PARK'S KITCHEN - NIGHT).
- Action lines are short paragraphs in the present tense describing only what we can see and hear. No inner thoughts.
- Before each speech, put the speaking character's name in CAPITALS on its own line, with the dialogue on the next line. A parenthetical such as (quietly) goes on its own line between the name and the dialogue.
- Leave a blank line between blocks. No camera directions, no markdown, no bold."""

FORMATS = {
    "novel": {
        "name": "Novel",
        "example": 'e.g. Park finally opens the letter. Joon finds him at the kitchen table at 3 a.m.',
        "icon": "menu_book",
        "unit": "Chapter", "units": "chapters", "section": "Chapters", "group": "Part",
        "layout": "prose", "words": 1500, "beats": "4 to 7",
        "forgotten_after": 3, "forgotten_unit": "chapters",
        "structure": "A novel is told in chapters, each a complete movement of the story that changes something. "
                     "Across the whole book it follows a three-act shape: setup, rising confrontation, then climax "
                     "and resolution.",
        "style": "Polished literary prose in the third person, past tense, unless the outline asks for something "
                 "else. Ground every scene in sensory detail and the point-of-view character's inner life, and "
                 "vary the rhythm of the sentences. If the chapter has more than one scene, separate them with a "
                 "line containing only * * *.",
        "hint": "Each chapter should change something: a decision, a discovery or a loss. End it with a reason to "
                "turn the page.",
        "title_hint": "an evocative chapter title of 2 to 5 words, like one in a published novel",
    },
    "light_novel": {
        "name": "Light novel",
        "example": 'e.g. I sneak into the academy library at midnight and run straight into the villainess.',
        "icon": "auto_stories",
        "unit": "Chapter", "units": "chapters", "section": "Volumes", "group": "Volume",
        "layout": "prose", "words": 1200, "beats": "4 to 6",
        "forgotten_after": 3, "forgotten_unit": "chapters",
        "structure": "A light novel is released in volumes. Each volume tells one complete arc in about 8 to 12 "
                     "short chapters, and every chapter ends on a hook that makes the reader open the next one.",
        "style": "Light novel style: first person from the main point-of-view character unless the outline says "
                 "otherwise. Short paragraphs, plenty of dialogue, vivid inner monologue, in an energetic, accessible "
                 "voice that still feels like real people. Use any running joke or catchphrase at most once in the "
                 "chapter, and never let a character's quirk take over the scene. End the chapter on a hook.",
        "hint": "Keep it punchy and voice-driven, and end on a hook: a reveal, a threat or a question.",
        "title_hint": "a catchy light-novel style chapter title (it can be long and playful) that says what "
                      "actually happens in the chapter, without running jokes or gimmicks",
    },
    "film": {
        "name": "Feature film",
        "example": 'e.g. Nora corners Hale at the fundraiser, in front of the cameras.',
        "icon": "movie",
        "unit": "Scene", "units": "scenes", "section": "Screenplay", "group": "Act",
        "layout": "screenplay", "words": 700, "beats": "3 to 5",
        "forgotten_after": 10, "forgotten_unit": "scenes",
        "structure": "A feature film is a screenplay of about 90 to 120 pages in three acts: Act I (setup, about "
                     "a quarter), Act II (confrontation, about half) and Act III (resolution, about a quarter). "
                     "It is told in scenes of one to four pages, with only what can be seen and heard.",
        "style": SCREENPLAY_STYLE + "\nThis is one scene, or two very short connected scenes, of a feature "
                                    "film. Tell it visually: show, don't tell.",
        "act_hints": {
            1: "Act I · Setup. Typical beats: opening image, the hero's ordinary world, the catalyst that "
               "upends it, the debate, and the decision that breaks into Act II.",
            2: "Act II · Confrontation. Typical beats: new world and fun and games, a B story (often a "
               "relationship), the midpoint twist, the bad guys closing in, all is lost, and the dark night "
               "of the soul.",
            3: "Act III · Resolution. Typical beats: the finale where the hero applies what they learned, the "
               "climax, and a final image that mirrors the opening.",
        },
        "title_hint": "a short name for the scene (2 to 4 words), like 'Kitchen Standoff'",
    },
    "tv_sitcom": {
        "name": "TV sitcom",
        "example": "e.g. Nora accidentally tells the whole coffee shop Hale's secret. B plot: Park tries to return a gift.",
        "icon": "live_tv",
        "unit": "Act", "units": "acts", "section": "Episodes", "group": "Episode",
        "layout": "screenplay", "beats": "3 to 6",
        "forgotten_after": 2, "forgotten_unit": "episodes",
        "parts": ["Cold open", "Act One", "Act Two", "Tag"],
        "part_words": [450, 1100, 1100, 350],
        "part_hints": [
            "Cold open: a short, self-contained comic scene before the titles. It can tease the episode or "
            "stand alone. End on a laugh.",
            "Act One: set up the A, B and C plots, build each comic problem, and end on a complication.",
            "Act Two: escalate everything, let the plots collide, and resolve them with a bit of heart.",
            "Tag: a short button scene after the resolution, one last laugh.",
        ],
        "structure": "A half-hour sitcom episode (about 22 minutes) has a cold open, Act One, Act Two and a tag. "
                     "Each episode runs an A plot, a B plot and often a C plot across the ensemble, and every "
                     "main character should get a moment. Episodes are mostly self-contained within a season.",
        "style": SCREENPLAY_STYLE + "\nMulti-camera sitcom style: quick rhythm, setups and punchlines, humour "
                                    "that comes from character, and a running gag if one fits.",
        "title_hint": "a short, funny name for this part of the episode (2 to 5 words)",
    },
    "tv_drama": {
        "name": "TV drama",
        "example": "e.g. Nora finds the missing radio log. Hale's aide follows her home.",
        "icon": "live_tv",
        "unit": "Act", "units": "acts", "section": "Episodes", "group": "Episode",
        "layout": "screenplay", "beats": "3 to 6",
        "forgotten_after": 2, "forgotten_unit": "episodes",
        "parts": ["Teaser", "Act One", "Act Two", "Act Three", "Act Four", "Act Five"],
        "part_words": [500, 900, 900, 900, 900, 900],
        "part_hints": [
            "Teaser: hook the audience in two to four minutes and raise the episode's central question.",
            "Act One: establish the episode's problem and what is at stake. End on a turn.",
            "Act Two: complicate it; the characters pursue the goal and it pushes back. End on a reversal.",
            "Act Three: the episode's midpoint. Raise the stakes and end on a cliffhanger.",
            "Act Four: things fall apart; the darkest moment of the episode.",
            "Act Five: the climax and resolution, plus a hook into the season arc.",
        ],
        "structure": "A one-hour drama episode (about 45 to 60 minutes) has a teaser and five acts, each ending "
                     "on a turn or a cliffhanger before the break. Each episode tells its own story while "
                     "moving a season-long arc forward.",
        "style": SCREENPLAY_STYLE + "\nOne-hour drama style: tension and subtext, and end the act on a turn "
                                    "or a cliffhanger.",
        "title_hint": "a short, dramatic name for this act (2 to 5 words)",
    },
}
for _format_id, _fmt in FORMATS.items():
    _fmt["id"] = _format_id


# The four cards shown when starting a story. "tv" then asks: sitcom or drama.
CHOICES = {
    "novel": {"name": "Novel", "icon": "menu_book", "tagline": "Chapters of rich prose",
              "shape": "Parts → Chapters"},
    "light_novel": {"name": "Light novel", "icon": "auto_stories", "tagline": "Fast, voice-driven serials",
                    "shape": "Volumes → Chapters"},
    "film": {"name": "Feature film", "icon": "movie", "tagline": "A screenplay in three acts",
             "shape": "Acts → Scenes"},
    "tv": {"name": "TV series", "icon": "live_tv", "tagline": "Sitcoms and dramas, episode by episode",
           "shape": "Seasons → Episodes → Acts"},
}
TV_KINDS = {"tv_sitcom": "Sitcom · half-hour", "tv_drama": "Drama · one-hour"}

# What the "New story" page shows for each format: the structure, a few facts, and a sample page.
PREVIEWS = {
    "novel": {
        "tree": [("Part One", ["Chapter 1 · The Letter", "Chapter 2 · Ashes on the Sill", "…"]),
                 ("Part Two", ["Chapter 9 · Homecoming", "…"])],
        "facts": ["Chapters of about 1,500 words", "Group chapters into parts if you like", "Book-style prose page"],
        "sample": "The letter arrived on a Tuesday, which was the day Park did the books. He set it on the counter, "
                  "unopened, and finished the column of numbers first.\n\nIt was only when the shop was dark that "
                  "he let himself read the name on the back.",
    },
    "light_novel": {
        "tree": [("Volume 1", ["Chapter 1 · I Woke Up as the Villain's Butler", "Chapter 2 · Rule One: Don't Die",
                               "…"]),
                 ("Volume 2", ["Chapter 13 · The Academy Has a Dress Code?!", "…"])],
        "facts": ["Volumes of 8–12 chapters", "Short chapters of about 1,200 words", "A hook at every chapter end"],
        "sample": "\"Wait. I'm the villain?\"\n\nI stared at the mirror. The face staring back was gorgeous, "
                  "arrogant, and absolutely going to die in Volume 3.\n\nOkay. Okay. Don't panic. Rule one: "
                  "don't die.",
    },
    "film": {
        "tree": [("Act I · Setup", ["Scene 1 · EXT. HARBOR - DAWN", "Scene 2 · INT. LIGHTHOUSE - DAY", "…"]),
                 ("Act II · Confrontation", ["Scene 18 · The Midpoint", "…"]),
                 ("Act III · Resolution", ["Scene 41 · Final Image"])],
        "facts": ["Three acts, about 90–120 pages", "Scenes of about 3 pages", "Industry screenplay layout"],
        "sample": "INT. PARK'S KITCHEN - NIGHT\n\nOil pops in a pan. PARK (50s) slides it off the heat without "
                  "looking.\n\nPARK\nHomework stays on the placemat.\n\nHANA\n(not looking up)\nIt is on the "
                  "placemat. Mostly.",
    },
    "tv_sitcom": {
        "tree": [("Season 1 · Episode 1", ["Cold open", "Act One", "Act Two", "Tag"]),
                 ("Season 1 · Episode 2", ["Cold open", "…"])],
        "facts": ["Seasons of episodes", "Cold open, two acts and a tag", "About 22 minutes per episode"],
        "sample": "INT. COFFEE HOUSE - DAY\n\nThe gang on the couch. NORA bursts in, soaked to the bone.\n\nNORA\n"
                  "Don't. Nobody say anything.\n\nHALE\n(beat)\nIs it raining?",
    },
    "tv_drama": {
        "tree": [("Season 1 · Episode 1", ["Teaser", "Act One", "Act Two", "Act Three", "Act Four", "Act Five"]),
                 ("Season 1 · Episode 2", ["Teaser", "…"])],
        "facts": ["Seasons of episodes", "A teaser and five acts", "About 45–60 minutes per episode"],
        "sample": "EXT. RIDGE 614 - NIGHT\n\nWind. A single flashlight beam cuts across the rocks.\n\nNORA (V.O.)\n"
                  "Forty men went up this ridge. Three came down.",
    },
}


# =====================================================================
# Working with places
# =====================================================================

def display_name(fmt):
    """The format's name inside a sentence: 'a novel', 'a feature film', 'a TV sitcom'."""
    name = fmt["name"]
    return name if name.startswith("TV") else name[0].lower() + name[1:]


def get(format_id):
    return FORMATS.get(format_id or "novel", FORMATS["novel"])


def is_tv(fmt):
    return "parts" in fmt


def first_place(fmt):
    if is_tv(fmt):
        return {"season": 1, "episode": 1, "part": 0}
    return {"novel": {"part": 1}, "light_novel": {"volume": 1}, "film": {"act": 1}}[fmt["id"]]


def place_of(fmt, chapter):
    """Where a saved unit sits (units saved before formats existed count as the first group)."""
    return chapter.get("place") or first_place(fmt)


def label(fmt, place, number):
    """Full position, e.g. 'Volume 2 · Chapter 14', 'Act II · Scene 23', 'Season 1 · Episode 3 · Act One'."""
    if is_tv(fmt):
        return f"Season {place['season']} · Episode {place['episode']} · {fmt['parts'][place['part']]}"
    if fmt["id"] == "film":
        return f"Act {ROMAN[place['act']]} · Scene {number}"
    if fmt["id"] == "light_novel":
        return f"Volume {place['volume']} · Chapter {number}"
    return (f"Part {place['part']} · " if place["part"] > 1 else "") + f"Chapter {number}"


def short_label(fmt, place, number):
    """Compact position for badges: 'Ch 5', 'Sc 12', 'S1 E3'."""
    if is_tv(fmt):
        return f"S{place['season']} E{place['episode']}"
    return f"{'Sc' if fmt['id'] == 'film' else 'Ch'} {number}"


def group_title(fmt, place):
    """The heading a unit is listed under in the studio's left panel."""
    if is_tv(fmt):
        return f"Season {place['season']} · Episode {place['episode']}"
    if fmt["id"] == "film":
        return f"Act {ROMAN[place['act']]} · {['Setup', 'Confrontation', 'Resolution'][place['act'] - 1]}"
    if fmt["id"] == "light_novel":
        return f"Volume {place['volume']}"
    return f"Part {place['part']}"


def show_group_titles(fmt, chapters):
    """Novels only show part headings once a second part exists; every other format always does."""
    if fmt["id"] != "novel":
        return True
    return any(place_of(fmt, c)["part"] > 1 for c in chapters)


def unit_label(fmt, place):
    """What one unit is called: 'Chapter', 'Scene', or the episode part ('Cold open', 'Act Two')."""
    return fmt["parts"][place["part"]] if is_tv(fmt) else fmt["unit"]


def next_options(fmt, chapters):
    """Where the next unit can go, as [(choice label, place)]. The first choice is the natural next step."""
    if not chapters:
        place = first_place(fmt)
        return [(label(fmt, place, 1), place)]
    last = place_of(fmt, chapters[-1])
    if is_tv(fmt):
        season, episode, part = last["season"], last["episode"], last["part"]
        options = []
        if part + 1 < len(fmt["parts"]):
            options.append((f"Episode {episode}: {fmt['parts'][part + 1]}",
                            {"season": season, "episode": episode, "part": part + 1}))
        options.append((f"Start Episode {episode + 1}", {"season": season, "episode": episode + 1, "part": 0}))
        options.append((f"Start Season {season + 1}", {"season": season + 1, "episode": 1, "part": 0}))
        return options
    if fmt["id"] == "film":
        act = last["act"]
        options = [(f"Stay in Act {ROMAN[act]}", {"act": act})]
        if act < 3:
            options.append((f"Move to Act {ROMAN[act + 1]}", {"act": act + 1}))
        return options
    if fmt["id"] == "light_novel":
        volume = last["volume"]
        return [(f"Continue Volume {volume}", {"volume": volume}), (f"Begin Volume {volume + 1}", {"volume": volume + 1})]
    part = last["part"]
    return [("Next chapter", {"part": part}), (f"Begin Part {part + 1}", {"part": part + 1})]


def hint(fmt, place, chapters):
    """Guidance for writing at this place (shown in the editor and sent to the Director)."""
    if is_tv(fmt):
        return fmt["part_hints"][place["part"]]
    if fmt["id"] == "film":
        return fmt["act_hints"][place["act"]]
    if fmt["id"] == "light_novel":
        count = sum(1 for c in chapters if place_of(fmt, c)["volume"] == place["volume"])
        return (f"This will be chapter {count + 1} of Volume {place['volume']}. A volume usually tells one "
                f"complete arc in about 8 to 12 chapters. {fmt['hint']}")
    return fmt["hint"]


def progress(fmt, place, chapters):
    """Steps of the current group for the editor's progress strip, as [(name, state)].

    state is "done", "now" or "todo". Empty for formats without fixed steps.
    """
    if is_tv(fmt):
        done = {place_of(fmt, c)["part"] for c in chapters
                if (place_of(fmt, c)["season"], place_of(fmt, c)["episode"]) == (place["season"], place["episode"])}
        return [(name, "now" if i == place["part"] else "done" if i in done else "todo")
                for i, name in enumerate(fmt["parts"])]
    if fmt["id"] == "film":
        return [(f"Act {ROMAN[a]}", "now" if a == place["act"] else "done" if a < place["act"] else "todo")
                for a in (1, 2, 3)]
    return []


def words_for(fmt, place):
    return fmt["part_words"][place["part"]] if is_tv(fmt) else fmt["words"]


def step(fmt, place, number):
    """A position used to measure absence: episodes for TV, units for everything else."""
    return (place["season"], place["episode"]) if is_tv(fmt) else number


def pages(words):
    """Screenplay pages for this many words (at least 1 once anything is written)."""
    return max(1, round(words / SCREENPLAY_WORDS_PER_PAGE)) if words else 0


def _pages_text(words):
    count = pages(words)
    return f"{count} {'page' if count == 1 else 'pages'}"


def reading_meta(fmt, words):
    if fmt["layout"] == "screenplay":
        return f"≈ {_pages_text(words)} · ≈ {pages(words)} min on screen"
    return f"{words:,} words · {max(1, round(words / 230))} min read"


def summary(fmt, places, words):
    """One line for a library card, e.g. '2 volumes · 14 chapters'."""
    count = len(places)
    if is_tv(fmt):
        episodes = len({(p["season"], p["episode"]) for p in places})
        return f"{episodes} {'episode' if episodes == 1 else 'episodes'} · ≈ {_pages_text(words)}"
    if fmt["id"] == "film":
        return f"{count} {'scene' if count == 1 else 'scenes'} · ≈ {_pages_text(words)}"
    if fmt["id"] == "light_novel":
        volumes = len({p["volume"] for p in places}) or 1
        return f"{volumes} {'volume' if volumes == 1 else 'volumes'} · {count} chapters · {words:,} words"
    return f"{count} {'chapter' if count == 1 else 'chapters'} · {words:,} words"
