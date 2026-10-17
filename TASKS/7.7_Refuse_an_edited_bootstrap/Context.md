# LLM Agent Context Log

## 2026-10-16: Created

* From Wayne's dogfood: twice he edited `prog.py`'s bootstrap
  (`"choose pipx"`, `"choose pipxxx"`) and expected a complaint, but
  `EZPkg` only reports under `EZPKG_BOOTSTRAP=check` (6.12.2 of
  `T.fbanwiis`, `report_bootstrap`, `bootstrap_status`).  Wayne: an
  edit must ***never*** go undetected.
* Agreed items 1-5 of `Details.md`; "Still To Discuss" is Wayne's
  item 4, which needs more discussion.
* Where to hook it: the bootstrap calls `m.EZPkg().install(bootstrap=
  NAME)`, and only `install` knows the name, so the check belongs in
  `install` (Wayne spoke of `EZPkg.__init__()`; same idea).

## 2026-10-16: Written

* Wayne settled `Details.md`: textual comparison, adjusting for the
  paste's indentation; the "Still To Discuss" items as Claude
  recommended (layout, comments and stale copies pass; no check
  without `bootstrap=`).
* `ezpkg.py`: `OLD_BOOTSTRAP_TEXTS` (`nopip5`'s text, from `d6a7f11`;
  the current one is `find_bootstrap(QUICK_START)`; `nopip3`/`nopip4`
  named `alt_venv`, so unreachable); `bootstrap_refusal` (fingerprint
  decides; `difflib` line diff, `rstrip`ped, against the nearest text;
  `find_bootstrap` already dedents; at most 8 lines shown);
  `EZPkg.refuse_an_edited_bootstrap`, called by `install` when
  `bootstrap` is given, after the `EZPKG_BOOTSTRAP=check` report.
  Unreadable source (`python -c`) is not checked.
* `EZPKG_BOOTSTRAP=unchecked` skips it, printing a line every time.
  Needed by `bootstrap.py`, whose copies spell `PACKAGE`/`JSON_API`;
  set in `run_bootstrap_case` and `bootstrap.run_tests`.  Needs
  Wayne's approval.
* Tests: `test_an_edit_is_refused_where_it_is`,
  `test_layout_comments_and_stale_copies_pass`,
  `test_a_wrong_name_or_no_bootstrap_is_refused`,
  `test_install_stops_on_an_edited_bootstrap`.  Quick suite: 277 OK,
  18 skipped.
* README: the new "Never edit the bootstrap" paragraph is proposed in
  an HTML comment.
* Dogfood: `~/ezpkg_dogfood/run` (the project's `ezpkg.py`) refuses
  Wayne's `"choose pipxxx"` at line 33.  `run_testpypi` will not until
  a rehearsal publishes this.

## 2026-10-16: Exact trimmed lines (Wayne)

* Wayne: compare exact lines after trimming, so only the paste's
  indentation is forgiven; a comment or a space is an edit.  Show each
  difference line by line with a `|` under the first differing
  character.  `EZPKG_BOOTSTRAP=unchecked` approved ("very few would
  know how to use it").
* `ezpkg.py`: `trimmed`, `published_bootstraps`, `bootstrap_name`
  (exact match), `bootstrap_refusal`, `bootstrap_differences` (pairs
  changed lines, then `(not in nopip6)` / `(missing after line N)`; at
  most 6, then `... and N more`).  `bootstrap_status` (and so
  `EZPKG_BOOTSTRAP=check`) uses `bootstrap_name` too.  The fingerprint
  remains only as `BOOTSTRAPS`' key.
* Shown to Wayne on `quick_start.py`: extra space, extra, deleted and
  changed character, added comment, added line, deleted line; a fully
  indented paste passes.  Syntax errors never reach the check.
* Tests: `test_the_four_states` (stale now from the real `nopip5`
  text), `test_an_edit_is_refused_where_it_is` (exact three lines),
  `test_only_indentation_and_staleness_pass`,
  `test_added_and_missing_lines_say_where`,
  `test_published_texts_are_registered`.  Quick suite 279 OK, 18
  skipped.
* README proposal (HTML comment) rewritten to match.  Rehearsal
  deferred until the comparison is settled (Wayne).
