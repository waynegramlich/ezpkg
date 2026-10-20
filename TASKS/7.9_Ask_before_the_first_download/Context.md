# LLM Agent Context Log

Earlier entries (the `ux01`-`ux27` review, the redesign's slices and
the 2026-10-19 batches) are in `History.md`.

## 2026-10-19: State at day's end (condensed)

`Details.md` "The Design" is the design, with these changes since:

* End user: the question's paragraph says "they are retained in";
  a no on a first run removes `~/.ezpkg`, a no on a later program
  (`newly_filled` false) keeps it and says "answer `n` and `second.py`
  will not run."  A bare Enter asks again, silently and uncounted; no
  answer in 5 minutes is no (`EZPKG_ANSWER_SECONDS` shortens it, for
  tests and `ux/drive.py` only).  The list after a yes says "retained".
  Failed fetches are `I.ffspo`'s one-line messages (wording agreed).
* Developer: never sees the end user's list; `medium` shows each
  change; a misspelt import reads "`prog.py` line N: `import x` needs
  a package, but PyPI has none called `x`."; a failed fetch is one
  line with `pip`'s `ERROR:` (S1.5f), the lock hint a line of its own.
  `ranges` is gone: every release ranges bare entries (S5.1b) and the
  `ezpkg` entry, except from a source `ezpkg` (S5.1c); `bootstrap`
  governs only the bootstrap.  A release prints one "Released ..."
  line.  Marks go when an import explains the entry (S3.1e, `MARK`).
  Compiled wheels' approvals carry `tag:` (S2.4d).  The template
  explains itself (S1.5h); `T.ept` holds Wayne's edits.
* Windows `remove.py`: docs give `py $HOME\.ezpkg\remove.py`
  (PowerShell, every version) and `py %USERPROFILE%\.ezpkg\remove.py`
  (`cmd.exe`); researched in `History.md`.
* Fixed via `ux` step 2.2: `reconcile`'s fetch (`fetching`) asks what
  `providing` asks, so a developer's new import edits `prog.py` once.
* `ux/drive.py`: end user 1.1-1.12, developer 2.1-2.13 (including a
  release and running its `.pyz` and `uv` exports): 25 of 25 pass.
  Unread by Wayne, batched for later: `ux/ux01`-`ux25`.
* Rehearsed as `0.0.1.dev202610200048` (the day's last commit):
  `release_check` and `check.yml` run 39349884759 (25 jobs) passed.
* `README.md.old` is the old README; `README.md` is a skeleton of
  headings (Wayne starts it 2026-10-20).  README gates the pypi.org
  setup (`T.utpat`).

## Open

* Wayne's batched read of `ux/`, then `T.ept`'s template edits.
* Lower: S2.2b (`python -c` is not asked on a warm run), S2.4g (Part 1
  grows 3 + 1 lines per package; recommended accept), S2.4h, S3.3c,
  S3.3d, S5.1d (agent's notes, `History.md`).
* Then `Summary.md` and close.  Issue numbering: `S<slice>.<n>`,
  letter sub-items, never renumbered.
