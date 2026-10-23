# Summary of `T.abfd` Ask before the first download

Done 2026-10-22.  `EZPkg`'s two customers: without a `prog.py.toml` a
program is an end user's, who is asked once per program ("Retain
`~/.ezpkg` and run `prog.py`?", `y`/`n`/`?`; Control-C, Control-D or no
answer in 5 minutes is no; a no removes what was fetched) and whose
program is never edited; with one it is its developer's, who is asked
nothing.  The bootstrap became `nopip8` (fetches only `ezpkg`'s wheel;
`EZPkg.own_pip` fetches `pip`).  The developer's side was reshaped by
`T.ee` (no edits, the stash, releases) and `T.ept` (the template).
`ux/drive.py` (end user 1.1-1.12, developer 2.1-2.17) passes 29/29 and
Wayne read it on 2026-10-22.  Small items left in `History.md`: S2.2b,
S2.4g, S2.4h, S3.3c, S3.3d, S5.1d.  Related: `T.ee`, `T.ept`,
`I.ffspo`.
