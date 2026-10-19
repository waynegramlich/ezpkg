# LLM Agent Context Log

## 2026-10-16: Designed, not built

* `Details.md` holds the agreed design: "The Download Prompt" (three
  lines, onus on the author) and "Keep or Delete" (`n` on a first run
  deletes `~/.ezpkg`; if in doubt, delete).  Nothing is built; Wayne's
  dogfood `output` still shows the old messages, which confused him
  until Claude said so plainly.
* Possible split (asked, not answered): first the messages (the
  three-line question, `y`/`n` endings, the decline line instead of
  `fetch packages failed: RuntimeError('declined: ...')`), which need
  no bootstrap change; then capturing `pip`'s output and handing it to
  `EZPkg.__init__()`, which makes a new bootstrap (`nopip7`) and must
  follow `T.eui`'s rehearsal.

## 2026-10-17: Part 1, the messages, built

* Wayne: add the three lines now, to debug the flow of questions.
* `consent` asks Details' "Keep or Delete" wording (singular forms
  for one package), via `program_name()` and `shown()` (`~` except on
  Windows).  `?` adds the one-line "software package" explanation, then
  `details` as before.  When standard error is not a terminal, the
  question and the answer are copied to it.
* `announce` is gone: no list before the question.  After unpacking,
  every path prints `ezpkg: N packages stored in ~/.ezpkg.`
* `gate` raises `Declined` (a `RuntimeError`); `install()` with no
  arguments turns it into `SystemExit("ezpkg: nothing was installed, so
  prog.py stops here.")`, which the bootstrap's `except Exception` lets
  through, so no bootstrap change.
* Not built (part 2): capturing `pip`'s output, `n` on a first run
  deleting all of `~/.ezpkg`, README "Download Prompt".
* Tests: `PROMPT` is now the prompt's tail; the old-wording tests
  follow; `test_a_dependency_is_shown_as_having_come_along` became
  `test_a_dependency_counts_as_a_package`.

## 2026-10-17: `nopip7`, `pip`'s output captured

