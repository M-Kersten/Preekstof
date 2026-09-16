"""The inputs both the Python and the TypeScript tests run, so the two stay comparable.

frontend/src/subtitleLayout.ts and frontend/src/crop.ts are hand-written mirrors of
backend/subtitles.py and backend/renderer.py. When they drift, the preview stops telling
the truth about the render, which nobody notices until a clip is already posted. These
cases are fed to both sides and the results are diffed.
"""

LAYOUT_TEXTS = [
    "Genade",
    "God is op zoek naar jou",
    "Hij wil dat je dichter bij hem komt.",
    "Niet omdat je perfect bent, maar omdat hij van je houdt.",
    "Wat is God vandaag aan het doen in jouw leven, denk je?",
    "Onvoorstelbaarheid",  # one word, longer than a line
    "   ruimte   rondom   en   dubbele   spaties   ",
    "Een hele lange zin die op geen enkele manier binnen drie regels past zonder dat het lettertype "
    "kleiner wordt gemaakt door de layoutfunctie, wat precies is wat we hier willen controleren.",
]

LAYOUT_SIZES = [24, 40, 48, 64, 80, 100, 140, 200]

# (width, height) of the source video
CROP_SOURCES = [
    (1920, 1080),   # landscape, the usual church camera
    (1280, 720),
    (1080, 1920),   # already vertical
    (720, 1280),
    (1440, 1080),   # 4:3
    (3840, 2160),
    (1080, 1080),   # square
    (2560, 1080),   # ultrawide
]

CROP_WINDOWS = [
    (0.5, 0.5, 1.0),
    (0.0, 0.0, 1.0),
    (1.0, 1.0, 1.0),
    (0.25, 0.75, 1.6),
    (0.5, 0.5, 0.3),    # below the minimum for a landscape source: must be clamped up
    (0.5, 0.5, 3.0),    # the top of the range the interface offers
    (0.33, 0.66, 2.4),
]

OUTPUT = (1080, 1920, 30)

# Paths for the crop to walk: (fps, positions, jumps). The preview reads these to draw the
# frame where the render will put it, so the two readings have to agree to the pixel. The
# awkward ones are the jumps (a camera cut, never slid into) and the ends of the path.
TRACKS = [
    (12.5, [0.5], []),
    (12.5, [0.2, 0.8], []),
    (12.5, [0.2, 0.8], [1]),                       # the frame jumped rather than panned
    (12.5, [0.5] * 12, []),                        # somebody standing still
    (12.5, [0.30, 0.31, 0.33, 0.36, 0.40, 0.45], []),
    (12.5, [0.4, 0.4, 0.9, 0.9, 0.35, 0.35], [2, 4]),
    (25.0, [0.1, 0.2, 0.3, 0.4], []),              # a path stored at another rate
    (12.5, [], []),                                # nothing was found
]

# Moments to read each of them at, including before the start and past the end.
TRACK_TIMES = [-1.0, 0.0, 0.01, 0.039, 0.04, 0.08, 0.121, 0.16, 0.24, 0.399, 0.4, 1.0, 30.0]

# Captions with and without the word timings whisper handed back, for the lighting-up. The
# awkward ones are the caption somebody has edited since, where the timings no longer count
# out the words, and the one that was never timed at all.
CAPTIONS = [
    # (start, end, text, [(start, end, word)] or None for "timings that fit")
    (1.0, 3.0, "God is op zoek naar jou", None),
    (1.0, 3.0, "God is op zoek naar jou", []),                       # never timed
    (0.0, 2.5, "Genade", None),
    (10.0, 14.0, "Niet omdat je perfect bent, maar omdat hij van je houdt", None),
    # Edited since: a word added, so the timings count out one too few.
    (1.0, 3.0, "God is op zoek naar jou vandaag",
     [(1.0, 1.4, "God"), (1.4, 1.6, "is"), (1.6, 1.9, "op"),
      (1.9, 2.2, "zoek"), (2.2, 2.6, "naar"), (2.6, 3.0, "jou")]),
    # Edited since: a word removed.
    (1.0, 3.0, "God zoekt jou",
     [(1.0, 1.4, "God"), (1.4, 1.6, "is"), (1.6, 1.9, "op"),
      (1.9, 2.2, "zoek"), (2.2, 2.6, "naar"), (2.6, 3.0, "jou")]),
    # A blank among the timings: whisper does that, and it must not shift the count.
    (1.0, 2.0, "Heer, hoor ons",
     [(1.0, 1.3, "Heer,"), (1.3, 1.3, " "), (1.3, 1.6, "hoor"), (1.6, 2.0, "ons")]),
    (5.0, 5.0, "geen tijd", None),                                   # nothing to divide
    (0.0, 1.0, "   ", None),                                         # nothing to say
]
