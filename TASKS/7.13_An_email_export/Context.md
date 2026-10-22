# LLM Agent Context Log

## 2026-10-20: Built (Wayne: "grind away on the `email` option")

* Why: a developer's `checksums` hold only what arrived on their own
  computer, so a package another computer alone needs (`tqdm`'s
  `colorama` on Windows) is refused there by `verify`.  Wayne's
  answer: a third export, `email`, which does the thorough work at a
  release.
* Measured: `pip download --platform win_amd64` (24.0 and 26.2.2)
  judges markers by this machine and never fetches `colorama`; `uv
  lock --script` resolves for every computer and lists every wheel's
  SHA-256.  So `email` needs `uv` on the developer's computer (refused
  with a plain line without it); the recipient needs only Python.
* Code: `EXPORT_FORMS` adds `"email"`; `release` names it
  `prog-X.Y.Z.py`; `build_email` locks a pinned, bootstrap-less copy
  in a scratch directory (`lock_script`, now shared with `build_uv`,
  with the `exclude-newer` date and a retry without it), checks the
  lock with `lock_mismatches`, and writes the program (bootstrap kept)
  with `checksums` from `everywhere_approvals`: the author's rows
  unchanged, plus one row per package the lock adds (a pure wheel, or
  the first compiled one with its `tag:`, version-only elsewhere as in
  S2.4d).  The program's own `checksums` are untouched.  Template
  `exports` line mentions `"email"` (`T.ept` may reword).
* Tests: `test_export_email_approves_what_other_computers_need` (index
  packages `paned`, needing `shutter` on `win32` only),
  `test_everywhere_approvals_adds_what_other_computers_need`; form
  lists updated.  Dogfooded against pypi.org with `tqdm`: the copy
  gained `colorama==0.4.6 id:4f1d9991f5acc0ca`, and ran as a new end
  user on Linux.
* README: proposals in `<!-- Claude: -->` comments (intro, `exports`
  bullet, Releasing with a new "Using `email`", Conclusion).

## 2026-10-20: Proved on Windows (`email_check.yml`)

* `email_check.py` (`build DIR`, `friend DIR OUT`) and
  `.github/workflows/email_check.yml` (made by a background agent):
  Linux builds a `tqdm` program and its `email` release with this
  tree's `ezpkg.py`; friends on Windows, macOS and Linux, Python 3.11
  and 3.14, run both as new end users (`CI=1`).
* Run 39546669421 (commit `55b8af0`): all 7 jobs passed.  Windows:
  `prog.py` refused (3.3 s on 3.14, 4.9 s on 3.11), because
  `colorama-0.4.6-py2.py3-none-any.whl` is not in its `checksums`;
  `prog-1.0.0.py` ran (1.8 s, 3.2 s), listing pip, colorama, tqdm.
  macOS and Linux ran both.  Build job 13 s in all.
* Cost: one `uv lock` at release (0.8 s locally), and `uv` on the
  developer's computer; nothing extra for the friend.
* Side finding: the Windows friend's refusal reads "`prog.py` could
  not get its software packages ...: colorama-...whl is not in the
  `checksums` of Part 1 of prog.py; running the program as its
  developer brings them up to date", which is developer talk.
  Proposed for `end_user_failure` (`I.ffspo` style): "`prog.py` needs
  colorama 0.4.6 on this computer, which its author did not approve,
  so `prog.py` did not run.  Its author can send a newer `prog.py`."
  Not built.

## Open (Wayne, 2026-10-20: "too tired"; decide tomorrow)

1. Wayne's idea: three settings instead of `exports = [...]`:
   `# email_export = true`, `# zipapp_export = true`,
   `# uv_export = true`.  Claude's view, given in chat:
   * hyphens to match `auto-dependencies` (`email-export`, ...);
   * `email` on by default, `zipapp` and `uv` off;
   * then "Each setting is shown at its default" (template) breaks
     (`release` already breaks it): either change the rule to "each
     line shows what removing its `#` does" (`# email-export =
     false`, `# zipapp-export = true`, `# uv-export = true`), or keep
     it and make people edit `false` to `true` too.  Wayne undecided.
   * The order question (`EXPORT_FORMS`) goes away: built in a fixed
     order, email, zipapp, uv.
   * Small change: `Settings` fields, `release`, template, about 4
     tests, `email_check.py` (writes `exports = ["email"]`).
