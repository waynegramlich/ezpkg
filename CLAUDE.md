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

3. **Commit messages are drafted in `.git_commit.md`.**  That file is
   the one place a git commit message is composed; Claude writes a
   proposed message there, says it is ready, and stops.  Wayne reviews
   it and runs `git commit -F .git_commit.md` himself.  The file is
   listed in `.gitignore`, so it never becomes part of a commit -- it
   holds only the *next* message, and is overwritten by the one after
   that.  It is tracked in mercurial, so drafts are recoverable like
   everything else.

   Claude adds no `Co-Authored-By:` trailer, and no other generated
   attribution line, to anything written there.  Wayne is the author of
   record for every git commit.

4. **Every git commit message must stand on its own** in `git log`.  One
   commit per meaningful unit of work.  No "wip", no "fix typo", no
   "checkpoint", no chains of commits that only make sense in order.  If
   the work took twelve mercurial checkpoints, it still lands in git as
   one commit.

5. **To undo, reach for mercurial**, not git.  `hg log`, then
   `hg revert -r <rev> <file>` or `hg update -r <rev>`.  Checkpoint
   freely and often -- being able to undo is really, really important
   here, and mercurial is the only tool Claude has for it.

6. **In `log_book.md`, do not edit above the `FENCE:` marker.**
   `log_book.md` is this project's running record -- purpose, problem
   statement, prior art, findings and decisions.  Wayne maintains it,
   with suggestions from Claude.  An HTML comment containing `FENCE:`
   marks how far the settled material reaches; everything above that
   comment is considered decided.  Editing it is discouraged, so propose
   the change and let Wayne make the call rather than editing it
   directly.  Exceptions can be made -- ask.  Text below the fence is
   ordinary working material and can be edited normally.  The fence
   moves down the file as more of the document settles.

   The point is to stop settled questions from being reopened over and
   over.

### Why

A log where every entry is meaningful is worth more than a log that
records everything that happened.  Mercurial already records everything
that happened.
