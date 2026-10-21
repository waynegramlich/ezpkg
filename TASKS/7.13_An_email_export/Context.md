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
