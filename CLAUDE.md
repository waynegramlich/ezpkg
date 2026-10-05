# Working agreement for this project

<!-- ----------------------------79 characters----------------------------- -->

## Version control: two repositories, two purposes

This project deliberately uses **both** mercurial and git over the same
working directory.  They serve different purposes and must not be confused:

| Repo | Purpose | Who commits | How often |
|------|---------|-------------|-----------|
| `.hg` | Undo.  A safety net. | Claude, freely | Constantly |
| `.git` | History.  The record. | **Wayne only, by hand** | Rarely |

Each ignores the other: `.hgignore` excludes `.git/`, `.gitignore`
excludes `.hg/`.

The division is absolute in both directions: Claude never changes the
git repository, and Wayne never runs `hg`.  Wayne includes `CLAUDE.md`
in every git commit, so the rules stay versioned alongside the work
they govern.

### Rules for Claude

1. **Checkpoint into mercurial often**, especially before any edit that
   would be annoying to reconstruct, and after any step that works.
   `hg commit -A -m "checkpoint: <what was just tried>"`.  These messages
   are notes to our future selves, not publishable history; they do not
   need to be good.

2. **Claude never changes the git repository.**  Not `commit`, not
   `add`, not `amend`, not `init`, not `stash`, not `checkout` or
   `restore`, not a branch or a tag.  Wayne owns every git write, and
   `git commit` above all, because the point is a git log free of the
   checkpoint traffic that mercurial carries.  When a chunk of work
   looks finished, say so and stop there; do not offer to commit it,
   and do not stage anything in preparation.

   Reading is allowed, as of 2026-10-01: `git status`, `git log`,
   `git diff` and `git show` are fine, since they change nothing.

   This rule exists because Claude previously made three unrequested
   commits while setting up the repository, which is exactly the
   cluttered log this project was organized to avoid.

3. **Claude does not write commit messages at all.**  When a chunk of
   work looks finished, Claude says so -- "this looks like a commit
   point" -- and stops.  Wayne writes the message himself, by hand.

   An earlier version of this rule had Claude drafting messages into a
   `.git_commit.md` file for Wayne to review.  Wayne never used them,
   so the file and the rule were retired on 2026-09-23.  Do not
   recreate it.  Wayne is the author of record for every git commit,
   and no generated attribution line -- `Co-Authored-By:` or any
   other -- appears in one.

4. **Every git commit message must stand on its own** in `git log`.  One
   commit per meaningful unit of work.  No "wip", no "fix typo", no
   "checkpoint", no chains of commits that only make sense in order.  If
   the work took twelve mercurial checkpoints, it still lands in git as
   one commit.

5. **To undo, reach for mercurial**, not git.  `hg log`, then
   `hg revert -r <rev> <file>` or `hg update -r <rev>`.  Checkpoint
   freely and often -- being able to undo is really, really important
   here, and mercurial is the only tool Claude has for it.

6. **`LOGBOOK.md` is this project's running record** -- purpose,
   problem statement, prior art, findings and decisions.  Wayne and
   Claude maintain it jointly.

   The file is organised as numbered tasks, and a closed task is marked
   twice.  A marker is the text `(CLOSED ` followed by a real date and
   a closing parenthesis; the template spelled out as letters is prose
   about the convention rather than a marker, which is what lets Task 4
   quote it without failing its own test.  A task is closed when all
   three of these hold:

   * The heading carries a marker.
   * The last non-blank line of the task is that same marker, carrying
     the same date.
   * The summary section holds at least one line of text besides that
     closing line.  A `...` placeholder does not count.

   So a task holds either no markers or exactly two with matching
   dates, and anything else is a mistake to point out.  The usual one
   is a dated heading with no closing line, where the heading claims
   what the rest of the task does not support.

   A closed task is settled: do not edit it, propose the change and let
   Wayne make the call.  An annotation goes above the closing line,
   never after it, so that the line stays last.

   An open task can be edited normally, and may put its summary heading
   in early and accumulate working material underneath it -- a chart
   that gets updated in place, a running list of findings.  That is not
   a mistake.  The material is provisional, and writing it closes
   nothing.  This arrangement replaced the `FENCE:` marker on
   2026-09-24, and the two-marker rule replaced a one-marker version of
   it on 2026-09-25.

   A task divides into numbered **steps**, written `* Step T.S:` with a
   blank line before each, and a step's findings into sub-items written
   `  * T.S.I - `.  Steps are mini-tasks and **do not close**: only
   tasks do.  A step needs no marker, no summary and no date, and the
   steps of an open task are listed highest priority first.  A step may
   also earn a `### Step T.S:` section after the list, for what was
   learned rather than what was intended.

   The point is to stop settled questions from being reopened over and
   over.

