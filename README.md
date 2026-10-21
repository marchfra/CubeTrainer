# CubeTrainer

<!--toc:start-->

- [CubeTrainer](#cubetrainer)
  - [Install](#install)
  - [Using CubeTrainer](#using-cubetrainer)
  - [Development](#development)
  - [Licence](#licence)
  <!--toc:end-->

A desktop app for Rubik's cube practice. It combines a
[cstimer](https://cstimer.net)-style timer for full solves with a
[jperm](https://jperm.net)-style trainer for the OLL and PLL algorithms.

- **Timer:** WCA inspection with the judge's calls, random-state scrambles,
  sessions, rolling averages and a time graph.
- **Trainer:** drills OLL or PLL cases picked from your own selection, with
  step-by-step hints and mistake tracking.
- **Learn:** every case of 2-look OLL, 2-look PLL, full OLL and full PLL, with
  your learning status, your own algorithms and a notation guide.
- **Stats:** averages, distributions, personal bests over time and a learning
  curve.
- Three themes, in light or dark mode.

Everything is saved automatically on your computer; nothing is sent anywhere.

## Install

Download the source (the green _Code_ button → _Download ZIP_, or `git clone`),
open a terminal in its folder, then follow the steps for your system.

You need **Python 3.12 or newer** and a **C compiler** (the scramble solver,
[kociemba](https://pypi.org/project/kociemba/), is compiled when it's
installed).

<details>
<summary><strong>macOS</strong></summary>

### Requirements

- Python 3.12 or newer, from [python.org](https://www.python.org/downloads/) or
  Homebrew (`brew install python`). Check with `python3 --version`.
- Xcode Command Line Tools, for the C compiler:

  ```shell
  xcode-select --install
  ```

### Install and run

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install .
cubetrainer
```

If `python3` is older than 3.12, name the newer one in the first command, e.g.
`python3.12 -m venv .venv`. Once the environment is active, `python` is the
right one.

Next time, only activate the environment and start it:

```shell
source .venv/bin/activate
cubetrainer
```

With [uv](https://docs.astral.sh/uv/) instead, a single command installs and
starts it: `uv run cubetrainer`.

### Build a standalone app (optional)

This makes `CubeTrainer.app`, which runs without Python or a terminal. It takes
a minute or two and about 250 MB. In the activated environment:

```shell
pip install ".[app]"
python -m app_bundle.build_app --install
```

It goes into `/Applications`, so Spotlight, Launchpad and the Dock find it.
Installing also prepares the app's font cache once (up to half a minute), so the
app starts quickly. Without `--install`, the app is only built, into `dist/`.

To remove it:

```shell
python -m app_bundle.build_app --uninstall
```

The app keeps a copy of the code: after downloading a newer version, run the
`--install` command again.

### Your data

`~/Library/Application Support/CubeTrainer/`

</details>

<details>
<summary><strong>Windows</strong></summary>

### Requirements

- Python 3.12 or newer, from [python.org](https://www.python.org/downloads/)
  (tick _Add python.exe to PATH_ when installing). Check with `py --version`.
- Microsoft C++ Build Tools, for the C compiler: install
  [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
  and choose _Desktop development with C++_.

### Install and run

In PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
pip install .
cubetrainer
```

If PowerShell refuses to run the activation script, allow scripts for your user
once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Next time, only activate the environment and start it:

```powershell
.venv\Scripts\activate
cubetrainer
```

With [uv](https://docs.astral.sh/uv/) instead, a single command installs and
starts it: `uv run cubetrainer`.

### Build a standalone app (optional)

This makes a CubeTrainer program that runs without Python or a terminal. It
takes a minute or two and about 250 MB. In the activated environment:

```powershell
pip install ".[app]"
python -m app_bundle.build_app --install
```

It goes into `%LOCALAPPDATA%\Programs\CubeTrainer`, with a CubeTrainer shortcut
in the Start Menu. Installing also prepares the app's font cache once (up to
half a minute), so the app starts quickly. Without `--install`, the app is only
built, into `dist\`.

To remove it:

```powershell
python -m app_bundle.build_app --uninstall
```

The app keeps a copy of the code: after downloading a newer version, run the
`--install` command again.

> [!NOTE]
> The Windows app build hasn't been tested yet. Please report any problems.

### Your data

`%LOCALAPPDATA%\CubeTrainer\`

</details>

<details>
<summary><strong>Linux</strong></summary>

### Requirements

- Python 3.12 or newer with its `venv` module. Check with `python3 --version`.
- A C compiler and the Python headers. For example:
  - Debian and Ubuntu: `sudo apt install build-essential python3-dev python3-venv`
  - Fedora: `sudo dnf install gcc python3-devel`
  - Arch: `sudo pacman -S base-devel`

### Install and run

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install .
cubetrainer
```

If `python3` is older than 3.12, name the newer one in the first command, e.g.
`python3.12 -m venv .venv`. Once the environment is active, `python` is the
right one.

Next time, only activate the environment and start it:

```shell
source .venv/bin/activate
cubetrainer
```

With [uv](https://docs.astral.sh/uv/) instead, a single command installs and
starts it: `uv run cubetrainer`.

### Build a standalone app (optional)

This makes a CubeTrainer program that runs without Python or a terminal. It
takes a minute or two and about 250 MB. In the activated environment:

```shell
pip install ".[app]"
python -m app_bundle.build_app --install
```

It goes into `~/.local/share/cubetrainer`, with a launcher entry and an icon so
your desktop's app menu lists it. Installing also prepares the app's font cache
once (up to half a minute), so the app starts quickly. Without `--install`, the
app is only built, into `dist/`.

To remove it:

```shell
python -m app_bundle.build_app --uninstall
```

The app keeps a copy of the code: after downloading a newer version, run the
`--install` command again.

> [!NOTE]
> The Linux app build hasn't been tested yet. Please report any problems.

### Your data

`~/.local/share/CubeTrainer/` (or under `$XDG_DATA_HOME`, if you set it)

</details>

The data folder holds your solves, sessions, case statuses, your own algorithms
and images, and your settings. The installed app and `cubetrainer` share it. To
keep your times, back up this folder. To use a different folder, for example to
try things out without touching your real times, set `CUBETRAINER_DATA_DIR`
before starting:

```shell
CUBETRAINER_DATA_DIR=~/cubetrainer-test cubetrainer
```

(In PowerShell: `$env:CUBETRAINER_DATA_DIR = "$HOME\cubetrainer-test"`, then
`cubetrainer`.)

## Using CubeTrainer

Shortcuts below are written for macOS. On Windows and Linux, use
<kbd>Ctrl</kbd> where they say <kbd>⌘</kbd>.

### Timer

- Hold <kbd>Space</kbd> until the time turns green, then release to start.
  Press any key to stop.
- <kbd>Esc</kbd> cancels a hold.
- **Inspection** (on by default) follows the WCA rules. The first press of
  <kbd>Space</kbd> starts a 15-second countdown. Starting after 15 seconds is a
  +2 penalty, and after 17 seconds a DNF. Beeps at 8 and 12 seconds stand in for
  the judge's calls. <kbd>Esc</kbd> cancels inspection.
- Inspection and its beeps are set with the ⚙ button in the timer's corner.
- The arrows beside the scramble go back to the previous scramble or on to a
  new one. The copy button copies the scramble.
- Click a solve in the list to see it, change its penalty or delete it.
  <kbd>⌘</kbd> <kbd>1</kbd>, <kbd>⌘</kbd> <kbd>2</kbd> and <kbd>⌘</kbd>
  <kbd>3</kbd> mark the last solve OK, +2 or DNF. <kbd>⌘</kbd> <kbd>Z</kbd>
  deletes it, after asking.
- The graph under the timer shows your singles, ao5 and ao12. Hover over it to
  read the values.
- **Sessions** keep groups of solves apart, for example one per cube. Pick a
  session above the solves list, and use the ⋯ button beside it to create,
  rename or delete one. Statistics are per session.

Averages follow the WCA rules: the best and worst 5% are left out (the best and
worst solve in an ao5 or ao12), and a DNF counts as the slowest time.

### Learn

- Choose a set with the _Set_ picker: 2-look OLL, 2-look PLL, full OLL or full
  PLL. Each case shows its picture, name, algorithm, and your best and average
  trainer times.
- Click a case's picture to change its status: unlearned → learning → finished.
  The trainer can use the status to pick cases.
- **Edit** a case to use your own algorithm, your own picture, or to rotate the
  picture. Your algorithm is checked as you type: it must solve the same case,
  but may start from another angle. It's then used everywhere: in the list, the
  hints and the scrambles.
- **Notation** explains every move the algorithms use, with a picture of each.

### Trainer

Click _Train …_ in the Learn tab to train the chosen set. The Timer tab switches
to the trainer, and _← Full timer_ goes back.

- Each scramble sets up one case of the set. The rest of the cube is random, as
  in a real solve.
- The **case filter** (the _N cases_ button) chooses which cases come up, by
  group and status, and how often:
  - _Equal_: every case equally often.
  - _Realistic_: as often as in real solves.
  - _Slowest first_: your slow cases more often, and the ones you make
    mistakes on. Cases with few solves come up as if they were the slowest.
- **Hints:** press <kbd>→</kbd> to see the case's picture and the first move of
  its algorithm. Each further <kbd>→</kbd> shows one more move. Turn the top
  layer to match the picture first. Hints never stop the timer.
- **Mistakes:** press <kbd>M</kbd>, or click _Mistake_, when you mess up a solve.
  During a solve it flags that solve without stopping the timer; afterwards it
  flags (or unflags) the last solve. Mistakes are left out of your averages.
- The solves list marks mistakes with ✗ and hint use with 💡. The table on the
  right shows your count, average, ao5 and mistake rate for every case.
- Each set's trainer has its own sessions, separate from your full solves. The
  trainer has its own inspection setting, off by default.

### Stats

Pick what to look at: the full timer or a trainer, one session or all, and, for
a trainer, one case or all. You get:

- an **overview** (best, mean, median, consistency and more), and current and
  best averages of 5, 12, 50 and 100;
- the share of solves **under a time** you choose;
- the **distribution** of your times, with a fitted curve. Its μ is your typical
  clean solve, σ how consistent those are, and τ how big your tail of bad solves
  is;
- your **personal bests** over time;
- a **learning curve**: your trend, where it's heading and how fast you're
  improving;
- for a trainer, **which cases to drill**: your slowest cases, with their
  mistake rate and hint use.

### Settings

Open **Settings** with <kbd>⌘</kbd> <kbd>,</kbd> or _Settings…_ in the cog
menu. Choose a theme, with a live preview:

- _Calm_: soft rounded panels and a violet accent (the default);
- _Clean_: like a native Mac app;
- _Bold_: big type, and the timer as a coloured card.

Each theme comes in light and dark. Follow the system, or choose one.

### Keyboard shortcuts

| Shortcut                                                                          | Action                             |
| --------------------------------------------------------------------------------- | ---------------------------------- |
| <kbd>Space</kbd> (hold, then release)                                             | Start inspection, or the solve     |
| Any key                                                                           | Stop the timer                     |
| <kbd>Esc</kbd>                                                                    | Cancel a hold or inspection        |
| <kbd>⌘</kbd> <kbd>1</kbd> / <kbd>⌘</kbd> <kbd>2</kbd> / <kbd>⌘</kbd> <kbd>3</kbd> | Mark the last solve OK / +2 / DNF  |
| <kbd>⌘</kbd> <kbd>Z</kbd>                                                         | Delete the last solve (asks first) |
| <kbd>→</kbd>                                                                      | Trainer: show the next hint move   |
| <kbd>M</kbd>                                                                      | Trainer: flag a mistake            |
| <kbd>⌘</kbd> <kbd>,</kbd>                                                         | Open Settings                      |

On Windows and Linux, use <kbd>Ctrl</kbd> instead of <kbd>⌘</kbd>. The keyboard
button in the timer's corner (or _View → Keyboard Shortcuts_) lists the
shortcuts in the app.

## Development

Install [uv](https://docs.astral.sh/uv/), then run the checks (lint, format,
types and tests) from the project folder:

```shell
uv run ruff check && uv run ruff format --check && uv run ty check && uv run pytest
```

A pre-commit hook in `.githooks/` runs ruff and ty. Enable it once per clone
with `git config core.hooksPath .githooks`.

## Licence

CubeTrainer's source code is under the [MIT licence](LICENSE).

It uses [kociemba](https://github.com/muodov/kociemba), which is under the
GPLv2. A built app includes kociemba, so if you share a built app, you must do
so under the terms of the GPLv2.

The bundled fonts are under the SIL Open Font License:

- Geist and Geist Mono © Vercel ([licence](src/cubetrainer/ui/fonts/OFL-Geist.txt))
- Space Grotesk © The Space Grotesk Project Authors
  ([licence](src/cubetrainer/ui/fonts/OFL-SpaceGrotesk.txt))
- Space Mono © The Space Mono Project Authors
  ([licence](src/cubetrainer/ui/fonts/OFL-SpaceMono.txt))
