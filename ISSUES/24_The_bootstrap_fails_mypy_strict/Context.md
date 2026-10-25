# LLM Agent Context Log

2026-10-25: Wayne's other Claude instance ran `mypy --strict` (the
newly active `R.pcr` asks for it) and hit errors in the pasted
bootstrap, so every stranger who does the same would.  `2026-10-23`
had 4: `def g(u)` untyped (and its two calls), and `req.URLError`,
which `urllib.request` does not export.  Wayne chose a new bootstrap,
`2026-10-25`, and released `ezpkg` 0.0.3 to accept it:

* `import urllib.error`; `def g(u: str) -> bytes:  # Fetch u; with curl
  if no certificates.`; `bytes(req.urlopen(...).read())` (`urlopen`
  is typed `Any`); `except urllib.error.URLError as y: z = y  #
  python.org's macOS.`  Comments shortened to fit 79 columns (Wayne:
  yes).
* All copies changed (`quick_start.py`, `QUICK_START`, README,
  `bootstrap_2026_10_25`), fingerprint `a3efb435...` added to
  `BOOTSTRAPS`, the `2026-10-23` text kept in `OLD_BOOTSTRAP_TEXTS`.
* `mypy.ini` has `strict = True`; the tests patch `os`, `subprocess`
  and friends directly instead of through `ezpkg.` (31 errors), and
  `ezpkg_test_all.py` types its JSON dicts.
* Suite 342 OK; `ux/drive.py` passed (transcripts in the scratchpad
  only, since `ux/` is Wayne's).

Next: Wayne commits; Claude pushes, rehearses on test.pypi.org, tags
`v0.0.3`, releases to pypi.org, runs `release_check.py pypi 0.0.3`;
then this issue closes.
