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
