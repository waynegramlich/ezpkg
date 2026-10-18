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

## 2026-10-17: Wayne's dogfood, two findings

* Fixed: every `EZPKG_APPROVE=write` run stamped a new time, so it
  asked to change `exclude-newer` each run.  `gate` now keeps the old
  `# Resolved:` date (`EZPkg.resolution`) when the wheels equal the
  approvals, and says `approvals unchanged in ...`; `stamp` then has
  nothing to ask.  `test_write_stamps_the_date_into_the_block` extended
  (fails, by hanging on the question, with the fix taken out).
* Agreed, NOT built (Wayne: 1.1-1.4, 1.3b): when two or more entries
  would change, `reconcile`'s summary line and `See the discrepancy
  list? [o/a/n/d]` become

  ```
  ezpkg: prog.py: 3 entries in `dependencies` (line 5) need to be updated.
  Update them? [y=>Yes/n=>No/i=>Individually/a=>Always/d=>Don't ask again]
  ```

  * `y`: show the changes display once (anchored, as now) and write,
    with no "Make these changes?".
  * `n`: warn once per change, as today's `n`.
  * `i`: today's per-item questions, then "Make these changes?".
  * `a`: as `y`, now and from then on without asking, after "Really?"
    (`a` means Always in every `ezpkg` question; Wayne chose 1.3b over
    `a=>All`).
  * `d`: never ask about this program, after "Really?", as today.
  * One change: today's single-item question for it, no list question.
  * Guessed additions that fail `prove` are still reported and skipped.

## 2026-10-17: The batch question, built

* `reconcile` now proves guessed additions first (failures reported,
  not counted), then counts the entries that would change
  (`Discrepancy.updating`, from `rows`, which `changes` now formats).
  Two or more: `Discrepancy.needing` ("ezpkg: prog.py: N entries in
  dependencies (line 5) need to be updated.", plus the `ezpkg` mypy
  comment if needed) and `Update them? [y/n/i/a/d]`.  `y` and `a` make
  every change (removals included, never `k`), show the display, write,
  no "Make these changes?".  `i`, or one change: the old per-item
  questions (after the old `disagree` line), then "Make these changes?".
  A `n` to either "Really?" goes back to the question.
* `a` is recorded as `answer: "update"`, and then applies even a single
  change without asking (on a terminal only; no terminal still only
  warns).  An old record's `"always"` (show the list) now just asks.
* Only guessed names fail `prove`, so with none the count is free.
* Tests: `test_several_changes_are_one_question` (y with a misspelt
  third, n, i); `test_always_and_never_outlive_the_run` rewritten (a,
  "Really?" n, d); single-change tests lost their `o`.  `InstallTest`:
  157 OK, 2 skipped; quick suite 295 OK, 18 skipped.
* README: replacement for "Keeping `dependencies` in Sync" proposed in
  an HTML comment.
* Next: Wayne's verdict, commit, rehearse (also carries the kept
  resolution date).

## 2026-10-17: `~/ezpkg_dogfood/drive`, and what it found

* Wayne found the hand-run dogfood steps tedious, so `drive` (outside
  the project, beside `run`) runs them on a pseudoterminal in a
  temporary copy (Quick Start, fresh home, a private `pip.whl`),
  answers each scripted question, `y` to any download question, and
  checks output and `prog.py`.  Transcript `drive_output`, each step
  framed by 79-character `^`, `-` and `v` lines (Wayne's layout).
  `--until 1.4`, `--keep`.  Steps 1.1-1.11.
* Fixed from its first run (4 of 13 passed):
  * `providing(module, providers)`: Debian/Ubuntu strip `RECORD` and
    `top_level.txt`, so `packages_distributions` missed `python3-rich`
    and `attrs`, and `discrepancy` skipped `import rich` silently.  A
    distribution named as the module (or `MODULE_PACKAGES`) with no
    file listing at all now counts; used by `discrepancy` and
    `import_problems`.  (`Distribution.files` skips missing files, so
    the listings are read directly.)
  * `satisfied(requirement, cache)`: a copy in `EZPkg`'s own cache,
    put on `sys.path` earlier in the process, no longer counts.  It
    made `reconcile` skip the fetch and take ranges from Ubuntu's
    `requests` 2.31.0, while the next run fetched 2.34.2.
  * Control-C: `install()`'s no-argument form is now
    `install_declared`, and a `KeyboardInterrupt` there becomes
    `\nezpkg: interrupted, so prog.py stops here.` (`I.ffspo`).
* Left alone: a declared package with silent metadata that nothing
  imports is still never offered for removal (its modules are not
  known; guessing them could remove a needed one).
* Tests: `test_satisfied_ignores_the_cache`,
  `test_a_silent_distribution_provides_its_namesake`,
  `test_control_c_stops_with_one_line` (`MetadataTest`, 34 OK).

## 2026-10-17: The UX review changes this task's output

* `ux02`-`ux03` (see `T.abfd`'s `Context.md`) restyle the batch
  question and the changes display (line-numbered, `mypy` lines, no
  report lines) and make `a` silent.  Agreed, NOT built.

## 2026-10-18: `reconcile` reshaped by the UX review (see `T.abfd`)

* `T.abfd`'s `Context.md` (2026-10-18 entries) has the details; in
  short: the changes are listed (ranges from a silent `versions_of`
  fetch) before `Update them?`/`Update it?`; one change is asked like
  a batch (`k` offered for a lone removal); no "Really?" after `a`/`d`;
  a remembered `a` is silent; `n` says "Nothing changed. ...".
  Helpers `fetching`, `edit_for`; `Discrepancy.display(heading=)`,
  `needing(count, end)`.  Per-item questions remain behind `i`.
* An end-user's copy with an unimportable import is asked "Are you
  working on" every run and told whose mistake it is
  (`Discrepancy.stopping`).  Every edit restarts the program
  (`EZPkg.restart`).