* Wayne: the first line a stranger sees should be `prog.py needs ...`.
  Chose `m.EZPkg(pip=n)` (#1) over a module attribute, with
  `EZPkg.__init__(root, pip, **later)` ignoring unknown keywords so a
  newer bootstrap still reaches `install` and switches (`T.eui`).
* `nopip7`: `m = n = None`; `n = subprocess.run([... "ezpkg"],
  check=False, capture_output=True, text=True)`; new line
  `if n.returncode: raise RuntimeError(n.stderr.strip()[-300:])`
  (quick_start.py line 48), since a failed install leaves no `EZPkg`
  to report it; `m.EZPkg(pip=n).install(bootstrap="nopip7")`.
  Fingerprint `670d697c...` in `BOOTSTRAPS`; `nopip6`'s text in
  `OLD_BOOTSTRAP_TEXTS`; `nopip7` case in `bootstrap.py`;
  `SHIPPING`/`FAST_CASES` follow.  Stored as `self.pip_run` (`pip` is a
  method); `first_run()` adds `pip`'s lines under `?`.
* README: the bootstrap copies follow; bullets for `stdout=2` and
  `m.EZPkg()` proposed in HTML comments.
* `~/ezpkg_dogfood/run_testpypi --local` (Wayne): builds the project's
  wheel; its own notes go to `/dev/tty`, `release.py`'s output is
  hidden, and replacing `ezpkg` removes `__pycache__` too.
* Still part 2: `n` on a first run deleting all of `~/.ezpkg`.

## 2026-10-17: A terse `?`, and the dogfood cycle

* Wayne: `?` was "way, way, way too verbose".  Now `?=>Explain`, one
  line "Software packages are code from PyPI, the Python Package
  Index:", then `  N. name version: summary`, cut to 80 with `...`
  (`details(wheels, width)`; `summary` no longer cuts at 60).  Dropped
  (Wayne not yet asked): asked-for/came-along, `pip`'s captured lines
  (`first_run` removed; `pip_run` kept), size, SHA-256, the index.
* Dogfood (`~/ezpkg_dogfood/run_testpypi`, outside the project):
  `--local` rebuilds only when `ezpkg.py`'s SHA-256 changes, and then
  deletes `ezpkg.py` too (`pip install -t` never overwrites a file);
  plain mode refuses a `prog.py` bootstrap the test.pypi.org `ezpkg`
  does not know; `--time` times `prog.py` alone.  Measured: first run
  5.5 s (with the question), second run 0.13-0.18 s.  The 2.4 s Wayne
  saw was the harness reinstalling `ezpkg` every run.  Wayne: a win.

## 2026-10-17: Rehearsed; next

* `0.0.1.dev202610171830` passed every `check.yml` job, `--console`
  ones included, once `release_check.py`'s `PROMPT` became `=>Explain]`
  (the old `go ahead?` never appeared, so nothing answered).  The logs
  show the three lines, Windows' full path, the 5-minute no and the
  "stops here" line on all three systems.
* Next (Wayne: the focus after a few other issues):
  1. `n` on a first run (`self.pip_run is not None`) deletes all of
     `~/.ezpkg`; on later runs only the new downloads.
  2. README "Download Prompt" (about lines 130-160) rewritten to match,
     proposed in HTML comments; also Wayne's verdict on the `stdout=2`
     and `m.EZPkg()` bullet proposals already there.
  3. Ask Wayne which of the four things the terse `?` dropped come
     back (Claude suggests only marking packages that came along).

## 2026-10-17: The UX review (`ux/`), in progress

* Wayne reviews the user experience from `~/ezpkg_dogfood/drive`'s
  output: each step is also written to `ux/uxNN_NAME.txt` (git- and
  hg-ignored, but the files are `hg add`ed by name, so Claude
  checkpoints before and after each of Wayne's edits; a `drive` rerun
  overwrites them).  Wayne edits a file into the output he wants;
  Claude answers with issues by file and line.  Nothing built yet:
  the code still prints the old wording.
* `ux01_Baseline.txt` (first run) is agreed, lines 5-11:
  "`prog.py` needs to save 1 software package, chosen by its author or
  needed by them, into a directory called `.ezpkg` in your home
  directory.  If you do not trust the author of `prog.py`, answer `n`
  and the directory will be immediately removed.  Retain the `.ezpkg`
  directory and run `prog.py`?" / `[y=>Yes|n=>No|a=>Always|?=>Explain]:
  y` / "ezpkg: 1 software package stored into the newly created `.ezpkg`
  directory in your home directory."  Exact singular/plural, not "(s)".
* Wayne's decisions: `|` separators and `]:` in every `ezpkg` question
  (`/n` reads as newline); "in your home directory", but the full path
  when `EZPkg` was given another root; first run `n` removes `.ezpkg`
  entirely (build it, this task's part 2); a later run says something
  like "the N recently downloaded software packages will be removed"
  (to be written into `ux03` lines 5 and 16); the `?` text stays.
* Waiting on Wayne:
  1. Line 5 has no `ezpkg:` prefix, line 10 does: intended?
  2. New `drive` steps testing every answer to the download question
     (Wayne's #6): `?`; `x` (Claude: ask again); bare Enter (Claude:
     no); `n` first run; `n` later run; `a`; Control-C (1.10 exists);
     Control-D; the 5-minute timeout left out.  Shall Claude add them?
* Then `ux02` and `ux03`, where Claude noted: `ux03` 5-8 asks again
  for the 7 packages 1.2 stored (cause unknown); `ux03` 16-19 a second
  download question in one run; `ux03` 22 and 25 show the kept
  `requests` twice; `ux02` 17 "its import of requests, yaml".
* Also open, from `T.kdaiis`: the README proposals at `README.md`
  319-375 (batch question) and 376-382 (range sentence); Wayne's R1
  (silent packages never offered for removal) and R2 (no cap for
  `rich>=15`) accepted.

## 2026-10-17: `ux/` is in git

* Wayne changed his mind: `ux/` is tracked by git (staged) and hg, no
  longer ignored by either.  The ux files lost their `^^^` and `vvv`
  frame lines (`drive` now writes them without; `drive_output` keeps
  the frames, since it holds every step).  A `drive` rerun still
  overwrites Wayne's edited files, so `git diff ux/` shows where the
  real output departs from the agreed one.

## 2026-10-17: `ux01`-`ux03` agreed, NOT built

* The files in `ux/` are now the target output (Wayne: "everything
  looks great").  `ux04` (1.4 Batch n) is `drive`'s real output
  rewritten in the same style by Claude, not yet reviewed.  Nothing in
  `ezpkg.py` is built to them yet; `git diff ux/` after a `drive`
  rerun shows what is left (commit Wayne's edits first: a rerun
  overwrites them).
* Conventions, from Wayne's edits:
  * No `ezpkg:` prefix on these lines.  Backticks around names.  `|`
    separators and `]:` in every question.
  * Paragraphs wrapped at print time (`textwrap`) to the narrower of
    the terminal and 79 columns, since the program name's length is
    unknown.  Lines that cannot wrap (a long `mypy` line) run long.
  * "N package(s)" is literal: the count, then `package(s)`, for any N.
  * Explanation paragraph, blank line, then the question.
* First download (`ux01`): Wayne's 4-line paragraph ("The author of
  `prog.py` has selected some software packages from the internet.
  If you agree, they will be retained ...").  It deliberately does not
  say they are already downloaded: "retained" is true, and nothing runs
  and everything goes on `n`.  Then `Retain the `.ezpkg` sub-directory
  and run `prog.py`?`.
* After the `y`: "The following N package(s) are now installed in the
  `.ezpkg` sub-directory:", then `1. name version: Summary` per package
  (metadata `Summary`, cut to 79 with `...`, as `details` does for
  `?`), then "The `.ezpkg` sub-directory is managed by `EZPkg`
  (https://pypi.org/project/ezpkg/)." (wrapped).
* Later downloads are never asked about (Wayne: the person has bought
  into downloads), and only new packages are counted and listed
  (`ux02`; the real run counted 7, including the stored `cowsay`).
* Changes display (`ux02`, `ux03`): "Changes made to `prog.py`:" (after
  `y`/`a`, no further question) or "Changes to be made to `prog.py`:"
  (before "Make these changes?").  Each line `NN:` (colon-aligned, the
  line number in the file after the change; a removed line has a blank
  number), a marker column (`add`, `remove`, `mypy`, or none for an
  anchor) and the line's text.  `mypy` lines show the whole import with
  its new comment; `k` shows the added `[tool.ezpkg]` lines.  No report
  lines after the display ("added ...", "kept ... as unimported").
* `a` to the batch question: the changes are made silently (Wayne);
  today it shows the display.
* Removing imports must never ask a download question (`ux03`; the
  real run asked twice, a bug).
* Done today: `quick_start.py`'s last line (and `QUICK_START`, README
  86 and 106) is `The cow above was drawn by cowsay 6.1.`; Part 5, so
  no new bootstrap.
* Next: Wayne reviews `ux04`; then the remaining `drive` steps
  (1.4b-1.11) and the extra download-answer steps (`?`, `x`, Enter,
  `n` first and later run, `a`, Control-D); then build.
* `~/ezpkg_dogfood/` deleted (Wayne).  `drive` is now `ux/drive.py`
  (in git): it fetches its own `pip.whl` with `pip download` and writes
  `ux/drive_output.txt` (ignored); `--until 1.1` passed.  `run` and
  `run_testpypi` are gone; `drive` replaced them.
* So the dogfood still awaited elsewhere (`T.eui` and `T.reb`: the
  `zipapp` and `uv` exports, with and without `import ezpkg`;
  `T.kdaiis`: the ranges offer under `EZPKG_APPROVE=write`) becomes new
  `drive` steps.  Older notes naming `~/ezpkg_dogfood/` are history.

## 2026-10-18: `ux01` built, with `pip` and `ezpkg` listed

* Wayne: on a first run the bootstrap has already stored `pip` and
  `ezpkg`, and `n` removes them too, so hiding them "feels like we are
  hiding something".  Agreed (#1-#5): list them first, `pip` marked
  `(used by `EZPkg`)` before its summary (so a cut keeps the mark);
  `?` lists the same packages; only what this run stored (later runs:
  only the new downloads); a switched-to `ezpkg` (`T.eui`) is listed
  as an arrived wheel anyway.
* Built in `ezpkg.py`: `columns`, `wrapped`, `cut`, `metadata_fields`
  (headers end at the first blank line), `LINE_WIDTH` 79, `HOME_PAGE`;
  `EZPkg.metadata`, `bootstrapped` (only with `pip_run`, once:
  `told`), `described`, `place`, `listing`; `details` uses `described`
  (sorted by normal name, metadata `Name` spelling); `consent` asks
  `ux01`'s paragraph once, then the question with `|` and `]:`;
  `provide` prints `listing` (built before `unpack` moves the wheels)
  instead of `ezpkg: N packages stored in ...`.
* `ux/drive.py` now does a real first run: no `PYTHONPATH`, no
  pre-fetched `pip.whl`; the bootstrap fetches `pip` from pypi.org and
  installs a `release_wheel` of `ezpkg.py` (version `__version__`)
  via `PIP_FIND_LINKS`.  `first_run_again` removes the whole cache.
  Step 1.1's output equals `ux01` except the new list lines.
* NOT built: `n` on a first run removing `.ezpkg` (which `ux01` line 7
  promises); later downloads not asked (`ux02`); the rest of `ux02`-`ux04`.

## 2026-10-18: `~/.ezpkg` in every message; `ux01` built

* Wayne: PowerShell understands `~`, so user-facing text says
  `~/.ezpkg`, not "a sub-directory called `.ezpkg`".  On Windows the
  full path (`shown`), since `cmd.exe` and Explorer do not ("ugly, but
  so is Windows").  No "(in your home directory)": redundant (Wayne).
  `place()` is now `` `shown(root)` `` for every root.
* Wayne's line 15: `` `ezpkg` (HOME_PAGE) manages `~/.ezpkg`. `` then a
  blank line (the list ends with one, wherever it appears).  `pip` is
  marked `(used by `ezpkg`)`.  Names keep the author's capitalisation
  (`PyYAML`), from the metadata.
* The list counts only packages not already unpacked (`ux02` had
  counted the stored `cowsay`), and prints nothing when none are new.
* `drive` 1.1 output equals `ux01`; quick suite 299 OK, 18 skipped.
* README: proposals in HTML comments at 94-104 (Quick Start paragraph)
  and 170-213 (Download Prompt); they describe the unbuilt `n` removal
  and silent later downloads, and say so.
* `ux02` left: batch question style (4-5), no download question on a
  later run (6-12), an extra blank line (22), changes display (23-30).

## 2026-10-18: End-user and developer mode (Wayne), built

* Two customers.  A program is assumed to be an end-user's until its
  file changes; from then on it is in developer mode.  Per program, in
  its `develop/` record (`mode`, `source` = the file's SHA-256), set by
  `EZPkg.developing()` at the start of `install_declared`.  Deleting
  the record makes it an end-user's again.  Accepted edge: an end-user
  given a newer copy by its author looks like a developer.
* End-user mode: only the download question (`ux01`'s words); never a
  `dependencies` question or an edit (the discrepancy is only warned
  about once per change, as with no terminal).
* Developer mode: the batch/per-item questions and display; the
  download question says "Your changes to `prog.py` need N more
  software package(s) from the internet.  Answer `n` and they will be
  removed again, without running `prog.py`." / "Keep them in
  `~/.ezpkg` and run `prog.py`?" (Claude's wording, for Wayne's review
  in `ux02`).
* The download answers (Wayne, B): `y=>Yes, this time`,
  `a=>Always, never ask again`.  `AGREED` was built and removed again.
  Open: drop "Really never ask again?" after `a`?
* A fetch with nothing new asks nothing (`gate(..., new)`), which
  fixed `ux03`'s two needless download questions.
* `ux/drive.py`: each `Step` has a `mode` (default `developer`;
  1.1, 1.10, 1.11 `end-user`), checked against the record.
* Open: `ux03` line 4 says lines 6-9 (the entries); Wayne's target
  5-10 (the whole array).
* `ux02` agreed by Wayne as `drive` now prints it (developer-mode
  download question included).
* `k` (Wayne): label `k=>Keep it, needed without an import`; then
  `What needs `X`? (a few words, or Enter to skip):`; `with_unimported`
  writes one entry per line with `# Needed by ...` (or `# Needed, but
  not imported.`), adds before an existing array's `]`, keeps comments.
* `inserted` compares a script block change as one block (common start
  and end), since line-by-line matching paired the new `]` with the
  `dependencies` `]` (Wayne spotted the missing `14: add ]` in `ux03`).

## 2026-10-18: Where this stopped (before Wayne's commit)

* Agreed and built: `ux01`, `ux02`, `ux03` (`drive` output equals the
  files; `ux03` line 4 stays "lines 6-9", the entry lines).  Quick
  suite 300 OK, 18 skipped; `drive --until 1.3` 3 of 3.
* Deferred to step 1.7 (Wayne): whether "Really never ask again?"
  after the download question's `a` goes (the label now says it), and
  the batch question's `a` label and its "Really update ...?".
* README proposals at 94-104 and 170-213 still await Wayne ("apply").
* NOT built: `n` on a first run removing `~/.ezpkg`; `a` to the batch
  question being silent; later-step wording (1.4 onwards).
* Next: `ux04` (1.4 Batch n), then 1.4b-1.11, then the download-answer
  steps (`?`, `x`, Enter, `n` first and later run, `a`, Control-D).

## 2026-10-18: `drive --only`

* Wayne: run UX steps individually.  `ux/drive.py --only 1.4 [1.6
  ...]` restores the copy saved after the step before
  (`ux/.snapshots/NN/`, keyed on the SHA-256 of `drive.py`,
  `ezpkg.py`, `quick_start.py` and `ezpkg_test.py`), else runs the
  earlier steps as setup (not written to ux files, not counted).  Only
  the chosen steps' `uxNN_*.txt` files are written; `--ux-dir DIR`
  writes them elsewhere.  A snapshot goes back to its original `/tmp`
  path, since the cache records absolute paths.

## 2026-10-18: Ask before developer mode (Wayne), agreed, NOT built

* `ux02` and `ux04` list the changes before `Update them?`; the
  "Changes made" display after `y` is gone.  Additions are fetched
  silently first, so the list shows the real ranges.
* A changed program is no longer put in developer mode silently.  When
  the file has changed and `dependencies` and the imports disagree
  (only then), `ux02` lines 4-8 ask "Are you working on `prog.py`?
  [y=>Yes|n=>No]".  `y`: developer mode (then `n` to `Update them?`
  is "later").  `n`: stays end-user, warned once, asked again at the
  next change of the file.  No terminal: end-user, as now.
* `drive.py`: 1.2 answers the new question `y`; new steps 1.12, 1.12b,
  1.12c (answer `n`, unchanged rerun, changed again and `y`).  They
  fail until the question is built.

## 2026-10-18: "Are you working on `prog.py`?", built

* `developing()` no longer switches modes: a changed end-user copy
  sets `self.changed` (the new SHA-256).  `sync_dependencies` asks
  `working_on` only when the file changed and there is a discrepancy,
  on a terminal.  `y`: `mode` developer, `source` updated.  `n`:
  `source` updated, `Discrepancy.unlisted()` line ("is left as it
  is, although line 58 imports `tabulate` ..."), `self.declined`
  silences `scan_imports` for that run.  A changed copy with nothing
  to offer records the new `source` and asks nothing.
* Paragraph wrapped like the others (`wrapped`), so `ux02`/`ux04`
  lines 4-6 were rewrapped to match.
* Tests: `synced_program` marks the program developer's;
  `test_an_end_user_is_never_asked_about_dependencies` covers n, rerun,
  second edit y.  Quick suite 300 OK, 18 skipped.
* `drive`: new steps 1.1b and 1.1c (`ux02`, `ux03`; old `ux02`-`ux04`
  renamed `ux04`-`ux06`); `forget_answers` drops only `answer`; the
  temporary path shows as `/tmp/drive-...`.  All 15 steps pass; `ux01`,
  `ux02`, `ux03`, `ux05` equal their targets.
* Left in `ux04`/`ux06` (agreed, NOT built): the list before `Update
  them?`, no "Changes made" after `y`, `ux06`'s "Nothing changed."
  line.  Known cost: a changed end-user copy with no terminal reruns
  the discrepancy check every run (its `source` is kept old so a later
  terminal run still asks).

## 2026-10-18: The list before `Update them?`, built

* `reconcile` lists the changes before the batch question, headed by
  `needing(count, ":")`, via `Discrepancy.display(..., heading=)`.
  The additions are fetched silently first (`versions_of`: lock and
  date as `provide`, holding directory thrown away) for their ranges.
  After `y` nothing is listed again, unless what `provide` brought
  differs from the list.  `n` prints `ux06`'s "Nothing changed." line
  and silences `scan_imports` (`self.declined`).  New helpers
  `fetching` (leaves out the `ezpkg` entry this one meets) and
  `edit_for` (the three-stage edit).
* `ux06`'s target lost a `cowsay` anchor line Claude had written by
  mistake (only the nearest unchanged entry anchors).
* `drive`: 15 of 15 pass; `ux01`-`ux04` and `ux06` equal their
  targets.  `ux05` (Batch i) now gets the list too, then its "Changes
  to be made" display: Claude proposes keeping both (asked, not
  answered).
* Quick suite: 300 OK, 18 skipped, before the last test edit
  (`test_several_changes_are_one_question`, now passing alone).

## 2026-10-18: Breaking imports, and `ux01`-`ux06` agreed

* Wayne: a non-author who edits a program and blames `ezpkg` is the
  worry.  So a missing package (an addition whose module
  `importable()` cannot find) is "breaking": an end-user is asked
  "Are you working on" on every run, changed copy or not (record
  `breaking` = fingerprint), and `n` or no terminal prints
  `Discrepancy.stopping` every run ("Line 58 of `prog.py` imports
  `tabulate`, ... This is a mistake in `prog.py`, not in Python or
  `ezpkg`.  To fix it, add "tabulate" to the `dependencies` list near
  the top of `prog.py` (line 5), or run `prog.py` again and answer
  `y`.").  Deleting `~/.ezpkg` no longer hides it.  Cosmetic
  discrepancies (unused, order, `mypy`) stay a developer's business.
* Wayne's added paragraph sentence ("If the imports and dependencies
  are not in sync, ...") is in `working_on`.
* `ux01`-`ux06` all agreed by Wayne; `drive` output equals every one.
  `ux05` keeps both lists (before `Update them?`, and "Changes to be
  made"); the heading/row line-number mix is left as is.
* Test `test_a_missing_package_is_explained_every_run`.  Quick suite
  301 OK, 18 skipped.
* Next: `ux07` onwards (1.4b Batch n, run again, then 1.5-1.11).

## 2026-10-18: Where this stopped (before Wayne's commit and `/clear`)

* `ux01`-`ux09` agreed by Wayne; `drive` output equals each.  `ux10`
  (renamed `ux10_Always.txt`, step "1.7 Always") is under review.
* Built today, after the breaking-imports note above:
  * Restart after every edit (`EZPkg.restart`, `run_again`, shared
    with `switch`): Python compiled the old file, so a traceback named
    new lines by old numbers (`ux08`).  `EZPKG_RESTARTED` marks the
    second start (it holds `EZPKG_APPROVE`, which the restarted run
    hides from `ezpkg` and gives back to the program, so `write` asks
    nothing twice).  `install_declared` now wraps `provide_declared`.
    The restarted run's `scan_imports` is silent.
  * `statements_above_bootstrap` (allowed: docstring, imports, `def`,
    `class`, assignments, `pass`; the `if` a bootstrap is indented in
    ends it, compared by line since `bootstrap_node` parses its own
    tree); reported by `import_problems`.
  * Misspelt import (`ux08`): "prog.py:69: `import X` needs a package,
    but no package "X" is currently available.  Please check the
    spelling, or manually add the right package to `dependencies`
    (lines 6-8)."; `self.reported` silences `scan_imports`' repeat.
  * Download paragraph (developer): "... from the internet.  They have
    been downloaded, but nothing in them has run yet.  Answer `n` and
    they will be removed again, without running `prog.py`."
  * One change is asked like a batch (`ux09`): list, then `Update it?
    [y|n|a|d]` (plus `k=>Keep it, needed without an import` when the
    one change is a removal); `needing` says "1 entry ... needs".
    The per-item questions remain only behind a batch's `i`.
  * Every question asked once (Wayne: "nobody wants to answer the same
    question twice"): no "Really ...?" after `a`/`d` to `Update
    them?`, nor after the download prompt's `a`.  `a`/`d` print "From
    now on, `ezpkg` updates/never asks about `prog.py`'s
    `dependencies` ...  To be asked again, delete `~/.ezpkg/develop/
    HASH.json`."  A remembered `a` is silent (`ux11`).
* Open:
  * README still describes "Really never ask again?" (lines ~166 and
    ~206) and the old prompts; propose rewrites in HTML comments.
  * `ux10`-`ux15` to review; `ux10`'s record path is a hash that
    changes every run, so `git diff` always shows that line.
  * Last checks: `drive` 15 of 15; quick suite 301 of 302, the one
    failure a wrapped-line assertion, fixed and passing alone.  The
    silent remembered `a` went in mid-run, so rerun the quick suite.
  * Next: Wayne reviews `ux10`-`ux15`; README proposals; then the
    download-answer steps (`?`, `x`, Enter, `n` first and later run,
    `a`, Control-D) and `n` on a first run removing `~/.ezpkg`.

## 2026-10-18: Two modes, Manual and Auto (Wayne)

* `ux/drive.py` now leaves `prog.py` per step: `uxNN_prog.py` (as the
  step ran it) and `uxNN_prog_after.py` (only when `ezpkg` edited it);
  each `uxNN_*.txt` names them on its third line.  Its `with_imports`
  keeps an existing import line whole (it had been stripping the
  `# type: ignore` comments, a false edit in every step).
