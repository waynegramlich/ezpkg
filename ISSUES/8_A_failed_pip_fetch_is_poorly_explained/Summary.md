# Summary of `I.fpfipe` A failed `pip` fetch is poorly explained

If the JSON API lists no wheel for `pip`, case 13's `next(...)` raises a bare
`StopIteration`, and the person sees `cannot fetch alt_venv: ` with nothing
after it.  The SHA-256 digest is in the same JSON and is never checked, so a
truncated download surfaces as a zip error from `python pip.whl/pip` rather
than as a failed fetch.

Last thought: Claude (2026-10-01): The other half is done too, by Step 6.15.15:
the download is checked against its SHA-256 before it is written.
