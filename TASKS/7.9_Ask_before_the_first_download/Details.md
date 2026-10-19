# 7.9 Ask before the first download

On a stranger's first run the bootstrap fetches `pip` and `ezpkg`
before anybody is asked anything, and `pip install`'s own lines
(`Looking in links`, `Processing`, `Installing collected packages`,
`Successfully installed`) are the first thing they see, with nothing
to explain them (Wayne, 2026-10-16: "totally confusing").

## The Design (Wayne, 2026-10-19)

`EZPkg` has two customers, and both should find it extremely easy.
The end user is asked one question per program; the developer is
never asked anything.  Everything the developer wants to change is
written in a file, never answered at a prompt, and there are no
environment variables to mistype.  This replaces the questions built
during the UX review (`ux01`-`ux27`), which went down the wrong path
for a while.

### The Two Modes

* **Developer mode** is a file `prog.py.toml` beside `prog.py` (an
  empty one will do: `touch prog.py.toml`).  Without it, `prog.py` is an end user's.
  Nothing else decides the mode: no guessing from edits, and no "Are
  you working on `prog.py`?".
* **An empty `prog.py.toml` is an invitation.**  When the file is
  empty (or only blank lines), `ezpkg` fills it with the settings,
  every one commented out at its default, and says so in one line.
  The developer turns things on and off by editing the file; `ezpkg`
  never writes it again.

  ```toml
  # prog.py.toml: EZPkg settings for prog.py.  Having this file means
  # prog.py is being developed.  Remove a `#` to change a setting.
  # https://pypi.org/project/ezpkg/

  # Keep `dependencies` matching the imports.
  # auto-dependencies = true

  # Print one line for each change made to `dependencies`.
  # report = false

  # Make a release: runs once each time this value changes.
  # release = "1.0.0"

  # What a release builds: "zipapp" (prog-X.Y.Z.pyz), "uv" (prog-X.Y.Z-uv.py).
  # exports = ["zipapp", "uv"]

  # At a release, give each bare entry in `dependencies` a version range.
  # ranges = false
  ```

* Every setting is checked, so a typo stops the run:

  ```
  prog.py.toml line 3: unknown setting `relase` (did you mean `release`?)
  ```

* The settings, all optional (the template above shows each):

  | Setting             | Default | Meaning                                     |
  |---------------------|---------|---------------------------------------------|
  | `auto-dependencies` | `true`  | Keep `dependencies` matching the imports.   |
  | `report`            | `false` | Print one line per change to `dependencies`. |
  | `release`           | none    | `"X.Y.Z"`: make a release (below).          |
  | `exports`           | `[]`    | What a release builds: `"zipapp"`, `"uv"`.  |
  | `ranges`            | `false` | At a release, give bare entries ranges.     |

### The End User (no `prog.py.toml`)

* **One question per program** (identified by its path), on its
  first run: `ux01`'s paragraph, then

  ```
  Retain `~/.ezpkg` and run `prog.py`? [y=>Yes|n=>No|?=>Explain]:
  ```

  `?` shows the short list of packages with their summaries.
* **A yes covers this program and its later versions.**  If the author
  sends a new `prog.py` that needs more packages, they are downloaded
  and run silently, as Ubuntu updates are.
* **After the first yes**, the list of stored packages and the line
  `` `ezpkg` (https://pypi.org/project/ezpkg/) manages `~/.ezpkg`. ``
  Later downloads print nothing.
* **A no** (or Control-C before Enter) removes what was downloaded
  (all of `~/.ezpkg` on a first run), and `prog.py` does not run.
* **Once it works, it keeps working.**  A `prog.py` that was emailed
  never changes by itself: its versions are frozen by its date, and it
  never asks about updates.
* **Never an edit.**  `ezpkg` never changes an end user's `prog.py`.
  If the author forgot a package, Python's own `ImportError` says so.

### The Developer (`prog.py.toml` present)

* **No prompts at all**, not even the first download.  Developer mode
  can be as chatty as it needs to be when something goes wrong.
* **`dependencies` follows the imports** (with `auto-dependencies`
  on), silently:
  * A new import gets an entry, named from this Python's metadata, a
    list of known names, or the module's own name, checked to exist
    and to provide the module, with a range such as `>=1.2.3,<2`.  If
    no such package exists, one line says so and Python's
    `ImportError` follows.
  * Entries follow the order of the first imports.
  * The author's `# type: ignore` comment is copied to the new import,
    if the others carry one.
  * The program restarts after the edit, so line numbers in any
    traceback are right.
  * An entry whose import was removed is removed.  Its packages stay in
    `~/.ezpkg` until `cull` ages them out (or `remove.py`).  If the
    import was removed by mistake, putting it back brings the entry
    back.
* **Needed, but not imported.**  An entry the developer adds by hand
  that no import explains is kept, and marked with a comment:
  * a module named in a string (`importlib.import_module("yaml")`)
    counts as an import, so it needs no mark;
  * an optional extra of another entry is marked `# Needed by pandas
    (excel)`;
  * anything else is marked `# Needed, but not imported`, for the
    developer to reword (`# Needed by matplotlib`).

  An entry whose comment starts `# Needed` is never removed.
  `ezpkg`'s record of the program's last imports tells an entry added
  by hand from one whose import was just removed.
