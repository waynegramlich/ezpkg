# LLM Agent Context Log

## 2026-10-11: Design agreed with Wayne, and first implementation

* Why: a package the author's own Python happens to have (e.g. a
  distribution's `python3-requests`) but Part 1 does not name works for
  the author and fails for the recipient.  "Is it preinstalled
  everywhere?" has no stable answer, so we check at export time instead.
* Wayne's decisions: no new environment variable; nothing checked while
  developing (an `ImportError` already tells the author); every
  `ALT_VENV_EXPORT` form (`pins`, `zipapp`, `uv`) checks first, lists
  every problem on standard error, then fails ("nag").  Imports in a
  `try` that catches `ImportError` are ignored.  No guessing package
  names from PyPI.  `tkinter` does not matter; `alt_venv` itself does not
  use `venv` or `ensurepip` (only `bootstrap.py`'s `venv*` cases do).
* Code: `program_imports(text)` (module level, `ast`) and
  `AltVEnv.check_imports(asking)`, called from `export()` after the form
  is validated.  Accepted: standard library (`sys.stdlib_module_names`),
  `alt_venv`, a file or directory beside the program, and modules whose
  distribution (`importlib.metadata.packages_distributions()`) is
  declared or recorded in the approvals (which covers the packages that
  came along, e.g. `widget` under `needy`).  Platform-guarded imports
  that find nothing are not reported.  `TYPE_CHECKING` and relative
  imports are skipped.
* Tests: `test_export_refuses_an_undeclared_import`,
  `test_program_imports_leaves_out_what_may_fail`.  The existing export
  tests still pass.
* Unrelated failure seen: `test_the_quick_start_is_current` wants
  `#### Part N` headings, which the README rework (`T.rd`)
  replaced with `### Part N: ...`.  Leave it for the README work.