2. The end-user refusal wording above.
3. README proposals (`<!-- Claude: -->`): the `email` ones (intro,
   `exports` bullet, Releasing and "Using `email`", Conclusion) wait
   on item 1; the Security section is unread.
4. Later: warn at release when a compiled package has no wheel for some
   computer or Python that `requires-python` admits; an `email` step in
   `ux/drive.py`; whether `email_check.yml` joins `check.yml` or
   `release.yml`.

## 2026-10-21: Cross-platform `zipapp`; README comments

* Wayne: cross-platform resolution happens at release, and the
  README's "just email it" claim gets toned down.  `exports` array vs
  one line per form is a lower-level choice (Wayne: either is fine).
* Built: with `uv` installed, a `zipapp` carries the pure packages
  only other computers need (`elsewhere_trees`: fetched by the lock's
  URL, SHA-256 checked, unpacked into the cache; a compiled one is
  named in one line, not refused).  Without `uv`, one line says the
  `.pyz` carries only this computer's packages (Wayne: no `uv`
  requirement for `zipapp`).  `lock_everywhere` is shared with
  `build_email`.  Test `test_export_zipapp_carries_what_other_computers_need`.
* README `<!-- Claude: -->` comments (2026-10-21): intro "send the
  release, not `prog.py`"; "What are packages" order and the new
  computers-differ paragraph; Using `zipapp`; Conclusion rewording.

## 2026-10-21: `ezpkg` fetches `uv` itself

* Wayne: the developer never installs `uv`; an installed one recent
  enough is used, else `ezpkg` downloads it, invisibly.
* Built: `EZPkg.uv()`: `find_uv` (now also requires `UV_FLOOR`
  0.6.0, measured: the export tests pass with 0.6.0 and 0.8.0), else
  the newest `uv-*` tree in `versions/`, else `download(["uv>=0.6.0"],
  ["--no-deps"])`: `pip` picks this computer's wheel, `unpack` keeps
  it, the binary `uv-X.data/scripts/uv[.exe]` gets its execute bit.
  `EZPKG_UV=fetch` (tests only) passes over an installed `uv`.  Used
  by `build_uv`, `build_email`, `elsewhere_trees`.  Test
  `test_uv_is_fetched_once_when_none_is_installed`.
* Local end to end (`email_check.py build`/`friend`, real pypi.org):
  fetched `uv` 0.13.4 (about 4 s), colorama in both releases, all three
  ran.  `email_check.yml` widened to builds on 6 runner kinds plus
  Alpine; needs Wayne's commit before it can run on GitHub.

## 2026-10-21: Deleting `prog.py.release` builds a release

* Wayne's design: no file to create (PowerShell has no `touch`), one
  to delete.  A developer run with no `prog.py.release` builds every
  form (default `exports` is all of `EXPORT_FORMS`, now ordered
  email, zipapp, uv) into `prog_builds/X.Y.Z/`, writes
  `prog.py.release` (TOML: version, date, folder, built, skipped), and
  then the program runs (restart after the release's edits, allowed a
  second time: `restart(after_release=True)`).  The first developer
  run therefore builds 1.0.0.  Version: `release` if it differs from
  Part 1's `released`, else `next_release` (last number + 1).  Wayne:
  stress that versions can be reset any time; only PyPI needs care.
* A failed release says why, writes no `.release`, and the program
  runs; the next run tries again.  A `zipapp` refused for compiled
  code is skipped with a line.  No `checksums` (nothing fetched) is no
  longer an error for `email`/`zipapp`.  A program with no pasted
  bootstrap builds no forms (one line), and the release still counts.
