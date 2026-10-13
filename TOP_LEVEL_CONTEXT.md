# Top Level Context

<!-- --------------------------- 79 characters ---------------------------- -->

`CLAUDE.md` holds only `@` imports; project facts that every session
needs live here instead.

## The Files

* `ezpkg.py`: The `ezpkg` package itself (the `EZPkg` class).
* `quick_start.py`: The Quick Start program, and the authority for the
  bootstrap text.
* `bootstrap.py`: Every bootstrap this project has tried, one function
  per case (`nopip1` ... `nopip5`); `nopip5` is the one that ships.
* `ezpkg_test.py`: The test suite.
* `ezpkg_coverage.py`: Coverage with the standard library `trace`
  (`trace_hook/` carries it into child processes).
* `README.md`: The user documentation.

## The Bootstrap Has Four Copies

`quick_start.py` is the authority, and the test suite fails until these
match it:

* Both bootstrap copies in `README.md` (Quick Start, and Enabling
  `EZPkg` for Your Program).
* `QUICK_START` in `ezpkg.py`.
* The `nopip5` function in `bootstrap.py` (which spells the package name
  as `PACKAGE` and the index as `JSON_API`).

`bootstrap_fingerprint` ignores comments and whitespace, so a comment
edit keeps the same bootstrap.  A code edit makes a new one: it needs a
new `nopipN` name and its fingerprint added to the end of `BOOTSTRAPS` in
`ezpkg.py`.

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
* `ezpkg` is not on PyPI yet (`T.utt`, then `T.utp`), so the Quick Start
  cannot work for a new user; dogfood runs use `PYTHONPATH` pointing at
  the project.
