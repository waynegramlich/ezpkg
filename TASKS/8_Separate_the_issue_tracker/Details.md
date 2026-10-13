# 8 Separate the issue tracker

A plan, agreed 2026-10-04 and not yet started.  Issues are to be
managed apart from tasks, by a program of their own.

1. Each issue gets a tag such as `I.whwnn`: `I.` and the first letter
   of each word of its title, lower cased, with `a`, `an`, `the` and
   `of` dropped, and a trailing digit when two collide.  The tag is
   derived once, when the issue is created, and never changes, even if
   the title or the priority does.  The regular expression
   `\bI\.[a-z]+[0-9]?\b` finds every reference.  A false positive,
   such as an attribute of something named `I`, is flagged and fixed
   by hand.
2. Priority is separate from the tag, so changing it renames nothing.
3. `ISSUES/` holds one sub-directory per issue, as `TASKS/` does, with
   the priority in a hidden file, as `.status` is for a task.
4. An `issue` program, sharing roughly the same code as `task.py`,
   creates and manages them, lists them sorted by priority, and
   regenerates an `ISSUES/Startup` of `@` imports for the active
   issues, so that `CLAUDE.md` can import it.
5. Until then the issues live in `ISSUES.md`, under its old rules.
   Their old tags, such as `I.whwnn`, are renamed in one pass when the
   program exists.

The work is mostly in `RULES/`, Wayne's `claude_notes` repository.
