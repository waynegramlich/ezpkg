# Summary of `T.srdisb` Stamp a resolution date into the script block

`ALT_VENV_APPROVE=write` offers to stamp the resolution date into Part
1 as `[tool.uv] exclude-newer = "<UTC time>"` (the same time as the
`# Resolved:` line of `prog.altvenv`), asking first on the terminal
with the line number (`AltVEnv.ask`; no terminal or "no" leaves the
file untouched and says how to add it by hand).  Encoding, BOM and
CRLF are kept.  Without approvals, an ordinary run passes the date to
`pip` as `--uploaded-prior-to` (`pip` 26+), so a `.py` sent alone gets
what was newest when it was recorded; `uv run` reads the same key.
With approvals the lock decides and the date is unused.  An index
without upload times, or an older `pip`, makes the fetch retry without
the date, with a one-line note.  Block editing goes through
`script_toml`, `with_script_toml` and `uv_setting`; the `uv` export
drops `exclude-newer` and now adds `no-build = true` to an existing
`[tool.uv]` unless it sets `no-build`.  Tests borrow a `pip` >= 26
from `~/.alt_venv` (`dating_pip`) and skip without one.  Related:
`T.rafal`, `T.rd`.
