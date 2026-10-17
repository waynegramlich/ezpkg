# LLM Agent Context Log

## 2026-10-15: Where this stands (rewritten for the next session)

The design is in `Details.md` (items 1-11).  Everything is built,
tested and documented; this task is waiting on one more test.pypi.org
rehearsal and dogfood run, then its `Summary.md` and closing.

### History, briefly

* Created as `T.amda` (add missing dependencies, "are you
  developing?" question, import fingerprint).  Wayne then saw that a
  removed import matters too, renamed it `T.kdaiis` and redesigned it
  (2026-10-15).  The first design's code (`developing`,
  `development_question`, `with_dependencies`, `import_fingerprint`)
  is gone.

### The code (`ezpkg.py`)

* `install()` (no-argument form): `provide(asked)`, then under
  `EZPKG_APPROVE=write` `offer_ranges`, then export or
  `scan_imports(sync_dependencies(asked))`.
* `sync_dependencies`: fingerprint check against the program's record
  in `~/.ezpkg/develop/` (`development_record`, `keep`; fields
  `asked`, `warned`, `answer`), then `discrepancy`, then on a terminal
  `reconcile`, else the summary once per change on stderr.
* `discrepancy` builds a `Discrepancy` (dataclass: `arrange`,
  `target`, `pending`, `summary`, `changes`; fields include `guessed`
  and `uncommented`).
* `reconcile`: `See the discrepancy list? [o/a/n/d]` (`a`, `d`
  confirmed), per-item questions in line order (add y/n, remove
  y/n/k, ezpkg mypy comment y/n), then `provide` the additions
  (`expect=` refuses a wheel without its module), then ranges
  (`version_range`), then the changes display, `Make these changes?`,
  then one write, report lines, and `remember` of the ranged request
  so the next run does not fetch again.
* Helpers: `every_import`, `dependency_fingerprint` (includes
  `__version__`, so a new `ezpkg` re-checks every program),
  `dependency_lines`, `line_list`, `with_dependency_list`,
  `unimported` / `with_unimported` (`[tool.ezpkg] unimported`),
  `with_type_ignores`, `TYPE_IGNORE`, `MODULE_PACKAGES`,
  `wheel_modules`, `index_has` (asks the index before a guessed name
  is offered), `failure_reason` (`pip`'s `ERROR:` line), `choose`,
  `YES_NO`, `version_range`, `normal_name`, `read_program` /
  `write_program`, `exempt`, `uncovered_imports`.  `uv_setting` takes
  a `table`.
* `offer_ranges`: at `EZPKG_APPROVE=write`, after the date question,
  one question offering ranges to bare entries from the approved
  versions.

### Decisions beyond `Details.md`

* Line numbers are left out of the changes display when entries share
  a line (a one-line array).
* `import ezpkg` is never a dependency, but gets the author's mypy
  comment (an item of its own).  Standard library imports never get
  it: `mypy --strict` reports an unused `type: ignore` (checked).
* `version_range` caps: `<0.(x+1)` for `0.x`, `<(major+1)` for 1-9,
  none from 10.

### Tests (`ezpkg_test.py`)

* `InstallTest`: `synced_program`, `declared_now`, and tests for
  added, mypy comment, ezpkg comment, unused (remove/keep), order,
  optional import, no terminal, always/never, wrong guess (`decoy`
  wheel holds `elsewhere`), a name the index lacks, and
  `test_write_offers_ranges_for_bare_entries`.  The older write tests
  answer twice now (date, then ranges), or they hang until
  `answer_on_a_terminal`'s 300 s timeout.
* `MetadataTest`: `with_dependency_list`, `every_import` and the
  fingerprint, `Discrepancy` arranging and display, `failure_reason`,
  `version_range`, `with_type_ignores`, `wheel_modules`.
* Quick suite 2026-10-15: 273 tests OK, 18 skipped.  Full suite
  (`./ezpkg_test.py`): 273 OK, 9 skipped, 178 s.

### Dogfooding

* `~/ezpkg_dogfood/` (outside the project): `prog.py` (Wayne's copy
  of the Quick Start), `run` (the project's `ezpkg.py`, home
  `home/`), `run_testpypi` (the newest `release testpypi` build from
  test.pypi.org, home `home_testpypi/`, via `PIP_FIND_LINKS` and
  `PIP_CONSTRAINT`; refuses option-like arguments).  Questions need a
  real terminal; `> output 2>&1` only gets the warning.
* Found by dogfooding and fixed: a guessed name offered without
  asking the index; `pip`'s first stderr line (an old `.egg` warning)
  shown as the reason; `import ezpkg` without the mypy comment; a
  program never re-checked by a newer `ezpkg`.  Filed: `I.uedepi`.
* test.pypi.org once answered 404 for a just-uploaded release;
  `release_check.wheel_info` now retries 4 times, 10 s apart.

### Next

1. Wayne commits and pushes (everything is staged).
2. Start and approve the `testpypi` run (Wayne pre-approved
   test.pypi.org runs), then `./release_check.py testpypi`.
3. Wayne dogfoods `~/ezpkg_dogfood/run_testpypi`; to see the ranges
   offer, run `prog.py` with `EZPKG_APPROVE=write` (his `cowsay`,
   `coverage`, `pip` are bare).
4. Write `Summary.md` and close.  Then `I.wmau` (Windows and macOS),
   which must close before `T.utpat` (Wayne).

## 2026-10-17: Guessed names are proved before asking

* Wayne's dogfood: `import bogus` was offered and questioned, and only
  failed at the end.  PyPI's `bogus` is a stranger's source-only
  project.  And since `T.eui` the final fetch also asked for the `ezpkg`
  entry, which pypi.org lacks, so the failure named `ezpkg`, not `bogus`.
* Fixes (Wayne: do all three): `reconcile` fetches without the `ezpkg`
  entry this `ezpkg` meets; `EZPkg.prove(package, module)` runs before
  each guessed addition's question: `index_files` (replaces
  `index_has`; the PEP 503 page's file names) for "no package" and "no
  wheel, only source code", then a `download` into holding and
  `wheel_modules` for "does not provide".  A failure is one wrapped
  line, and no question.
* Tests: `test_a_wrong_guess_is_not_offered` (was
  `..._changes_nothing`), `test_a_source_only_package_is_not_offered`
  (`sourceonly-1.0.0.tar.gz` in the test index),
  `test_an_addition_does_not_fetch_this_ezpkg` (fails with the bug put
  back), and the index-lacks test's new wording.
