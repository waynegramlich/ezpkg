# 2 Windows and macOS are untried

Everything here has been verified on Linux only, under CPython 3.11 and 3.12.
`nopip3` and `alt_venv.py` both use `pathlib` and `sys.executable` rather than
spelling out paths, so nothing is known to break, but nothing has been run
either; `I.btosc` is the one specific worry, for macOS.  Carried over from
`I.hmmdrpe`.

Various thoughts:
* Wayne (2026-09-22): It would be nice to test on Windows and MacOS.
* Wayne (2026-09-22): I know people who have these machines and would be glad
  to help.  Until then, the answer is currently unknown.
* Wayne (2026-10-01): Access to macOS and Windows machines is in
  progress.
