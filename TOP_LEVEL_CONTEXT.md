# Top Level Context

<!-- --------------------------- 79 characters ---------------------------- -->

`CLAUDE.md` holds only `@` imports; project facts that every session
needs live here instead.

## The Files

* `ezpkg.py`: The `ezpkg` package itself (the `EZPkg` class).
* `quick_start.py`: The Quick Start program, and the authority for the
  bootstrap text.
* `bootstrap.py`: Every bootstrap this project has tried, one function
  per case (`nopip1` ... `nopip7`); `nopip7` is the one that ships.
* `ezpkg_test.py`: The test suite.
* `ezpkg_coverage.py`: Coverage with the standard library `trace`
  (`trace_hook/` carries it into child processes).
* `README.md`: The user documentation.
* `release.py`: Builds the wheel to publish (`./release.py
  testpypi|pypi DIR`), using `release_wheel` from `ezpkg_test.py`.
* `.github/workflows/release.yml`: Publishes it with Trusted
  Publishing, after Wayne approves on GitHub (`T.wrw`).
* `release_check.py`: Runs the Quick Start as a new user against a
  published `ezpkg` (`./release_check.py [--python PY] [--console]
  testpypi|pypi [VERSION]`).  `--console` gives it a real terminal
  (a pseudoterminal, or ConPTY via `pywinpty` on Windows) and answers
  the download prompt.
* `.github/workflows/check.yml`: Runs `release_check.py` on GitHub's
  Linux, Windows, Apple Silicon and Intel macOS runners, Python 3.11
  to 3.15, plus python.org's macOS Python without certificates and a
  `--console` job per system: `gh workflow run check.yml -f
  target=testpypi -f version=V` (25 jobs, about 3 minutes; Claude
  starts it).  Started by hand, not yet by `release.yml` (`T.gar`).
* `ux/drive.py [--keep] [--until STEP | --only STEP...] [--ux-dir
  DIR]`: Runs the scripted UX steps
  (1.1-1.23) on a pseudoterminal in a temporary copy of the Quick
  Start, as a stranger's real first run: a fresh home, the bootstrap
  fetching `pip` from pypi.org and installing a wheel of the project's
  `ezpkg.py` (`PIP_FIND_LINKS`), everything else from real pypi.org.
  Each step declares the program's mode (`end-user`, `developer`, or
  `gone` when `~/.ezpkg` must be removed) and is checked against it.
  Claude runs it (about 7 minutes, in the background).  The transcript,
  with framed steps, is `ux/drive_output.txt` (ignored); each step is
  also written unframed to `ux/uxNN_NAME.txt` (`NN` is the step's
  position, not its number), which Wayne edits into the agreed output
  and commits, so `git diff ux/` after a rerun shows what is left to
  build (`T.abfd`'s `Context.md`).  A rerun overwrites them; while
  Wayne may be editing them, run with `--ux-dir` into the scratchpad
  and copy back.  Each step also leaves `uxNN_prog.py` (as it ran) and,
  if `ezpkg` edited it, `uxNN_prog_after.py`, named on the `.txt`'s
  third line, so Wayne can `diff` the transitions.
  `--only 1.4` runs one step from the snapshot the step before left
  in `ux/.snapshots/` (ignored; dropped when the code changes), or
  after running the earlier steps as unrecorded setup.
* `git_hooks/`: `prepare-commit-msg` adds `Assisted-by: Claude
  Code:claude-opus-5-5` to Wayne's commit messages (deletable in the
  editor), and `commit-msg` refuses a message that is only that
  trailer.  On per clone with `git config core.hooksPath git_hooks`.
  Update the trailer when the model changes.

## The Bootstrap Has Four Copies

`quick_start.py` is the authority, and the test suite fails until these
match it:

* Both bootstrap copies in `README.md` (Quick Start, and Enabling
  `EZPkg` for Your Program).
* `QUICK_START` in `ezpkg.py`.
* The `nopip7` function in `bootstrap.py` (which spells the package name
  as `PACKAGE` and the index as `JSON_API`).

A changed bootstrap is a new one, comments and spaces included
(`T.reb`: `EZPkg` refuses any bootstrap that is not, line for line once
trimmed, a published one).  It needs a new `nopipN` name, its
fingerprint added to the end of `BOOTSTRAPS` in `ezpkg.py`, and the
previous text kept in `OLD_BOOTSTRAP_TEXTS`.  `bootstrap.py`'s copies
spell things as variables, so its harness sets
`EZPKG_BOOTSTRAP=unchecked`.

Part 1 of every program with a bootstrap lists `ezpkg` first (the Quick
Start's is `ezpkg>=0.0.1.dev0,<0.1` until the real release), and that
entry chooses which `ezpkg` runs it (`T.eui`).

## Testing and Linting

* Quick tests, during development (about 2 minutes):
  `EZPKG_TEST=NONE ./ezpkg_test.py`.  A single class or method can be
  named after it.
* The full suite (`./ezpkg_test.py`, or `EZPKG_TEST=COMPLETE` for every
  `bootstrap.py` case) runs only when Wayne asks.
* `ruff check .` and `mypy .`; both check against the Python 3.11 floor.
  `quick_start.py` draws one known `I001` (no blank line after the
  Part 2 imports).

## Working With Wayne

* `README.md` rewrites are proposed in HTML comments beside the old
  text, with the line ranges of both (recheck them, since they shift);
  when Wayne says delete, delete.  Never nest HTML comments: an inner
  `-->` ends the outer one.  Wayne answers with `<!-- Claude: ... -->`
  notes, and open items are `<!-- Issue: ... -->` comments.  Re-read
  the file before editing, since Wayne edits it between turns.
* Wayne does his own end-to-end reads of `README.md`.
* Wayne prefers discussing in chat to notes in `Details.md` files.
* Claude may push to GitHub, and start and approve `testpypi` release
  runs, but never commits; Wayne commits staged changes.
* `ezpkg` is on test.pypi.org (`T.uttat`) but not yet on pypi.org
  (`T.utpat`), so the Quick Start does not yet work for a new user;
  `ux/drive.py` installs a wheel of the project's `ezpkg.py`, and
  `release_check.py` checks what was published.
