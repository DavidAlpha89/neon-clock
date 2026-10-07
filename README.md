# neon-clock

A neon analog clock for the terminal — pure Python stdlib + `curses`, no
dependencies, no network. Born on a Pi 5 in October 2026 as a test of offline
coding.

![python](https://img.shields.io/badge/python-3.9%2B-blue)
![deps](https://img.shields.io/badge/dependencies-none-brightgreen)
![platform](https://img.shields.io/badge/platform-linux%20%7C%20macOS-lightgrey)

## Run

```bash
python3 neon_clock.py
```

## Features

- Elliptical neon tube ring with a bright core and a dim halo (compensates for
  terminal cells being ~2× taller than wide)
- Three glowing hands — magenta hour, cyan minute, acid-yellow second — over a
  white pivot
- Hour ticks and numerals that densify as the window grows (12/3/6/9, then all
  twelve)
- Blinking-colon digital readout
- Truecolor RGB on capable terminals, graceful 8-color ANSI fallback
- Adapts to any terminal size; resizes live

## Keys

| Key       | Action                          |
|-----------|---------------------------------|
| `q` / Esc | quit                            |
| `s`       | smooth sweep ↔ ticking seconds  |
| `d`       | toggle digital readout          |

## How it renders

Each frame is composed into a cell-priority buffer: glows draw first (low
priority), hand cores overwrite them, the pivot wins ties. Cells are then
coalesced into maximal same-attribute runs and flushed with a single `addstr`
per run, which keeps redraws flicker-free at ~20 fps.

Angles are computed from `datetime.now()` including microseconds, so the sweep
mode gives a genuinely smooth second hand.

## The terminfo footnote

If you run this over SSH from [Ghostty](https://ghostty.org) on macOS and see

```
_curses.error: setupterm: could not find terminal
```

the remote machine lacks the `xterm-ghostty` terminfo entry (Debian's
`ncurses-term` predates Ghostty). One-time fix, run from inside Ghostty:

```bash
infocmp -x xterm-ghostty | ssh user@host 'mkdir -p ~/.terminfo && tic -x -'
```

## Verification

- 180-combo mock-screen harness (terminal sizes 10×9 … 200×50 × clock times ×
  toggles): zero crashes, zero out-of-bounds writes
- live pty runs under `xterm-256color`, `xterm-ghostty`, and `TERM=dumb`

## License

MIT — do with it what you will.
