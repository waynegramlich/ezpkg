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

6. **The work is recorded as tasks under `TASKS/`**, managed by the
   `./task` program, which is described by the rules imported below;
   `./task help` lists its commands.  `LOGBOOK.md` held all of this
   until 2026-10-04, when it was retired: its background went to
   `ABOUT.md`, its issues to `ISSUES.md`, and each task and step of
   Task 6 to a task directory of the same number.

   * A task is `Open` while it is being worked on now, `Suspended`
     while it is unfinished but waiting, usually on Wayne, and `Closed`
     when it is done.
   * Each task directory holds three files.  `Details.md` says what the
     task is, in a few lines; Wayne writes it, and every session reads
     every task's, through `TASKS/Startup`, so it stays short.
     `Context.md` is Claude's and says where the work stands, so that a
     fresh session can pick it up; it is read only while the task is
     open, and Claude keeps it current.  `History.md` is the full
     record -- findings, measurements, decisions -- and is not read at
     startup; read it when the task needs it, and add to it as work is
     learned.
   * A closed task is settled: do not edit it, propose the change and
     let Wayne make the call.
   * `History.md` files and code comments still say "Step 6.16.4" and
     the like.  That is task 6.16, item 4 of its `History.md`; "see
     Step 6.12 in `TASKS/`" in a comment means task 6.12.

   The point is to stop settled questions from being reopened over and
   over.

@RULES/Task_Tracking_Rules.md
@TASKS/Startup

7. **Issues live in `ISSUES.md`**, until task 7 gives them a program
   of their own, and that file's preamble is the authority on how they
   work.  The parts that are easy to get wrong:

   * Each issue is named by an identifier such as `I.whwnn` -- a
     priority digit, then the first letter of each word of its title,
     lower cased, with `a`, `an`, `the` and `of` dropped.  Punctuation
     is dropped and a hyphenated word counts once.  Two titles that
     collide take a trailing digit.  Task 7 replaces these with frozen
     tags such as `I.whwnn`, renamed in one pass.
   * Changing an issue's priority or its title changes its
     identifier.  Updating every reference to the old name in the
     same pass is Claude's job, and is not a reason to leave an issue
     mis-prioritised.
   * A resolved issue moves to `## Closed Issues` with the date it
     was closed, and is purged later, once every reference to it is
     gone.  Rejected ones live in `## Rejected Issues` and are not
     purged by age, because their purpose is to stop the same idea
     coming back.

### Why

A log where every entry is meaningful is worth more than a log that
records everything that happened.  Mercurial already records everything
that happened.

## Talking to Wayne

Number the items of any list in a reply, so that Wayne can answer them
by number.  Asked for on 2026-10-04.

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
* `TASKS/`, `ISSUES.md` and `ABOUT.md` are joint, as rules 6 and 7
  describe.  `RULES/` is a symbolic link into Wayne's `claude_notes`
  repository: Claude may fix `RULES/task.py` and its rules, and Wayne
  commits them.

## The code, and how to run it

Six files, and it matters which is which:

* `bootstrap.py` -- the thirteen pasted bootstrap cases, plus the harness
  that measures them.  Run with no arguments it prints the comparison
  table; with a case label it runs one case, which is internal.  Cases
  are named by what they need -- `venv1`, `pip2`, `nopip3` -- and not
  numbered 1 to 13 any more; the module docstring maps the old numbers
  that the `History.md` files under `TASKS/` still use.
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
coverage, so that cases can be deleted on evidence; see task 6.16.
Wayne starts it himself at bedtime, because the machine is a laptop
and cron cannot run while it sleeps:

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
As of 2026-10-04:

* **Next:** `README.md`, task 6.10.  Its `Context.md` says what is left
  and the facts the README rests on.
* **Waiting on Wayne:**
  * Whether `nopip3`'s `pip` call should get `stdout=2`.  The README now
    calls its output deliberate, so this is only about which stream it
    goes to.  See Step 6.13.1.
  * Whether the download prompt should use his wording, `AltVEnv wants
    to download 2 packages with 3 dependencies ...`.  The README shows
    the code's real prompt; changing it is a code change, and the
    README follows.
  * Windows never shows the download prompt: `terminal()` opens
    `/dev/tty`.  Part of `I.wmau`.
  * Whether the cull should measure a copy of the project, so that an
    edit during a run cannot void it.  See Step 6.16.4.
  * Publishing to test.pypi.org, Step 6.17, after `README.md`.
* **Overnight 2026-10-02:** everything passes under 3.12 (`COMPLETE`,
  `--children`, both opt-in classes; `alt_venv.py` 100%, `bootstrap.py`
  99%, the one line being `pip3`'s non-Debian fallback) and under uv's
  CPython 3.11.16.  The 3.11 run found three faults, all fixed; see
  Step 6.16.9.  To rerun under 3.11:
  `~/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11
  alt_venv_test.py`.
* **Open issues:** `I.btosc` and `I.wmau`, waiting on access to macOS and
  Windows, which Wayne is arranging; `I.rthtf`, which waits on task 7.

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
