"""Build an asciinema v2 .cast from captured mneme output.

The command output is real (captured from `mneme` in a scratch repo); only the
prompt, the typing cadence and the pauses are scripted, so the clip is short,
deterministic and re-renderable.
"""
import json
import sys
from pathlib import Path

CAP = Path(sys.argv[1])
OUT = Path(sys.argv[2])
COLS, ROWS = 80, 24

PROMPT = "\x1b[1;32m$\x1b[0m "
KEY = 0.045       # seconds per typed character
AFTER_ENTER = 0.25
READ = {          # how long the viewer gets to read each result
    "brief": 3.5,
    "recall": 2.5,
    "show": 3.5,
}
STEPS = [
    ("mneme brief", "brief"),
    ("mneme recall --path src/auth/", "recall"),
    ("mneme show D-d40a40", "show"),
]

t = 0.0
events = []


def emit(text, dt):
    global t
    t += dt
    events.append([round(t, 3), "o", text])


emit(PROMPT, 0.6)
for cmd, name in STEPS:
    for ch in cmd:
        emit(ch, KEY)
    emit("\r\n", 0.5)
    body = (CAP / f"{name}.txt").read_text(encoding="utf-8").rstrip("\n")
    emit(body.replace("\n", "\r\n") + "\r\n", AFTER_ENTER)
    emit("\r\n" + PROMPT, READ[name])

emit("", 1.0)  # hold the last frame before looping

header = {
    "version": 2,
    "width": COLS,
    "height": ROWS,
    "timestamp": 0,
    "env": {"SHELL": "/bin/sh", "TERM": "xterm-256color"},
    "title": "mneme: brief, recall, show",
}
with OUT.open("w", encoding="utf-8", newline="\n") as f:
    f.write(json.dumps(header) + "\n")
    for ev in events:
        f.write(json.dumps(ev) + "\n")
print(f"wrote {OUT}: {len(events)} events, {t:.1f}s")
