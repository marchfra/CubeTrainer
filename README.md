# CubeTrainer

A desktop app for speedcubing practice: a [cstimer](https://cstimer.net)-style timer
for full solves plus a [jperm](https://jperm.net)-style OLL/PLL algorithm trainer.
Built with Python and PySide6.

## Features

**Timer tab** (full solves)

- Spacebar timer: hold until the display turns green (0.3 s), release to start, press
  any key to stop. Modifier keys (e.g. Cmd+Tab) don't stop a solve; Esc cancels a hold.
- WCA-style random-state scrambles (two-phase solver) with ◀ previous / ▶ next / Copy.
- Solves table (newest first) with rolling ao5 and ao12, plus a summary of current and
  best single / ao5 / ao12, solve count and session mean.
- Click a solve to see its details, change its penalty or delete it.
- Solves are saved automatically and survive restarts.

| Shortcut | Action |
|---|---|
| ⌘1 / ⌘2 / ⌘3 | Mark the last solve OK / +2 / DNF |
| ⌘Z | Delete the last solve (asks first) |
| → | Trainer only: reveal the next hint step |
| M | Trainer only: flag the solve in progress (or the last one) as a mistake (the *Mistake* button turns red) |

Statistics follow cstimer and the WCA regulations: averages trim 5% (rounded up) from
each end, a DNF counts as the worst result, single times are truncated to hundredths
and averages and means are rounded to the nearest hundredth.

**Learn tab**

- Four sets, chosen with the *Set* picker (the tab opens on PLL): 2-look OLL (3 edge + 7 corner cases),
  2-look PLL (2 corner + 4 edge cases), full OLL (57) and full PLL (21), jperm-style: image, name, default algorithm (grouped into blocks with
  brackets), group, and best / average trainer times. The OLL numbering is
  cross-checked in the tests against the SpeedSolving wiki's algorithms.
- Case images are drawn from the algorithm itself (yellow top, green front). PLL
  images show the colours and arrows for how the pieces move (a final AUF in the
  algorithm is ignored); OLL images show which stickers are yellow, the rest grey.
  2-look images grey out what their look ignores (the corners when orienting
  edges, the edges when permuting corners).
- Click a case image to cycle its status: unlearned → learning → finished (shown as
  the image's background colour, and named on hover). Statuses are saved.

**Trainer** (Learn → *Train …* for the selected set)

- Opens in the Timer tab (← *Full timer* goes back). Each scramble sets up a case
  of the set, with random U turns around it. Whatever the case's algorithm doesn't
  solve is random, as in a real solve: OLL cases come with a random PLL, the edge
  look of 2-look OLL with random corners, the corner look of 2-look PLL with random
  edges. Scrambles are random-state style, so they don't
  give away the algorithm.
- **Case filter** (the *N cases · equal ▾* button): choose groups and learning
  statuses (a case must match both), and whether cases come up with equal
  probability or with their real-solve frequency (*realistic*: in PLL, H/Na/Nb are
  1/72, E/Z 1/36, the rest 1/18; in OLL, 20 is 1/216, 1/21/55/56/57 are 1/108, the
  rest 1/54; in 2-look sets each case's odds are within its own look). The filter is saved per set; if status changes
  leave nothing selected, the trainer falls back to all cases and says so.
- The solves table has a case column, and the solve dialog shows the case's name
  and image. The case is recognised from the scramble itself.
- Trainer solves are stored in their own session, separate from full solves.
- **Hints:** press → to show the case image and the first move of its algorithm;
  each further → reveals one more move. The moves start from the case as the image
  shows it, so turn the U layer to match the image first. Brackets that group an
  algorithm into blocks, like `(R U R' U')`, are shown but don't count as steps. →
  works before and during a solve and never stops the timer. The number of hint steps used is saved with the
  solve.
- **Mistakes:** press M (or click *Mistake*, red while flagged) if you messed up. During a solve it
  flags that solve without stopping the timer; otherwise it toggles the flag of the
  last solve. The solve dialog has a *Mistake* checkbox too.
- The solves table shows flags: ✗ for a mistake, 💡n for n hint steps used.
- **Per-case table:** n, best, avg, ao5, err% (mistake rate) and hint% for every
  case trained, sortable by any column. Best/avg/ao5 leave out mistakes; hinted
  solves count. The summary's best and mean leave out mistakes too.
- The Learn tab shows each case's best and average trainer time.
- The same shortcuts work (⌘1/⌘2/⌘3, ⌘Z). No inspection.

**Stats** tab: coming soon.

## Requirements

- [uv](https://docs.astral.sh/uv/); it installs Python 3.13 and all dependencies.
- macOS is the main target; Linux and Windows should work but aren't tested.

## Run

    uv run cubetrainer

## Data

Solves and case statuses are stored in a SQLite database:

- macOS: `~/Library/Application Support/CubeTrainer/cubetrainer.db`
- elsewhere: the platform's user data directory (via `platformdirs`), e.g.
  `~/.local/share/CubeTrainer/` on Linux

Set `CUBETRAINER_DATA_DIR` to use another directory, e.g. to experiment without
touching your real times:

    CUBETRAINER_DATA_DIR=/tmp/cubetrainer uv run cubetrainer

The schema is versioned and upgraded automatically on launch.

## Development

Run all checks (lint, format, types, tests):

    uv run ruff check && uv run ruff format --check && uv run ty check && uv run pytest

- Ruff extends the global config at `~/.config/ruff/ruff.toml`; `pyproject.toml` only
  adds test-specific ignores.
- Tests run headless (`QT_QPA_PLATFORM=offscreen`); set `QT_QPA_PLATFORM=cocoa` to run
  them against the real macOS display.

A pre-commit hook in `.githooks/` runs ruff and ty. Enable it once per clone:

    git config core.hooksPath .githooks

### Project layout

    src/cubetrainer/
      app.py               entry point
      timing.py            timer state machine (Qt-free)
      solves.py            Solve, Penalty, SolveList
      stats.py             averages, means, bests
      formatting.py        time / solve display strings
      scramble_history.py  ◀ / ▶ scramble history
      db.py                SQLite storage and migrations
      cube/
        model.py           sticker-level cube model and move notation
        scramble.py        random-state scrambles
        render.py          top-down last-layer images
      cases/
        catalog.py         case sets, cases, learning status
        recognition.py     identify OLL / PLL cases regardless of AUF
        trainer.py         case scrambles and recognising them
        filters.py         case filter and case probabilities
        data/              bundled OLL and PLL cases and default algorithms
      ui/                  Qt widgets: main window, timer/trainer/learn pages, dialogs
    tests/                 pytest + pytest-qt

## License

[MIT](LICENSE)
