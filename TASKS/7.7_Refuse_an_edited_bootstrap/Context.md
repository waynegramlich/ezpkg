# LLM Agent Context Log

Earlier entries are in `History.md`.

## 2026-10-19: State (condensed)

* Built and rehearsed (from `0.0.1.dev202610170025`): a bootstrap must
  match a published one line for line once trimmed; only the paste's
  indentation is forgiven (Wayne).  `trimmed`, `published_bootstraps`,
  `bootstrap_name`, `bootstrap_refusal`, `bootstrap_differences` (a
  `|` under the first differing character; at most 6, then `... and N
  more`), `EZPkg.refuse_an_edited_bootstrap`, called by `install` when
  `bootstrap=` is given.  `OLD_BOOTSTRAP_TEXTS` holds older texts.
* `EZPKG_BOOTSTRAP=unchecked` skips it (for `bootstrap.py`'s harness),
  printing a line each time.
* Settled: a stale, unedited bootstrap passes.  Still open: a program
  with no bootstrap (`uv run`, a `zipapp`, a direct call) is not
  checked; settle with Wayne's `zipapp`/`uv` dogfood, then
  `Summary.md` and close.
