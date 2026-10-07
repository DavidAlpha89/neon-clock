#!/usr/bin/env python3
"""neon_clock.py -- a neon analog clock for the terminal.

Keys:  q / Esc  quit
       s       toggle smooth sweep vs. ticking second hand
       d       toggle the digital readout
"""

import curses
import locale
import math
import os
from datetime import datetime

# Some shells (or apps that spawn them) export TERM=dumb or unset TERM,
# which makes curses.setupterm() abort. Fall back to a capable entry.
if os.environ.get("TERM") in (None, "", "dumb", "unknown"):
    os.environ["TERM"] = "xterm-256color"

# ---------------------------------------------------------------- palette --

PALETTE = {
    "ring_core": (0, 255, 240),    # neon tube ring
    "ring_glow": (0, 90, 110),     # halo around the ring
    "tick":      (170, 255, 255),
    "num":       (255, 140, 215),
    "hour_core": (255, 45, 160),   # magenta hour hand
    "hour_glow": (120, 0, 70),
    "min_core":  (0, 225, 255),    # cyan minute hand
    "min_glow":  (0, 65, 115),
    "sec_core":  (235, 255, 60),   # acid-yellow second hand
    "sec_glow":  (95, 115, 0),
    "dot":       (255, 255, 255),  # center pivot
    "digit":     (0, 255, 205),    # digital readout
    "digit_dim": (0, 115, 95),
}

BOLD = {"ring_core", "tick", "num", "hour_core", "min_core", "sec_core",
        "dot", "digit"}

ANSI_FALLBACK = {
    "ring_core": curses.COLOR_CYAN,
    "ring_glow": curses.COLOR_CYAN,
    "tick":      curses.COLOR_WHITE,
    "num":       curses.COLOR_MAGENTA,
    "hour_core": curses.COLOR_MAGENTA,
    "hour_glow": curses.COLOR_MAGENTA,
    "min_core":  curses.COLOR_CYAN,
    "min_glow":  curses.COLOR_CYAN,
    "sec_core":  curses.COLOR_YELLOW,
    "sec_glow":  curses.COLOR_YELLOW,
    "dot":       curses.COLOR_WHITE,
    "digit":     curses.COLOR_CYAN,
    "digit_dim": curses.COLOR_CYAN,
}

# Draw order priorities: higher wins the cell.
P_GLOW, P_CORE, P_FACE, P_HAND_GLOW, P_HAND, P_PIVOT = 1, 2, 3, 4, 5, 6

TWO_PI = 2.0 * math.pi


def build_attrs():
    """Map palette names -> curses attributes (truecolor if available)."""
    attrs = {}
    try:
        curses.start_color()
        curses.use_default_colors()
        truecolor = curses.can_change_color() and curses.COLORS >= 32
    except curses.error:
        truecolor = False

    for i, (name, rgb) in enumerate(PALETTE.items()):
        attr = None
        if truecolor:
            idx = 16 + i
            if idx < curses.COLORS:
                try:
                    r, g, b = (round(c * 1000 / 255) for c in rgb)
                    curses.init_color(idx, r, g, b)
                    curses.init_pair(i + 1, idx, -1)
                    attr = curses.color_pair(i + 1)
                except curses.error:
                    attr = None
        if attr is None:
            fg = ANSI_FALLBACK.get(name, curses.COLOR_WHITE)
            try:
                curses.init_pair(i + 1, fg, -1)
                attr = curses.color_pair(i + 1)
            except curses.error:
                attr = 0
        if name in BOLD:
            attr |= curses.A_BOLD
        attrs[name] = attr
    return attrs


# ---------------------------------------------------------------- drawing --

def clock_geometry(W, H, digital):
    reserve = 3 if digital else 1
    rx = min((W - 4) / 2.0, (H - 2 - reserve) / 2.0 / 0.52)
    rx = max(rx, 1.0)
    ry = 0.52 * rx                      # chars are ~2x taller than wide
    cx = (W - 1) / 2.0
    cy = (H - reserve - 1) / 2.0
    return cx, cy, rx, ry


def _put(frame, W, H, x, y, ch, attr, prio):
    x = int(math.floor(x + 0.5))          # not round() -- banker's rounding
    y = int(math.floor(y + 0.5))          # collapses adjacent .5 cells
    if not (0 <= x < W and 0 <= y < H):
        return
    cur = frame[y][x]
    if cur is None or prio >= cur[2]:
        frame[y][x] = (ch, attr, prio)


def _draw_ring(frame, W, H, cx, cy, rx, ry, A):
    core_w = 0.55 / rx
    glow_w = 1.7 / rx
    y0 = int(cy - ry - 2)
    y1 = int(cy + ry + 2)
    x0 = int(cx - rx - 2)
    x1 = int(cx + rx + 2)
    for y in range(max(0, y0), min(H, y1 + 1)):
        for x in range(max(0, x0), min(W, x1 + 1)):
            d = math.hypot((x - cx) / rx, (y - cy) / ry)
            if abs(d - 1.0) < core_w:
                _put(frame, W, H, x, y, "\u25cf", A["ring_core"], P_CORE)
            elif abs(d - 1.0) < glow_w:
                _put(frame, W, H, x, y, "\u00b0", A["ring_glow"], P_GLOW)


