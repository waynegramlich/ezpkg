# LLM Agent Context Log

## 2026-10-16: The fix, written

* `EZPkg.terminal` opens `CONOUT$`/`CONIN$` when `os.name == "nt"`,
  else `/dev/tty`; failing to open either is still "nobody to ask".
  `InstallTest.test_windows_asks_through_its_console` pretends by
  name.  Quick suite 280 OK, 18 skipped.
* `release_check.py --console` runs the Quick Start on a terminal of
  its own (pseudoterminal with `os.login_tty`; on Windows `pywinpty`'s
  ConPTY), answers `y` at `go ahead?`, and fails if the prompt never
  appears.  Passed on Linux against `0.0.1.dev202610170025`.
* `check.yml` job `console` (ubuntu, windows, macos; Python 3.12;
  `pywinpty` on Windows; 15-minute timeout).  Against the published
  `ezpkg`, which lacks the fix, Windows should fail with "no 'go
  ahead?' on the terminal": the bug, seen.  After a rehearsal it
  should pass.  QEMU avoided if it does (Wayne).
* Agreed alongside: `ezpkg` goes in Part 1 (`T.eui` rewritten).

## 2026-10-16: Seen, fixed, and a new problem

* Before (run 38995866752, `0.0.1.dev202610170025`): `console
  (windows-latest)` failed "no 'go ahead?' on the terminal" while
  `cowsay` was fetched: the bug on a real Windows console.  24 others
  passed.
* Release run 38996065088 (`4fec167`): `0.0.1.dev202610170244`.
  Check run 38996135541: all three `console` jobs passed, Windows
  included, so `CONIN$`/`CONOUT$` works.  QEMU not needed.
* But the five `quick-start (windows-latest, ...)` jobs hung: a
  runner's processes have a console with nobody at it, so `ezpkg`
  now asks and waits forever (no job timeout; Claude cancelled the
  run).  `release_check.py` now starts its child with
  `DETACHED_PROCESS` (no console) unless `--console`, and the
  `quick-start` and `python-org` jobs have `timeout-minutes: 15`.
* For real users the same holds: on Windows "has a console" does not
  mean "somebody is there" (Task Scheduler, CI, services with a
  console).  To be decided with Wayne.

## 2026-10-16: Nobody at the console (Wayne: "sounds reasonable")

* `terminal()` returns `None` when `CI` is set (not "", "0",
  "false").  `answer_from(reader, writer, seconds)` replaces the four
  `reader.readline()` calls: `select` on POSIX, `msvcrt.kbhit` polling
  on Windows; after `ANSWER_SECONDS` (300) it writes "No answer in 5
  minutes, so: no." and returns "", which every question takes as no.
  A tty read returns at most one line, so type-ahead survives.
* `release_check.py --console` pops `CI`, which runners set.
* Tests: `test_ci_is_nobody_to_ask`, `test_an_unanswered_question_is_no`.
  Quick suite 282 OK, 18 skipped.
* README "Download Prompt" no-terminal paragraph proposed in an HTML
  comment.
* Next: Wayne commits; push, rehearsal, check: the five Windows
  `quick-start` jobs should no longer hang (`CI` set), and `console`
  should still pass.