* Wayne (#1-#6): a developer has two modes, Manual (the default: each
  change asked) and Auto (`a`, never asked again).  `d` ("Don't ask
  again") is gone; an old record's `"never"` now just asks.  The label
  is `a=>Auto, from now on`.  Auto prints one line per change
  (`Discrepancy.reported`: `ezpkg: added "X" to `prog.py`'s
  `dependencies` (line N).`, `removed ... from ...`, `moved`), since
  the file changed under its developer; the `mypy` comment it adds is
  not reported.  Auto covers `dependencies` only: an addition still gets
  the developer download question.  End-user mode is unchanged.
* `drive`: 1.7 Auto (`ux10_Auto`), 1.8 Auto removes an import (`ux11`),
  new 1.9 Auto adds an import (`ux12`); the `d` steps went, so 1.10 and
  1.11 are `ux13` and `ux14` (`git mv`).
* Test `test_auto_outlives_the_run` (was `..._always_and_never_...`).
* README still describes `d` (about lines 330-400); rewrite to propose.
* Later the same day: an Auto addition's line also names the `mypy`
  comment its import got (Wayne's #2); new step 1.9b (`ux13`, `import
  humanize`, never fetched, so the download question comes first);
  Control-C steps are `ux14`, `ux15`.  `drive` 15 of 15.  README:
  the sync proposal (HTML comment after "Keeping `dependencies` in
  Sync") rewritten for both modes; the Download Prompt proposal's
  labels and `a` brought up to date.  Wayne reads README only after
  the UX review.

## 2026-10-18: A no removes what it refuses; Control-C before Enter is a no

* Wayne (`ux14`, `ux15`): Control-C at the download question before the
  answer's Enter is a no; after it the answer stands.  A no on a first
  run (`pip_run` set, `pip.whl` there, root not the home) removes the
  whole cache (`EZPkg.removed`); on a later run only the new downloads,
  which `provide`'s `finally` already did.
* Lines (no `ezpkg:` prefix, backticks): "Declined, so `~/.ezpkg` has
  been removed and `prog.py` did not run." / "... so the new software
  package(s) have been removed ...", "Interrupted, ..." for Control-C;
  elsewhere "Interrupted, so `prog.py` stops here."  `Declined.said`
  carries the line; `install_declared` turns it into `SystemExit`, so a
  no during a `dependencies` update stops too (it had been reported as
  `nothing changed: declined: ...`).  Helper `name_of`.
* `drive`: 1.10 checks the cache is gone (`mode="gone"`); 1.11 (`ux15`)
  now equals `ux01`; new 1.12 No on a later run (`ux16`), 1.13 No on a
  first run (`ux17`).  17 of 17.  Test `test_a_no_removes_what_it_refuses`.
* Left from the download-answer steps: `?`, `x`, bare Enter, `a`,
  Control-D.  The Download Prompt README proposal still says "NOT
  built: `n` on a first run": now built.

## 2026-10-18: `s`, `remove.py`, and steps 1.14-1.23

* Download answers now `[y=>Yes, this time|n=>No|a=>Always, list|
  s=>Always, silently|?=>Explain]` (Wayne).  `FOREVER_APPROVE`'s first
  line is `always` or `silent` (an old marker counts as `always`);
  `EZPkg.silent()` stops `provide`'s list.  The note after `a`/`s`:
  "From now on, `ezpkg` downloads software packages into `~/.ezpkg`
  without asking/silently.  To be asked again, delete
  `~/.ezpkg/FOREVER_APPROVE`.  To remove `ezpkg` and everything it
  downloaded, run `python3 ~/.ezpkg/remove.py`." (no `rm -rf`; Wayne).
* `REMOVE_SCRIPT`, written by the constructor as `remove.py` in every
  cache (`removal_command`: `py FULLPATH` on Windows).  Removes its own
  directory only if it has `versions/` and is not the home; `chdir`s
  out first for Windows.  The cache README names it instead of
  `rm -rf`.
* The `?` list is no longer indented and cuts at 79 like the other
  list.  Control-D ends the prompt line.
* `drive`: steps 1.14 Explain ... 1.23 After remove.py, files
  `ux18`-`ux27` (file numbers are step positions, not step numbers);
  a `Step.command` runs something other than `prog.py`.  27 of 27.
  Tests: `test_silently_asks_and_lists_nothing_again`,
  `test_remove_py_removes_only_a_cache`.
* README proposals still name `a=>Always, never ask again`: update.

## 2026-10-18: Where this stopped (before Wayne's commit and `/clear`)

* The UX review is complete: `ux01`-`ux27` agreed by Wayne (`ux14`
  onwards he was reading at the end), all built, `drive` 27 of 27,
  quick suite 305 OK, 18 skipped.  `remove.py` says "Removed
  `~/.ezpkg`." (`ux26`).
* Decisions today, in short: end-user and developer mode; "Are you
  working on"; Manual and Auto (`a`), no `d`; Auto's report lines; a
  no (or Control-C before Enter) removes the whole cache on a first
  run, the new downloads later; `a=>Always, list`, `s=>Always,
  silently`; `remove.py` instead of `rm -rf`.
* README: proposals in HTML comments for the Quick Start paragraph
  (~94), the Download Prompt (~170) and "Keeping `dependencies` in
  Sync" (~390); Wayne reads them now that the UX review is done.
* Next: Wayne's README read; a test.pypi.org rehearsal (none since
  `1efdcae`; the bootstrap is unchanged, `nopip7`) with
  `release_check.py` and `check.yml` (its `--console` jobs look for
  `=>Explain]`, which still matches); then close `T.abfd`, `T.kdaiis`, `T.reb`, `T.eui`.

## 2026-10-19: Reversal: no prompts for the developer (Wayne), being settled

* Wayne: two experiences, both extremely easy.  The end user gets one
  Yes/No per program ("we downloaded stuff, OK to run it?"); a yes
  covers this and every later version, as Ubuntu updates do.  The
  developer gets no prompts at all.
* Settled: `[tool.ezpkg]` in Part 1 holds the configuration (names
  not decided), including auto upkeep of `dependencies` (on: just do
  it; off: do nothing).  No typo-squatting guard (the developer's
  care).  Removals are silent; a chattier option may come later.  No
  mode detection: end-user/developer mode, "Are you working on",
  `Update them?`, Manual, per-item questions all go.  Removed
  packages stay in `~/.ezpkg` until `remove.py`.
* Also settled: "the program" is its path; additions are silent too,
  `report = true` makes both report; no auto-upkeep setting means the
  developer's responsibility; the download prompt is `[y=>Yes|n=>No]`
  (no `a`, `s`, `?`, `FOREVER_APPROVE`); all configuration is the user
  editing `[tool.ezpkg]`; `cull` stays.
* Wayne's next round: developer mode is a `PROG.py.toml` beside
  `PROG.py` (TOML, like `dependencies`); without it, an end user.  An
  author's forgotten package: let the `ImportError` happen.  Download
  prompt `[y|n|?]`.  `PROG.py.toml` may replace `EZPKG_APPROVE`.
  An entry needed but not imported gets a `# Needed by ...` comment.
* Settled: an empty `PROG.py.toml` is developer mode with defaults
  (auto-upkeep on, silent); the developer never sees the download
  prompt; a hand-added unimported entry is kept and marked, a vanished
  import's entry removed; `ux01`'s list after `y` stays.  Wayne wants
  user-facing environment variables minimised or gone, and a release
  trigger that cleans up and builds the exports (proposal: a command
  script in `~/.ezpkg`, like `remove.py`).
* Earlier open list (superseded): what an empty `PROG.py.toml` means; whether
  the developer sees the download prompt at all; how a hand-added
  unimported entry is told from a stale one; where the approvals and
  date live, and when they change; `EZPKG_EXPORT`; `ux01`'s list.
* Agreed in principle, NOT built; no major coding until every point is
  settled (Wayne).
* Release trigger settled: `release = "X.Y.Z"` in `prog.py.toml`; the
  first run whose value differs from the last recorded (`# Released:`
  in the approvals file) releases once, names its outputs by version,
  and stops instead of running the program.  Every key in
  `prog.py.toml` is checked; an unknown one stops the run ("did you
  mean ...?").  No user-facing environment variables.
* Upgrade (Wayne leaning yes): deleting the `exclude-newer` line makes
  the next run fetch the newest and stamp a new date.

## 2026-10-19: The design, for Wayne's read (agreed in chat, NOT built)

### The two modes

* **Developer mode** is a `prog.py.toml` beside `prog.py` (an empty
  one will do).  Without it the program is an end user's.  No other
  detection: the old `develop/` modes, "Are you working on", and the
  breaking-import messages all go.
* `ezpkg` only reads `prog.py.toml`; the developer edits it.  Every
  key is checked: an unknown one stops the run with `prog.py.toml line
  N: unknown setting X (did you mean Y?)`.

### End user (no `prog.py.toml`)

* One question per program (its path): `ux01`'s paragraph, then
  `[y=>Yes|n=>No|?=>Explain]:`.  `?` is today's terse list.
* `y` covers this program and its later versions: anything it needs
  later is downloaded and run without asking, as Ubuntu updates are.
* After the first `y`: `ux01`'s list of stored packages and the
  `` `ezpkg` (HOME_PAGE) manages `~/.ezpkg`. `` line.
* `n` (or Control-C before Enter): the downloads are removed (the whole
  cache on a first run) and the program does not run.
* Never a reconciliation or an edit.  An author's forgotten package is
  Python's `ImportError`, with no `ezpkg` line.
* Gone: `a`, `s`, `FOREVER_APPROVE`.

### Developer (`prog.py.toml` present)

* No prompts at all, not even the first download.
* `auto-dependencies` (default `true`): `dependencies` is reconciled
  silently: an entry for each new import (named from metadata,
  `MODULE_PACKAGES`, or the module; checked by `prove`; ranged as
  now), the order of first imports, the author's `mypy` comment copied,
  the program restarted after the edit.  An entry whose import
  disappeared is removed.  An entry added by hand with no import is
  kept and marked; the program's record of its last imports tells the
  two apart.  `report = true` prints one line per change.
* Marks: a module named in a string (`importlib.import_module("X")`)
  is an import; an extra of another declared package gets `# Needed by
  pandas (excel)`; anything else `# Needed, but not imported`, for the
  developer to reword.  An entry whose comment starts `# Needed` is
  never removed.  Commands and plugins: not now.
* `auto-dependencies = false`: nothing edited, nothing said.
* Versions never change by themselves.  The approvals (`prog.ezpkg`,
  written by `ezpkg`, kept up to date in developer mode) change only
  when `dependencies` does; the `exclude-newer` date is stamped on the
  first run and moves only on an upgrade.
* Upgrade: delete the `exclude-newer` line; the next run fetches the
  newest and stamps a new date (Wayne leaning yes; trigger not final).
* Release: `release = "X.Y.Z"`.  The first run whose value differs from
  `# Released:` in `prog.ezpkg` reconciles, checks the bootstrap (what
  `EZPKG_BOOTSTRAP=check` did), checks the imports, gives bare entries
  ranges if `ranges = true`, builds what `exports` lists, records
  `# Released: X.Y.Z`, prints what it built, and stops without running
  the program.  Outputs are named by version (`prog-1.0.0.pyz`).
* Settings: `auto-dependencies`, `report`, `release`, `exports`
  (default empty; the README template's comment names `zipapp` and
  `uv`), `ranges`.

### Unchanged

* The bootstrap (`nopip7`), the `ezpkg` switch (`T.eui`), the edited-
  bootstrap refusal (`T.reb`), the restart, `remove.py`, `cull`.

### Environment variables

* `EZPKG_APPROVE` and `EZPKG_EXPORT` go.  `EZPKG_BOOTSTRAP=check` folds
  into the release; `unchecked` stays for the test harness only.
  `EZPKG_SWITCHED`, `EZPKG_RESTARTED`, `EZPKG_PYTHONPATH` stay: they
  pass state from `ezpkg` to its own re-run, and no user sets them.

### Still open

* The upgrade trigger.
* What a failed `prove` (no such package, source only) says in
  developer mode: one line, then the `ImportError`?
* A package added after the date was stamped may not exist before that
  date, so the fetch finds nothing; delete the date, or retry without
  it and say so?
* Whether an end user's later downloads print anything.

### Order (Wayne)

1. Wayne reads this; we iterate.  2. Code (with tests).  3. UX
testing (`ux/drive.py` steps rewritten).  4. README, with a new
developers section.  5. Iterate.
* The four open points settled (upgrade: delete the date line; a
  failed `prove`: one line, then the `ImportError`; a package newer
  than the date stops the run, telling the developer to delete the
  date; an end user's later downloads are silent).  At Wayne's request
  the whole design is now `Details.md`'s "The Design" (the old
  sections kept below it as "Earlier Design"); it supersedes the block
  above.  Waiting on Wayne's read and commit before any code.
* `Details.md` now also has: the empty `prog.py.toml` filled with a
  commented template; "Lessons From the Earlier Design" in place of
  the old sections; a developer run mentioning a newer bootstrap once.
  Wayne is committing the design, then `/clear`; next session starts
  the code, slice 1 (`Details.md`, "The Order of Work").
* Wayne: a release offers to update an older bootstrap and refuses to
  go on with the old one (`Details.md`, release step 2).  How the
  offer is made without a developer prompt (a message saying how, or
  `ezpkg` replacing it) is to be settled when building the release.