def _draw_ticks(frame, W, H, cx, cy, rx, ry, A, big):
    for m in range(60):
        a = m * TWO_PI / 60
        sa, ca = math.sin(a), math.cos(a)
        if big and m % 5 == 0:
            for r in (0.80, 0.86, 0.92):
                _put(frame, W, H, cx + sa * rx * r, cy - ca * ry * r,
                     "\u2588", A["tick"], P_FACE)
        elif not big:
            r = 0.86 if m % 5 == 0 else 0.90
            ch = "\u2588" if m % 5 == 0 else "\u00b7"
            _put(frame, W, H, cx + sa * rx * r, cy - ca * ry * r,
                 ch, A["tick"], P_FACE)


def _draw_numbers(frame, W, H, cx, cy, rx, ry, A, all_12):
    nums = range(1, 13) if all_12 else (12, 3, 6, 9)
    for n in nums:
        a = n * TWO_PI / 12
        s = str(n)
        x = cx + math.sin(a) * rx * 0.62 - len(s) / 2
        y = cy - math.cos(a) * ry * 0.62 - 0.5
        for i, ch in enumerate(s):
            _put(frame, W, H, x + i, y, ch, A["num"], P_FACE)


def _draw_hand(frame, W, H, cx, cy, rx, ry, ang, length, A, core_key,
               glow_key, tail=0.0, core_ch="\u2588"):
    sa, ca = math.sin(ang), math.cos(ang)
    span = length + tail
    steps = max(2, int(span * rx / 0.4))
    pts = []
    for i in range(steps + 1):
        t = -tail + span * i / steps
        pts.append((cx + sa * rx * t, cy - ca * ry * t))
    for x, y in pts:                              # glow halo under the core
        for gx, gy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            _put(frame, W, H, gx, gy, "\u2592", A[glow_key], P_HAND_GLOW)
    for x, y in pts:
        _put(frame, W, H, x, y, core_ch, A[core_key], P_HAND)


def _draw_digital(frame, W, H, cx, cy, ry, now, A):
    y = min(int(cy + ry) + 2, H - 1)
    s = "%02d:%02d:%02d" % (now.hour, now.minute, now.second)
    colon_on = now.second % 2 == 0
    x = cx - len(s) / 2
    for i, ch in enumerate(s):
        key = "digit" if ch != ":" or colon_on else "digit_dim"
        _put(frame, W, H, x + i, y, ch, A[key], P_HAND)


def render(scr, A, now, smooth=True, digital=True):
    H, W = scr.getmaxyx()
    frame = [[None] * W for _ in range(H)]

    if W < 14 or H < 9:
        msg = "terminal too small"
        scr.erase()
        if W >= len(msg) and H > 1:
            try:
                scr.addstr(H // 2, max(0, (W - len(msg)) // 2), msg,
                           curses.A_BOLD)
            except curses.error:
                pass
        scr.refresh()
        return

    cx, cy, rx, ry = clock_geometry(W, H, digital)

    _draw_ring(frame, W, H, cx, cy, rx, ry, A)
    big = rx >= 16
    _draw_ticks(frame, W, H, cx, cy, rx, ry, A, big)
    _draw_numbers(frame, W, H, cx, cy, rx, ry, A, all_12=rx >= 20)

    if smooth:
        sec = now.second + now.microsecond / 1e6
    else:
        sec = now.second
    sec_a = sec / 60.0 * TWO_PI
    min_a = (now.minute + sec / 60.0) / 60.0 * TWO_PI
    hour_a = (now.hour % 12 + now.minute / 60.0) / 12.0 * TWO_PI

    _draw_hand(frame, W, H, cx, cy, rx, ry, hour_a, 0.52, A,
               "hour_core", "hour_glow")
    _draw_hand(frame, W, H, cx, cy, rx, ry, min_a, 0.78, A,
               "min_core", "min_glow")
    _draw_hand(frame, W, H, cx, cy, rx, ry, sec_a, 0.88, A,
               "sec_core", "sec_glow", core_ch="\u00b7")

    _put(frame, W, H, cx, cy, "\u25c9", A["dot"], P_PIVOT)

    if digital:
        _draw_digital(frame, W, H, cx, cy, ry, now, A)

    scr.erase()
    for y in range(H):
        x = 0
        while x < W:
            cell = frame[y][x]
            if cell is None:
                x += 1
                continue
            s, attr = cell[0], cell[1]
            xn = x + 1
            while xn < W:
                c2 = frame[y][xn]
                if c2 is None or c2[1] != attr:
                    break
                s += c2[0]
                xn += 1
            try:
                scr.addstr(y, x, s, attr)
            except curses.error:
                pass  # bottom-right corner cell is unwritable
            x = xn
    scr.refresh()


def main(stdscr):
    locale.setlocale(locale.LC_ALL, "")
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(50)
    A = build_attrs()
    smooth, digital = True, True
    while True:
        render(stdscr, A, datetime.now(), smooth, digital)
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            break
        if key in (ord("s"), ord("S")):
            smooth = not smooth
        elif key in (ord("d"), ord("D")):
            digital = not digital


if __name__ == "__main__":
    curses.wrapper(main)