* **`auto-dependencies = false`**: nothing is edited and nothing is
  said; keeping `dependencies` right is the developer's business.
* **Versions never change by themselves.**  The approvals file
  (`prog.ezpkg`, written by `ezpkg`) is kept up to date, and changes
  only when `dependencies` does.  The `exclude-newer` date is stamped
  on the first run and moves only on an upgrade.  So the developer
  runs exactly what the end user will get.
* **Upgrade: delete the `exclude-newer` line.**  The next run fetches
  the newest versions and stamps a new date.
* **A package newer than the date** cannot be fetched under it, and
  the end user's copy would fail the same way, so the run stops:

  ```
  prog.py line 14 imports `tabulate`, but no release of it existed before
  the date prog.py's versions are frozen at (line 9, 2025-03-01).  To
  upgrade everything to today's versions, delete line 9 and run prog.py
  again.
  ```

* **A newer bootstrap.**  When `prog.py` carries an older bootstrap
  than the running `ezpkg` knows (such as `nopip6` when `nopip7` is
  current), a developer run says so once per newer bootstrap, with the
  lines to replace and where the new text is.  Actively maintained
  programs move forward with the bootstrap; unmaintained ones keep the
  old one, which goes on working (`T.eui`, `T.reb`).

* **Release: `release = "X.Y.Z"`.**  The first run whose value differs
  from the last release (recorded as `# Released: X.Y.Z` in
  `prog.ezpkg`) makes the release, once:
  1. reconciles `dependencies`;
  2. checks that the bootstrap is unedited and current: an older one
     is refused, with the offer to update it (Wayne);
  3. checks the imports;
  4. gives bare entries ranges, if `ranges = true`;
  5. freezes the approvals;
  6. builds what `exports` lists, named by version
     (`prog-1.0.0.pyz`, `prog-1.0.0-uv.py`);
  7. records `# Released: X.Y.Z`, prints what it built, and stops
     without running the program.

  The next release is just the next number.

### What Does Not Change

* The bootstrap (`nopip7`): no new bootstrap is needed.
* `ezpkg` switching to the version Part 1 asks for (`T.eui`), the
  refusal of an edited bootstrap (`T.reb`), the restart, `remove.py`
  and `cull`.

### What Goes

* End-user and developer mode as guessed from edits, "Are you working
  on `prog.py`?", `Update them? [y|n|i|a]`, the per-item questions,
  Manual and Auto, `k`, the changes display, the breaking-import
  messages.
* The download prompt's `a` and `s` answers, and `FOREVER_APPROVE`.
* `EZPKG_APPROVE` and `EZPKG_EXPORT`.  `EZPKG_BOOTSTRAP=check` becomes
  part of a release; `EZPKG_BOOTSTRAP=unchecked` stays for the test
  harness only.  (`EZPKG_SWITCHED`, `EZPKG_RESTARTED` and
  `EZPKG_PYTHONPATH` stay: they carry state from `ezpkg` to its own
  re-run of the program, and nobody sets them by hand.)

### The Order of Work

1. Wayne reads this, and we iterate; then Wayne commits.
2. The code, with tests, in slices: `prog.py.toml` and the two modes;
   the end user's path; silent reconciliation and the marks; frozen
   versions and the upgrade; the release.
3. UX testing: `ux/drive.py`'s steps rewritten for the new design.
4. `README.md`, with a new section for developers.
5. Iterate.

## Lessons From the Earlier Design

The questions built during the UX review (`ux01`-`ux27`) are gone, but
these lessons carry over.  `git` has the rest.

* **Downloading silently is fine; running downloaded code without
  asking is not.**  The bootstrap asks nothing, since the author put it
  there.
* **Put the onus on the author.**  Name the program, and promise
  nothing `ezpkg` cannot know ("chosen by its author", not "the correct
  software").
* **Hide nothing.**  On a first run, `pip` and `ezpkg` are listed with
  the other packages, since a no removes them too.
* **If in doubt, delete.**  Anything deleted is simply fetched again.
* **Say where, so it can be undone**: `~/.ezpkg` (PowerShell
  understands `~`), but the full path on Windows, since `cmd.exe` and
  Explorer do not.  Undoing is `python3 ~/.ezpkg/remove.py`, never `rm
  -rf`.
* **Ask once.**  No "Really?" after an answer; one question, then a line
  saying how to undo it.
* **Control-C before Enter is a no**; after Enter, the answer stands.
  No answer in 5 minutes is a no, and a set `CI` means nobody is there
  to ask (`I.owenabd`).
* **The bootstrap captures `pip`'s output** and hands it to `EZPkg`
  (`nopip7`, `m.EZPkg(pip=n)`), so the first thing a stranger sees is
  `ezpkg`'s question, not `pip`'s lines, and a failed install keeps
  `pip`'s reason.
* **When standard error is not a terminal**, the question and its
  answer are copied to it, so redirected output tells the whole story.
* **Restart after every edit** to `prog.py`, since Python compiled the
  old file and a traceback would name new lines by old numbers.
* **Style**: no `ezpkg:` prefix on these lines; backticks around names;
  `|` between choices and `]:` after them (`/n` reads as a newline);
  paragraphs wrapped to the narrower of the terminal and 79 columns;
  "N package(s)" is literal.
* **Not settled**: a second program starting at the same moment as a
  first run that is then declined.
