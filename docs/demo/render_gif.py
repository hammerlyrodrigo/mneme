"""Render an asciinema v2 .cast to an animated GIF with Pillow.

Supports what the mneme demo cast needs: printable text, \\r\\n, scrolling, and
SGR bold/colour for the prompt. Not a general terminal emulator.
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CAST = Path(sys.argv[1])
OUT = Path(sys.argv[2])
FONT = sys.argv[3] if len(sys.argv) > 3 else r"C:\Windows\Fonts\CascadiaMono.ttf"
SIZE = 15
PAD = 18

# Light terminal, matching the video's light IDE-accented look.
BG = (250, 250, 249)
FG = (36, 41, 46)
GREEN = (26, 127, 55)
CURSOR = (36, 41, 46)
BORDER = (222, 222, 220)

SGR = re.compile(r"\x1b\[([0-9;]*)m")

font = ImageFont.truetype(FONT, SIZE)
bold = font  # bold is faked by a 1px double draw, see render()
left, top, right, bottom = font.getbbox("M")
CW = right - left
CH = int(SIZE * 1.45)

header, *lines = CAST.read_text(encoding="utf-8").splitlines()
header = json.loads(header)
COLS, ROWS = header["width"], header["height"]
events = [json.loads(l) for l in lines if l.strip()]

W = COLS * CW + 2 * PAD
H = ROWS * CH + 2 * PAD


class Screen:
    def __init__(self):
        self.rows = [[]]  # each row: list of (char, style)
        self.style = {"bold": False, "fg": FG}

    def write(self, text):
        pos = 0
        for m in SGR.finditer(text):
            self._put(text[pos:m.start()])
            self._sgr(m.group(1))
            pos = m.end()
        self._put(text[pos:])

    def _sgr(self, params):
        for p in (params or "0").split(";"):
            if p in ("", "0"):
                self.style = {"bold": False, "fg": FG}
            elif p == "1":
                self.style["bold"] = True
            elif p == "32":
                self.style["fg"] = GREEN

    def _put(self, text):
        for ch in text:
            if ch == "\r":
                continue
            if ch == "\n":
                self.rows.append([])
                continue
            if len(self.rows[-1]) >= COLS:
                self.rows.append([])
            self.rows[-1].append((ch, dict(self.style)))

    def visible(self):
        return self.rows[-ROWS:]


def render(screen):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=BORDER)
    vis = screen.visible()
    for r, row in enumerate(vis):
        y = PAD + r * CH
        for c, (ch, st) in enumerate(row):
            x = PAD + c * CW
            f = bold if st["bold"] else font
            d.text((x, y), ch, font=f, fill=st["fg"])
            if st["bold"]:  # faux bold: redraw shifted 1px
                d.text((x + 1, y), ch, font=f, fill=st["fg"])
    # block cursor after the last character
    r = len(vis) - 1
    x = PAD + len(vis[r]) * CW
    y = PAD + r * CH
    d.rectangle([x, y + 2, x + CW - 1, y + CH - 3], fill=CURSOR)
    return im


screen = Screen()
frames, durations = [], []
prev_t = 0.0
for i, (t, kind, data) in enumerate(events):
    if kind != "o":
        continue
    screen.write(data)
    next_t = events[i + 1][0] if i + 1 < len(events) else t + 1.0
    dur = max(next_t - t, 0.02)
    frames.append(render(screen))
    durations.append(int(round(dur * 1000)))

# Open on the finished screen, so the GIF's first frame (what still-image
# previews and reduced-motion viewers show) is the output, not an empty prompt.
PREVIEW_MS = 1500
frames.insert(0, frames[-1])
durations.insert(0, PREVIEW_MS)

# Quantise once with a shared palette so frames don't flicker.
pal = frames[0].convert("P", palette=Image.ADAPTIVE, colors=64)
qframes = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
qframes[0].save(
    OUT,
    save_all=True,
    append_images=qframes[1:],
    duration=durations,
    loop=0,
    optimize=True,
)
total = sum(durations) / 1000
print(f"wrote {OUT}: {len(qframes)} frames, {total:.1f}s, {W}x{H}, {OUT.stat().st_size // 1024} KB")
