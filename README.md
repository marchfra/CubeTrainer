# CubeTrainer

A desktop app for speedcubing practice: a [cstimer](https://cstimer.net)-style timer
for full solves plus a [jperm](https://jperm.net)-style OLL/PLL algorithm trainer.
Built with Python and PySide6.

## Features

**Timer tab** (full solves)

- Spacebar timer: hold until the display turns green (0.3 s), release to start, press
  any key to stop. Modifier keys (e.g. Cmd+Tab) don't stop a solve; Esc cancels a hold.
- WCA inspection (the ⚙ options in the timer's bottom-right corner, on by default): the first press starts a 15 s
  countdown (or, with *Hold space to start inspection*, a hold until green does);
  starting after 15 s is +2, after 17 s DNF. Optional beeps at 8 s (one) and 12 s
  (two), like a judge's calls. Esc cancels inspection.
- WCA-style random-state scrambles (two-phase solver) with ◀ previous / ▶ next / Copy.
- Solves table (newest first) with rolling ao5 and ao12, plus a summary of current and
  best single / ao5 / ao12, solve count and session mean.
- Click a solve to see its details, change its penalty or delete it.
- **Time graph** under the timer: singles, ao5 and ao12 over the session (DNFs are
  gaps). Hover for a crosshair and the values at that solve. Follows the system's
  light/dark mode.
- **Sessions**, cstimer-style (the *Session ▾* button above the list): switch
  between sessions, or create, rename or delete one (deleting asks first and
  takes its solves with it; the last session can't be deleted). Statistics are
  per session, and the current session is remembered.
- Solves are saved automatically and survive restarts.

The small keyboard button in the timer's bottom-right corner (next to the ⚙
options) lists every key the timer and the
current page react to; the list is generated from the shortcuts as they are
registered, so it's always complete.

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
- **Edit** a case to use your own algorithm (checked as you type: it must solve
  the same case, but may start from another side, e.g. with a `y`, or add U
  turns), upload your own image, or rotate the image in quarter turns. The
  generated image follows your algorithm, so it shows the case the way you hold
  the cube. Your algorithm is used everywhere: list, hints and scrambles.
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
  statuses (a case must match both), and how likely each case is:
  - *Equal*: every case equally often.
  - *Realistic*: as often as in real solves. In PLL, H/Na/Nb are 1/72, E/Z 1/36
    and the rest 1/18; in OLL, 20 is 1/216, 1/21/55/56/57 are 1/108 and the rest
    1/54; in 2-look sets each case's odds are within its own look.
  - *Slowest first*: slow cases come up more often. Each case is rated on its
    last 12 solves across all the set's sessions: the weight is the square of
    the mean time (mistakes and DNFs left out), times 1 + the share of
    mistakes. A case twice as slow comes up four times as often. Cases with
    fewer than 3 timed solves count as the slowest, so new cases get practised.

  The button shows the odds in one word (*equal*, *realistic*, *slowest*) and
  keeps the same width whatever the filter. The filter is saved per set; if
  status changes leave nothing selected, the trainer falls back to all cases and
  the button shows *⚠ all N* (its tooltip explains).
- The solves table has a case column, and the solve dialog shows the case's name
  and image. The case is recognised from the scramble itself.
- Trainer solves are kept apart from full solves: each set's trainer has its own
  sessions, with the same *Session ▾* menu. The Learn tab's best/avg come from the
  set's current trainer session.
- **Hints:** press → to show the case image and the first move of its algorithm;
  each further → reveals one more move. The moves start from the case as the image
  shows it, so turn the U layer to match the image first. Brackets that group an
  algorithm into blocks, like `(R U R' U')`, are shown but don't count as steps. →
  works before and during a solve and never stops the timer. Faint dots after
  the moves show how many are still hidden. The number of hint steps used is
  saved with the solve.
- **Mistakes:** press M (or click *Mistake*, red while flagged) if you messed up. During a solve it
  flags that solve without stopping the timer; otherwise it toggles the flag of the
  last solve. The solve dialog has a *Mistake* checkbox too.
- The solves table shows flags: ✗ for a mistake, 💡n for n hint steps used.
- **Layout:** the top row holds the trainer's name and filter on the left, the
  scramble in the middle and *Mistake* and *← Full timer* on the
  right. Below it, the hint and the timer sit in the middle of the window,
  between the session's solves on the left and the per-case table on the right.
- **Per-case table:** n, avg, ao5 and err% (mistake rate) for every case trained,
  sortable by any column; hover a row for the case's best time and how often you
  used hints. Avg/ao5 leave out mistakes; hinted solves count. The summary's best
  and mean leave out mistakes too.
- The Learn tab shows each case's best and average trainer time.
- The same shortcuts work (⌘1/⌘2/⌘3, ⌘Z). Inspection is off by default; the
  trainer has its own ⚙ toggle, separate from the full timer's.

**Stats tab**

- Choose a *Source* (the full timer or a set's trainer), a *Session* (one, or all)
  and, for trainers, a *Case* (one, or all). Trainer statistics leave out
  mistakes.
- **Overview:** solves, DNFs, best, worst, mean, median, standard deviation,
  variation (CV: std / mean, lower is more consistent), 10th and 90th percentile.
- **Averages:** current and best ao5, ao12, ao50 and ao100.
- **Sub-X:** the share of solves under a time you choose.
- **Ex-Gaussian fit:** solve times are modelled as a normal distribution plus an
  exponential tail. μ is your typical clean solve, σ how consistent clean solves
  are, τ how big your tail of bad solves is; D (Kolmogorov-Smirnov) says how well
  the model fits (smaller is better).
- **Distribution** and **personal bests over time**, side by side: a histogram
  of your times with the fitted curve (hover for bar counts), and every new best
  single and best ao5, carried on to your latest solve (hover for the record and
  when it was set).
- **Learning curve:** your times by solve number with a fitted trend that levels
  off (an exponential learning curve), projected half as far again, with the
  plateau it approaches and how many solves it takes to halve the remaining gap.
  A trend is only reported when it's clearly bigger than random scatter.
- **Which cases to drill** (trainers, all cases): the slowest cases' mean time,
  mistake rate and hint use, side by side.
- The tab only computes and draws when you open it, and reopening it without new
  solves is instant. The scroll wheel scrolls the page even over the plots.

## Requirements

- [uv](https://docs.astral.sh/uv/); it installs Python 3.13 and all dependencies.
- macOS is the main target; Linux and Windows should work but aren't tested.

## Run

    uv run cubetrainer

## Data

Solves, case statuses and your case edits are stored in a SQLite database
(uploaded images are copied into an `images` folder next to it):

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
      inspection.py        inspection countdown, penalties and warnings
      sound.py             generated inspection beeps
      settings.py          key-value settings
      sessions.py          sessions (in memory; the database version is in db.py)
      solves.py            Solve, Penalty, SolveList
      stats.py             averages, means, bests, summary
      fits.py              ex-Gaussian fit (scipy)
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
        editing.py         checking a user's algorithm
        data/              bundled OLL and PLL cases and default algorithms
      ui/                  Qt widgets: main window, timer/trainer/learn pages, dialogs,
                           time graph (matplotlib)
    tests/                 pytest + pytest-qt

## License

[MIT](LICENSE)
