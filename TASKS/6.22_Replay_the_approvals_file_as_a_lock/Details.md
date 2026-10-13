# 6.22 Replay the approvals file as a lock

Make `prog.altvenv` a lock file, the way `uv.lock` and
`package-lock.json` are, instead of a list that only checks.

Today `ALT_VENV_APPROVE=write` records each wheel's file name and
SHA-256, and later runs refuse a wheel that does not match.  But the
file never tells `pip` what to fetch: `pip` resolves `dependencies`
afresh every time, so a new release of a package is refused rather than
replaced by the recorded one.  The file detects a change but cannot
recreate the old packages.  Only `ALT_VENV_EXPORT=pins`, which writes
`==` pins into Part 1, steers what is fetched (`T.ewar`).

The unified behaviour:

* **An ordinary run with `prog.altvenv` present:** the recorded
  versions are handed to `pip` as constraints (`pip install -c`), so
  the run gets exactly the recorded packages without editing
  `dependencies`, and the hashes still check that they are the same
  files.
* **`ALT_VENV_APPROVE=write`:** the constraints are ignored, `pip`
  resolves afresh, and the result is recorded.  `write` becomes
  "upgrade and record".
* **`pins`:** still needed for a `.py` sent on its own, since the
  versions must then travel inside the file.

Your own code and the packages then change in separate steps, and a
`git diff` of `prog.altvenv` shows which packages moved, which is how a
bug brought in by a new package gets told apart from one in your code.

The README (`T.rd`, "Releasing a Program") already promises this.