* `release_due`, `release_path`, `next_release`; tests
  `test_deleting_the_release_file_builds_the_next_release`,
  `test_next_release_adds_one_to_the_last_number`; helper `no_release`.
  `email_check.py build` now relies on the first developer run's
  release.  README proposals in `<!-- Claude: -->` comments (Enabling
  step 3, Settings bullets, Releasing).
* Not yet changed: `T.abfd`'s `Details.md` "Release" bullets (Wayne's
  file); `ux/drive.py` developer steps (2.x) will now see a release on
  the first developer run.

## 2026-10-21: The end user's refusal is plain (open item 2 done)

* `verify` raises `Unapproved` (a `RuntimeError` carrying `pin`) for a
  wheel not in `checksums`; `end_user_failure` turns it into
  "`prog.py` needs colorama 0.4.6 on this computer, which its author
  did not approve, so `prog.py` did not run.  Ask its author for its
  release, and try again." plus the `last_failure.txt` note.  The
  developer's line is unchanged.  README "Not Approved" bullet (Wayne).
* Releases off until `exports` is uncommented: built the same day
  (next entry).

## 2026-10-21: Releases are off until `exports` names a form

* Wayne: no `prog_builds/` on a first run.  `Settings.exports`
  defaults to `()`, and `release_due` returns "" while it is empty
  (an explicit `exports = []` too); otherwise unchanged (no
  `prog.py.release`, a new `release`, or a deleted record).
* `SETTINGS_TEMPLATE`: the releases paragraph says they are off until
  a `#` goes from an `exports` entry; `exports` comes before
  `release`, as Wayne's README draft has it, written `exports = [` ...
  `]` left open (valid TOML, the empty default) with one commented
  line per form, so each form is one `#` to remove.  No
  `exclude-newer` setting (the code reads none).
* Tests: `test_deleting_the_release_file_builds_the_next_release`
  starts from the template (no release, no record, no folder), then
  uncomments its entries (1.0.0, every form).
  `test_a_newer_bootstrap_is_told_once_and_replaced_at_release` now
  sets `exports = ["zipapp"]`, whose build fails in that harness
  (nothing from a cache), so it checks the bootstrap and `ezpkg`
  entry replaced and "was not released", no longer `released`.
  `read_settings` case `exports = []`.
  `test_a_release_happens_once_per_value` and
  `test_a_source_ezpkg_leaves_the_ezpkg_entry_alone` add `exports =
  ["email"]` (no pasted bootstrap, so nothing is built).  Quick suite:
  318 tests OK (16 skipped).
* `email_check.py build`: an empty `prog.py.toml`, a run that fills it
  and builds nothing, then the template's `exports` entries
  uncommented, a run that builds 1.0.0, and one that only runs.
  Passed locally (pypi.org, `uv` fetched).
* `ux/drive.py` sets `exports` only in its release step, so its
  other developer steps again build nothing (not rerun).  README is
  Wayne's.

## 2026-10-21: The run that fills `prog.py.toml` edits nothing

* Wayne: never edit a developer's code before telling them ("How DARE
  you edit my code").  The run that fills an empty `prog.py.toml`
  (`EZPkg.filled`) writes no `dependencies`, `checksums` or date into
  the program; `reconcile` still fetches the new imports' packages for
  that run.  The template's `{note}` beside `auto-dependencies`
  (`first_run_note`) says what the next run changes, naming the
  additions (`name_the_additions` rewrites it in that run, only if the
  file is unchanged), and says to delete it.  One printed line points
  to it.  Tests `test_an_empty_settings_file_is_filled`,
  `test_the_filling_run_names_what_the_next_run_adds`; quick suite 319
  OK; `email_check.py build` passed locally.
* Open: `auto-dependencies = false` stops `dependencies` edits only;
  `checksums` and the date are still recorded (Claude's #3, moving
  them to release time, not yet discussed).

## 2026-10-21: Design (Wayne): the developer's `prog.py` is never edited

Decided, being built.  Supersedes the first-run note above.

