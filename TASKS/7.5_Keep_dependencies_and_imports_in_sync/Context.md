# LLM Agent Context Log

## 2026-10-15: Built

* `ezpkg.py`: `sync_dependencies` (called by `install()` before
  `scan_imports`), `developing` (records in `develop/`, keyed by the
  program path, holding `import_fingerprint`, 8 hex digits, and the
  answer), `development_question` (Wayne's wording; `a` and `d`
  confirmed), `uncovered_imports` split out of `import_problems`,
  `exempt`, `provide(..., expect=)` refusing a wheel that lacks its
  module (`wheel_modules`) before anything is unpacked,
  `with_dependencies`, `with_type_ignores` (Wayne's tweak: copy the
  author's `# type: ignore` comment onto added imports, only if the
  other declared imports carry one; added even past 79 columns),
  `MODULE_PACKAGES`, `read_program`/`write_program` (shared with
  `stamp`).  The bootstrap is unchanged.
* `always` acts only when the imports change, so a failing guess is
  not refetched every run.
* Tests: 5 in `InstallTest` (pty-answered), 4 in `MetadataTest`, and
  a `decoy` wheel in the test index (holds `elsewhere`).  Mutations of
  the wheel check, the answer handling and the comment copying each
  fail a test.  Full suite (`./ezpkg_test.py`): 264 tests, OK, 9
  skipped, 146 s.
* Known gap, by design: the first run of a program only records, so a
  brand-new program still needs step 4 by hand.
* Tests that run programs inherit the caller's controlling terminal;
  under Claude's shell there is none.  Run from Wayne's terminal, a
  fingerprint change with a missing import could ask there (as the
  download prompt already could).
* `README.md`: three proposals in HTML comments, awaiting Wayne.

## 2026-10-15: Reworked to Wayne's design (`Details.md`)

* Renamed from `T.amda`.  The first build (add-only, "are you
  developing?") was replaced: `sync_dependencies` now compares
  `dependencies` with the target (`Discrepancy`, built by
  `EZPkg.discrepancy`), asks o/a/n/d, then per addition (y/n) and
  removal (y/n/k), shows the changes with anchors
  (`Discrepancy.changes`) and asks once, then fetches and writes.
* New helpers: `every_import` (optional imports marked),
  `dependency_fingerprint`, `dependency_lines`, `line_list`,
  `with_dependency_list` (replaced `with_dependencies`), `unimported`,
  `with_unimported`, `choose`, `YES_NO`; `uv_setting` takes a `table`.
  Records in `develop/` hold `asked`, `warned` and `answer`.
* A one-line array keeps all entries on one line, so the display's
  anchors can share a line number: `move (3) "widget", line 3
  "sprocket"`.
* Tests: 8 end-to-end in `InstallTest`, 3 unit in `MetadataTest`.
  Quick suite: 268 tests OK, 18 skipped, 154 s.
* `README.md`'s "Keeping `dependencies` in Sync" still describes the
  first design and needs redoing.
* README rewritten for the new design and applied (Wayne edited step
  4).  Open: the 85-column question line (choices on their own line?),
  and "which is why step 4 lists it" in the paragraph after "That's it".

## 2026-10-15: Dogfood fixes

* Wayne's dogfood (`import bogus_package`): the guess was offered and
  fetched before anyone knew it did not exist, and the failure showed
  `pip`'s first line, a DEPRECATION warning about an old `.egg` in the
  system Python, instead of its `ERROR:` line.  Fixed: `index_has`
  asks the index (PIP_INDEX_URL, else PyPI, then extras) before a
  guessed addition is offered, and says "no package of that name is on
  the index" instead of asking; `failure_reason` picks the `ERROR:`
  line.  Tests: `test_a_name_the_index_lacks_is_not_offered`,
  `test_failure_reason_finds_pips_error`.
* The `yaml` case worked in Wayne's run: `"PyYAML"` added, the mypy
  comment copied.  He dogfooded on the project's `quick_start.py`,
  which he will restore.
* Wayne's dogfood, `import ezpkg`: correctly not a dependency, but it
  needs the author's `mypy` comment too (`mypy` cannot see
  `~/.ezpkg`).  Now an item of its own (`Discrepancy.uncommented`,
  `pending()`).  Test: `test_an_ezpkg_import_gets_the_mypy_comment_alone`.
* A program already looked at was never re-checked by a newer `ezpkg`
  with new rules; `dependency_fingerprint` now includes `__version__`.
* `I.uedepi` filed: a `uv` export drops an `ezpkg` the program imports.
* Quick suite: 271 tests OK, 18 skipped.
