# 4 Convert the logbook to the new format: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Task 4 of `LOGBOOK.md` on 2026-10-04.

## Task 4: Convert the Logbook to the New Format  (CLOSED 2026-09-24)

`log_book.md` grew as a running narrative with a `FENCE:` marker
separating settled material from working material.  That worked, but the
fence had to be moved by hand and the issue conventions lived only in
the file's own preamble.  This task renames the file to `LOGBOOK.md` and
converts it to the format described in `claude_notes.md`: numbered tasks
that close with a date and a summary, and issues split into active,
pending, rejected and closed.

The fence is gone.  A closed task is marked `(CLOSED YYYY-MM-DD)` in its
heading and carries a summary; both are required, and either one alone
means the task is still open.

Decisions about the format itself are collected in `LOGBOOK_NOTES.md`,
so that they can be propagated back into `claude_notes.md` and then
deleted from this project.

### Task 4 Summary

This file is now `LOGBOOK.md` and is organized as the template in
`claude_notes.md` describes.  In addition, the `FENCE:` marker is gone.
In its place a task is settled when its heading carries `(CLOSED YYYY-MM-DD)`
**and** it has a summary.

Three sections were dissolved rather than moved:
* `Rules of Engagement` -- already said by Task 1 and `CLAUDE.md`.
* The `python3 -m venv` shell transcripts -- a tutorial, not a finding.
* `Misc.` -- three blocks moved out, two superseded, one a pointer.

The issue tracker changed shape:
* Some issues got renamed due to new Issue naming rules.
* Each issue has progress through 4 states - `Active`, `Pending`,
  `Rejected` and `Closed`.
* `Wayne's current thoughts` became `Various thoughts`

Decisions about the logbook format were collected in `LOGBOOK_NOTES.md`,
propagated into `claude_notes.md`, which resides in another directory
under its own separate version control, and then deleted.

(CLOSED 2026-09-24)