7. **Issues live in `LOGBOOK.md` under `## Issues`**, and that
   section's own preamble is the authority on how they work.  The
   parts that are easy to get wrong:

   * Each issue is named by an identifier such as `0whwnn` -- a
     priority digit, then the first letter of each word of its title,
     lower cased, with `a`, `an`, `the` and `of` dropped.  Punctuation
     is dropped and a hyphenated word counts once.  Two titles that
     collide take a trailing digit.
   * Changing an issue's priority or its title changes its
     identifier.  Updating every reference to the old name in the
     same pass is Claude's job, and is not a reason to leave an issue
     mis-prioritised.
   * A resolved issue moves to `### Closed Issues` with the date it
     was closed, and is purged later, once every reference to it is
     gone.  Rejected ones live in `### Rejected Issues` and are not
     purged by age, because their purpose is to stop the same idea
     coming back.

### Why

A log where every entry is meaningful is worth more than a log that
records everything that happened.  Mercurial already records everything
that happened.

## Talking to Wayne

Number the items of any list in a reply, so that Wayne can answer them
by number.  Asked for on 2026-10-04.

## Tasks under `TASKS/`, on trial

From 2026-10-04 Wayne is trying a new task system alongside the
numbered tasks in `LOGBOOK.md`, which rule 6 still governs.  It is
described by the rules imported below, and `./task help` lists its
commands.  Wayne writes each task's `Details.md`; Claude keeps the
`Context.md` of every open task current, so that a fresh session can
pick the work up from it.  `RULES/task.py` lives in another repository,
so fixes to it are Claude's to make and Wayne's to commit.

@RULES/Task_Tracking_Rules.md
@TASKS/Startup

## Who owns which file

* `CLAUDE.md` is Claude's.  Wayne does not read it, so keeping it
  accurate is Claude's job, done without asking; a rule Wayne states
  in conversation belongs here.
* `claude_notes.md` and `python_with_markdown.md` are Wayne's.  Both
  are symbolic links into other directories with git repositories of
  their own.  Claude reads them and never edits them.
* `README.md` is Wayne's, and being rewritten by him.  Suggestions go
  to him, or into an HTML comment addressed to him, rather than into
  the text.  One standing exception, from 2026-10-02: when his edits
  leave a line over 79 columns, rewrap it without asking.  The pasted
  bootstrap's longest line is the only line allowed over, because the
  bootstrap must be copied exactly.  And from the same date: `README.md`
  describes what the code actually does.  A change to the code that
  alters anything the README says is not finished until the README
  says it too, and a README claim the code does not back is a mistake
  to fix, or to raise with Wayne if fixing it means changing the code.
* `LOGBOOK.md` is joint, as described above.

## The code, and how to run it

Six files, and it matters which is which:

* `bootstrap.py` -- the thirteen pasted bootstrap cases, plus the harness
  that measures them.  Run with no arguments it prints the comparison
  table; with a case label it runs one case, which is internal.  Cases
  are named by what they need -- `venv1`, `pip2`, `nopip3` -- and not
  numbered 1 to 13 any more; the module docstring maps the old numbers
  that closed tasks in `LOGBOOK.md` still use.
* `alt_venv.py` -- the second stage, fetched as a wheel.  `AltVEnv`
  downloads, approves, unpacks and imports.  It carries its own PEP 723
  block, which is the one place the Python floor is written down.
* `alt_venv_test.py` -- the whole test suite, and the local package
  server it runs against.  Nothing in it reaches the network.
* `alt_venv_coverage.py` -- coverage, using the standard library
  `trace` rather than `coverage`, so the suite needs nothing installed.
* `quick_start.py` -- the whole program `README.md`'s Quick Start asks
  a person to copy.  The README carries it verbatim, and
  `test_the_quick_start_is_current` fails if the two drift or its
  bootstrap is not the current one.  Edit the file, then paste it into
  the README; never the other way round.
* `trace_hook/sitecustomize.py` -- how child processes get traced.  It
  is in a directory of its own on purpose, because a `sitecustomize.py`
  in the project root would affect every interpreter started here.

Before any piece of work is called finished, three things are clean:
`ruff check`, `mypy`, and no line over 79 columns in any file including
the Markdown.  The tests that bear on the change are run by name, as
`python3 -m unittest alt_venv_test.SomeTest.test_one ...`, and pass.