* `EZPkg` keeps what it works out in the program's development record
  in `~/.ezpkg/develop/` (the stash), never in `prog.py` or the `.toml`:
  the entries for imports Part 1 does not declare, the `checksums`
  (and `tag:`s), the frozen date, the last released version.
* Part 1 is the developer's own input: hand-written entries (ranges,
  comment-kept ones) are read, never written or removed.  A developer
  run asks for Part 1's entries plus the stash's (by name, Part 1
  wins); `reconcile` and `record_approvals` write the stash; no
  restart is needed.
* No stash (deleted `~/.ezpkg`, another computer, a moved program):
  seed it from the newest release in `prog_builds/` (its `email` copy
  holds `dependencies`, `checksums`, date), else start fresh.
* Upgrade: a `.toml` setting, `upgrade = true`: every run fetches the
  newest versions; comment it out again to freeze at that run's date.
  Replaces "delete the `exclude-newer` line".
* A release writes only its copies, never `prog.py` (Wayne: release
  copies only): merged Part 1 with ranges for bare entries,
  `checksums`, date, and a current bootstrap where `bootstrap =
  "update"`.  The version record moves to the stash (fallback: the
  newest `prog_builds/` folder).
* The first-run note (`first_run_note`, `filled`) goes: nothing is
  edited, so there is nothing to announce.
* End users are unchanged: they run a release copy, whose Part 1 is
  complete.  The working `prog.py` runs only for its developer.

## 2026-10-22: The plan, revised (Wayne)

* Agreed, not yet built: everything `ezpkg` works out for a
  developer's program (undeclared entries, `checksums`, date, last
  release) is kept in its `~/.ezpkg/develop/` record for now; where it
  finally lives is revisited later (a file beside `prog.py` that
  version control can keep is one candidate).
* Undecided: whether `prog.py` itself is never edited.  Keep the code
  that edits Part 1 (and its tests) until that is decided; only switch
  it off.
* If the builds folder stays, `prog_builds/` becomes `prog.py.builds/`,
  so `ls` lists `prog.py`, `prog.py.builds`, `prog.py.release` and
  `prog.py.toml` together.
* New questions: garbage collection of `develop/` records and old
  builds, and git/hg retention of the builds and of the stash.
* Wayne (2026-10-22): go ahead with the three phases (1. stash, edits
  switched off by one constant; 2. `prog.py.builds/`; 3. `cull`), with a
  progress report after each.  Garbage collection is not solved (an end
  user could hold a lot in `~/.ezpkg` unknowingly).  git/hg retention
  deferred, but probably to be encouraged.  README left alone; edited
  together later.

## 2026-10-22: Phase 1 built: the stash

* `EDIT_PROGRAM` (off; `EZPKG_EDIT_PROGRAM=on` for tests) chooses.
  Off: `approved`, `declared_date`, `released` and `declared` read the
  stash (`stash`, `put_stash`; Part 1's date wins if written);
  `record_approvals` and `reconcile` write it; Part 1's own entries are
  never removed (`discrepancy` keeps them); no `mypy` comments, no
  restart.  Seeded once from Part 1, else `seed_from_builds`.
  `upgrade` setting (template's last line).  A release builds from
  `staged` (via `program_text`/`rewrite`), records `released` in the
  stash.  `stale` keeps a record holding a stash.  `builds_path` names
  `prog_builds/` in one place, ready for phase 2.
* Template wording changed for the stash (`T.ept` is Wayne's to edit).
* Tests: 18 marked `@editing`; `run_as_developer` edits (end-user tests
  need Part 1 approvals); new `test_the_stash_keeps_what_part_1_does_not_say`,
  `test_upgrade_takes_the_newest_versions`,
  `test_a_release_copy_carries_the_stash`,
  `test_an_import_newer_than_the_stash_date_says_upgrade`.  Quick suite
  323 OK (16 skipped).  `email_check.py` now expects `prog.py`
  unedited and runs only the releases as a friend.
* Not done: `ux/drive.py` developer steps still expect edits (stale).
