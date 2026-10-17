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