The **full suite** is run only for two things: closing a task, which
cannot happen until it passes, and measuring coverage.  It takes too
long to run otherwise.  Steps have no open or closed status, so
finishing one does not call for it.

    python3 alt_venv_test.py                  # about 90 seconds
    ALT_VENV_TEST=COMPLETE python3 alt_venv_test.py

`ALT_VENV_TEST` chooses how many of the thirteen bootstrap cases the
all-case tests exercise.  Unset or `FAST` uses the three that need no
pip, `nopip1` to `nopip3`; `COMPLETE` uses all thirteen and takes
several times longer.  The cull follows the same setting.  `nopip3` is
the one that ships, and the suite names it `SHIPPING`.  Case names,
such as `pip2` or `pip1,pip2`, select just those, and `NONE` selects no
case at all, which is the cull's baseline.  Anything else is refused
rather than quietly treated as `FAST`.

    ./alt_venv_coverage.py <directory>             # this process only
    ./alt_venv_coverage.py --children <directory>  # much slower

`--children` is what makes `bootstrap.py` visible at all: its cases run
in child interpreters, and without it the file reads as 7% however
thoroughly it is exercised.  With `--children` and `COMPLETE` the whole
measurement takes about twenty minutes, which is why it is off unless
asked for.

The **cull run** measures what each `bootstrap.py` case adds to
coverage, so that cases can be deleted on evidence; see Step 6.16 of
`LOGBOOK.md`.  Wayne starts it himself at bedtime, because the machine
is a laptop and cron cannot run while it sleeps:

    mkdir -p ~/alt_venv_cull && cd ~/public_html/projects/alt_venv && \
      nohup ./alt_venv_coverage.py --per-case \
      ~/alt_venv_cull/$(date +%F) > ~/alt_venv_cull/$(date +%F).log 2>&1 &

The answer is `~/alt_venv_cull/<date>/report.md`.  Re-reading saved runs
costs seconds: `./alt_venv_coverage.py --compare <that directory>`.  A
test that runs a bootstrap case must carry `@runs_cases`, or the cull
credits its coverage to no case; `test_case_runners_are_marked` enforces
it.

`AltVEnv` also reads `ALT_VENV_APPROVE`: unset enforces the approvals
file beside the calling program, `write` records what arrived, and
`skip` does neither.  `ALT_VENV_BOOTSTRAP=check` makes `install()`
say on standard error whether the program's pasted bootstrap is the
current one; `alt_venv.BOOTSTRAPS` lists the published ones, and
`bootstrap.pasted("nopip3")` is the exact text a person pastes.

**Never edit a file while a measurement is running** -- a coverage run,
a cull, or `bootstrap.py`'s report.  They take minutes, they read the
source as they go, and an edit in the middle counts the same lines
under two different numbers.  It happened on 2026-10-01 and voided a
cull's report; see Step 6.16.4.  Wait for it, or make the edit first.

## Where things stand

Updated at the end of each session, so that a fresh one starts here.
As of 2026-10-02:

* **Next:** `README.md` is nearly finished, and the next session starts
  there.  It is Wayne's file; help when asked, do not edit it unasked,
  and rewrap his over-long lines.  Its sections now run: the hook
  (problem, answer, happy ending), Quick Start (copy and run
  `quick_start.py`, then a read-along of its five `# Part` comments),
  Download Prompt, Author Package Management, Miscellaneous,
  Alternatives, Conclusion.  What is left:
  * **Conclusion.**  Claude proposed, and Wayne was too tired to read:
    (1) replace it with four lines closing the opening story -- list
    packages in Part 1, copy Parts 2 and 3, a single file you can
    e-mail; (2) add short `## Status` and `## License` sections; (3)
    say under Status that Windows never shows the download prompt.
    Also: the repository has no `LICENSE` file, which PyPI and GitHub
    look for.
  * **Author Package Management** is a placeholder.  Wayne wants a
    true freeze, to be "functionally equivalent to" `zipapp` (he wrote
    `appap`; Claude read it as `zipapp` and said so).  An HTML comment
    in the section records what a freeze needs: `==` pins in Part 1
    plus the approvals file, perhaps with `ALT_VENV_APPROVE=write`
    printing the pins.  Approvals are keyed by wheel file name, so a
    compiled package approved on one platform is refused on another.
  * **Alternatives** is a first pass, unreviewed.  Settled overnight:
    `quick_start.py` does run under `uv run`, but redundantly -- `uv`
    installs `cowsay` into its environment, then the bootstrap fetches
    `alt_venv`, downloads `cowsay` again into `~/.alt_venv`, asks, and
    imports its own copy.  So "works with `uv`" needs that caveat, or a
    code change: `install()` could skip what is already importable.
  * **The PyPI names are free**, checked 2026-10-02: `alt_venv`,
    `alt-venv` and `altvenv` all return 404.  The bootstrap installs
    whatever PyPI serves under `alt_venv`, so anyone who registers it
    first owns every program that pastes it.  Worth claiming soon.
  * The facts the README rests on:
    * The shipping bootstrap is `nopip3`: **31 pasted lines** -- its 28
      line body plus `import importlib`, `import pathlib` and
      `import sys`.  Since 2026-10-02 it calls
      `AltVEnv().install(bootstrap="nopip3")` itself, so a program's
      author never touches `AltVEnv` or names `alt_venv`.  The label is
      read by nothing, but Wayne wants it; there is no `package=`.
    * What a machine needs: Python 3.11 or later, and a network that
      reaches PyPI on the first run.  No `pip`, no virtual environment,
      no administrator rights.  Verified on Linux only, under 3.11 and
      3.12; Windows and macOS are untried (`2wmau`, `2btosc`).
    * The Quick Start cannot work until `alt_venv` is on PyPI.  It was
      verified end to end with `alt_venv` from a local index and `pip`
      and `cowsay` from the real PyPI.
    * `README.md` says the bootstrap's first-run `pip` output is
      visible on purpose, at Wayne's word, and that `AltVEnv` hides
      `pip`'s output unless `pip` fails, which is what the code does.
    * Wayne wants `pip` kept out of the opening sections.
