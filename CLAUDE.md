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

The division is absolute in both directions: Claude never runs `git`, and
Wayne never runs `hg`.  Wayne includes `CLAUDE.md` in every git commit, so
the rules stay versioned alongside the work they govern.

### Rules for Claude

1. **Checkpoint into mercurial often**, especially before any edit that
   would be annoying to reconstruct, and after any step that works.
   `hg commit -A -m "checkpoint: <what was just tried>"`.  These messages
   are notes to our future selves, not publishable history; they do not
   need to be good.

2. **Claude never runs `git` at all.**  Not `commit`, not `add`, not
   `amend`, not `init`, not a branch or a tag.  Wayne does every git
   operation himself, by hand.  When a chunk of work looks finished, say
   so and stop there; do not offer to commit it, and do not stage
   anything in preparation.  Reading state with `git status` or
   `git log` is also off limits -- if that information is needed, ask.

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

   The file is organised as numbered tasks.  A task whose heading
   carries `(CLOSED YYYY-MM-DD)` and a summary section is settled: do
   not edit it, propose the change and let Wayne make the call.  A task
   with neither is open and can be edited normally.  A task with one
   but not the other is a mistake worth pointing out.  This replaced
   the `FENCE:` marker on 2026-09-24.

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
