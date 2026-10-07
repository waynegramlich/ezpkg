# 8 A failed `pip` fetch is poorly explained

(CLOSED 2026-10-01)  If the JSON API lists no wheel for `pip`, case 13's
`next(...)` raises a bare `StopIteration`, and the person sees `cannot fetch
alt_venv: ` with nothing after it.  The SHA-256 digest is in the same JSON and
is never checked, so a truncated download surfaces as a zip error from `python
pip.whl/pip` rather than as a failed fetch.

Various thoughts:
* Wayne (2026-10-01): We'll improve this later.
* Claude (2026-10-01): Half done by Step 6.15.7.  The message now
  names the stage and the exception's type, so the empty `StopIteration`
  case reads `... choose pip failed: ValueError: ...` instead of
  nothing.  The unchecked SHA-256 digest remains.
* Claude (2026-10-01): The other half is done too, by Step 6.15.15:
  the download is checked against its SHA-256 before it is written.