* **Waiting on Wayne:**
  * Whether `nopip3`'s `pip` call should get `stdout=2`.  The README now
    calls its output deliberate, so this is only about which stream it
    goes to.  See Step 6.13.1.
  * Whether the download prompt should use his wording, `AltVEnv wants
    to download 2 packages with 3 dependencies ...`.  The README shows
    the code's real prompt; changing it is a code change, and the
    README follows.
  * Windows never shows the download prompt: `terminal()` opens
    `/dev/tty`.  Part of `2wmau`.
  * Whether the cull should measure a copy of the project, so that an
    edit during a run cannot void it.  See Step 6.16.4.
  * Restructuring `LOGBOOK.md`: Wayne has realised tasks and steps are
    inverted -- steps must be sequential, tasks may run in parallel --
    and will rework his workflow after this project closes.  Do not
    restructure it unasked.  Issue `3rthtf` waits on the same.
  * Publishing to test.pypi.org, Step 6.17, after `README.md`.
* **Overnight 2026-10-02:** everything passes under 3.12 (`COMPLETE`,
  `--children`, both opt-in classes; `alt_venv.py` 100%, `bootstrap.py`
  99%, the one line being `pip3`'s non-Debian fallback) and under uv's
  CPython 3.11.16.  The 3.11 run found three faults, all fixed; see
  Step 6.16.9.  To rerun under 3.11:
  `~/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11
  alt_venv_test.py`.
* **Open issues:** `2btosc` and `2wmau`, waiting on access to macOS and
  Windows, which Wayne is arranging; `3rthtf`, above.

## Python style

Python written for this project follows `python_with_markdown.md`, in
this directory.  It is a symbolic link to Wayne's own write-up, which
adapts the [Google Python Style
Guide](https://google.github.io/styleguide/pyguide.html) to docstrings
written in Markdown.  Read it before writing Python here; what follows
is only the part that comes up most often.

1. **Docstrings are Markdown.**  Triple double quotes, with a one line
   summary ending in a period immediately after the opening quotes, a
   blank line, then paragraphs.  Functions, classes and methods list
   `Arguments:`, `Returns:` or `Yields:`, and `Raises:` as bulleted
   lists, each name followed by its type in backquoted parentheses.
   Classes document `Attributes:` and a `Constructor:` line.

2. **79 columns**, per PEP 8, in docstrings and comments as much as in
   code.

3. **Backquote every identifier** named in prose, so that `my_func` and
   `my_variable` read as code rather than as English.

4. **Write complete sentences**, capitalized and ending in a period.
   Editors have spell checkers; there is no excuse for typos.

5. **Type hints everywhere, and both linters silent.**  `mypy <file>`
   and `ruff check <file>` should report nothing before a piece of work
   is called finished.  `ruff check --fix` is safe to run.

6. **A license boilerplate closes the module docstring**, with the SPDX
   identifier on the line immediately after the closing quotes.  This
   project uses MIT No Attribution:

       """
       ...
       MIT No Attribution

       Copyright <year> Wayne C. Gramlich
       ...
       """
       # SPDX-License-Identifier: MIT-0

Documentation that costs more lines than the code it describes is
fine.  Disk is cheap and rereading is not.
