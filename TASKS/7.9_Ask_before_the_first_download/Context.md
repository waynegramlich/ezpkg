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
