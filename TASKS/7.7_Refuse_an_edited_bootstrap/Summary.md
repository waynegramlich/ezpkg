# Summary of `T.reb` Refuse an edited bootstrap

Done 2026-10-19.  A bootstrap must match a published one line for line
once trimmed (only the paste's indentation is forgiven); otherwise
`install` stops, naming each differing line with a `|` under the
first differing character (`bootstrap_refusal`, `bootstrap_differences`,
`published_bootstraps`, `OLD_BOOTSTRAP_TEXTS`).  A stale but unedited
bootstrap passes, and a developer hears once of a newer one, which a
release replaces.  A program with no bootstrap (`uv run`, a `zipapp`,
a direct call) is not checked (Wayne, 2026-10-19): the exports leave
the bootstrap out on purpose.  `EZPKG_BOOTSTRAP=unchecked` is for
`bootstrap.py`'s harness only.  The exports were tried in `ux/drive.py`
steps 2.11-2.13.  Related: `T.eui`, `T.abfd`.
