# LLM Agent Context Log

Earlier entries (the `ux01`-`ux27` review, the redesign's slices and
the 2026-10-19 batches) are in `History.md`.

Superseded 2026-10-22 (see `T.ee`'s `Context.md`): `auto-dependencies`
is gone, a developer writes no Part 1, and a developer's Part 1
is no longer edited (the stash), releases follow `release` and go into
`prog.py.releases`, and `cull` uses 30 days.  Entries below that say
otherwise describe the code before that day.

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
* README gates the pypi.org setup (`T.utpat`); see the 2026-10-20
  README entry below.

## Open

* Wayne's batched read of `ux/`, then `T.ept`'s template edits.
* Lower: S2.2b (`python -c` is not asked on a warm run), S2.4g (Part 1
  grows 3 + 1 lines per package; recommended accept), S2.4h, S3.3c,
  S3.3d, S5.1d (agent's notes, `History.md`).
* Then `Summary.md` and close.  Issue numbering: `S<slice>.<n>`,
  letter sub-items, never renumbered.

## 2026-10-20: `nopip8`, a shorter bootstrap

* Wayne: `nopip7`'s Part 3 (35 lines) barely fit on a screen.
  `nopip8` (24 lines) fetches only `ezpkg`'s wheel via the JSON API,
  checks its SHA-256, keeps `~/.ezpkg/ezpkg.whl` and imports from it.
  `EZPkg.own_pip` now fetches every stranger's `pip`, from `json_api`
  (`PIP_INDEX_URL`'s index, else pypi.org).  A first run is
  `first_run`: `nopip7`'s `pip=n`, or `ezpkg.whl` with no `versions/`.
* `ux/drive.py` and `release_check.py testpypi` seed `ezpkg.whl`,
  since pypi.org has no `ezpkg` yet; `release_check.py pypi` lets the
  bootstrap fetch it.
* Every new end user is asked, whatever Part 1 carries (Wayne); the
  approvals are Part 1's `[tool.ezpkg] checksums` (renamed from
  `approved`).  With no terminal, or `CI` set, the answer is yes.
* An entry nothing imports goes once the latest recorded run declared
  it and none of the last `RUNS_KEPT` (10) runs loaded it behind the
  scenes (`unused_lately`; `note_loaded` by `atexit`, only the
  program's entries); a comment keeps it.  Replaces the `# Needed`
  marks (`needed_by`, `MARK`, `unmark` gone).  `Details.md` items
  1-3 under "follows the imports".  `ux/drive.py` 2.4/2.5 rewritten,
  not yet rerun.

## 2026-10-20: README pass with Wayne (top-2 rounds)

* Wayne rewrote `README.md` end to end; Claude checked it against the
  code in rounds of two, quoting line numbers recomputed just before
  each reply.  Done: Quick Start is `nopip8`; failures section (3
  bullets, `last_failure.txt` named except for No Network); Windows
  commands use `py`; "asked once" is per file path; no terminal (or
  `CI`) means yes; settings listed as the template shows them;
  "Releasing a Packaged Program" (`zipapp`, `uv`) rewritten from
  `build_uv`/`release`; How It Works ends with the `ezpkg` switch.
* Only `## Missing Sections` (an `Issue:` comment: Troubleshooting,
  Limitations, `uv run`/installed `ezpkg`, License) is left; Wayne
  says the rest is complete.  `README.md.old` was the source of the
  restored text.
* Not taken: the Garbage collection bullet's promise that an agreed
  program keeps its packages (Wayne skeptical; left out).
* Next: Wayne's own read; then `T.ept` (template), `T.utpat`.

## 2026-10-20: README against the code (top-2 rounds, evening)

* Done: upgrade/`checksums` detail cut (one sentence left); a release
  is once per version; zipapp refusal says take `"zipapp"` out of
  `exports`; no-terminal wording (covers `CI`); `uv` bullets no longer
  say `checksums`; Enabling step 1 keeps `from __future__` above Part
  2 and deletes `"cowsay"`; `cmd.exe` `type nul`; "After a `y`" lead-in.
* Part 2 of all three Quick Start copies has a new comment line, ``A
  `from __future__ import ...` line, if any, goes above Part 2.``
  (outside the `try`, so still `nopip8`).  `ux/` snapshots now stale.
* Code: the "Released ..." line names the `uv` lock when written
  (`release`); asserted in
  `test_write_pins_an_ezpkg_installed_from_a_wheel`.  Quick suite: 312
  tests OK (16 skipped: date tests, normal `HOME`).
* Open: the `<!-- Claude: -->` Security proposal (README, before
  Miscellaneous), unread by Wayne.
* Found: `checksums` holds only what arrived on the author's machine,
  so a marker-dependent package (`click`'s `colorama` on Windows,
  `typing_extensions` on older Pythons) is refused by `verify` on a
  friend's machine.  Wayne's direction: a new `email` export that
  resolves for every platform and Python at release.  Built and
  proved on Windows the same night: see `T.ee`.
