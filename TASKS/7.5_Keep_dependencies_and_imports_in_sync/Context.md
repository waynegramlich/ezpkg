# LLM Agent Context Log

Earlier entries (the interactive reconcile, the batch question,
Manual and Auto, dogfood findings) are in `History.md`.

## 2026-10-19: State (condensed)

* The redesign (`T.abfd`, slice 3) made reconciliation silent and
  developer-only: `reconcile` in `ezpkg.py`, with no questions.
  `Details.md` items 5, 6, 8 and 9 (asking, approving, `k`,
  `EZPKG_APPROVE`) describe the old design; `T.abfd`'s `Details.md`
  is current.
* Still in use from this task: `discrepancy` / `Discrepancy`,
  `every_import`, `dependency_fingerprint` (includes `__version__`),
  `with_dependency_list` (keeps comments), `with_type_ignores`,
  `MODULE_PACKAGES`, `wheel_modules`, `index_files`, `EZPkg.prove`
  (guessed names: no package, source only, does not provide),
  `failure_reason`, `version_range` (caps `<0.(x+1)` for `0.x`,
  `<(major+1)` for 1-9, none from 10), `providing(module, providers)`
  (Debian's stripped metadata), `satisfied` ignoring `EZPkg`'s cache.
* Left alone on purpose: a declared package with silent metadata that
  nothing imports is never removed (its modules are unknown).
* Left: a test.pypi.org rehearsal of the redesign (done, `T.abfd`),
  then `Summary.md` and close with `T.abfd`.
