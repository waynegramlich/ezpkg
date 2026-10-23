# Summary of `T.ept` Edit the prog.py.toml template

Done 2026-10-22.  `SETTINGS_TEMPLATE` in `ezpkg.py` is plain text that
names no program (`PROG_NAME`, the README's word), and `README.md`'s
"`prog.py.toml` Settings" shows it verbatim; a test fails if they
differ or a line passes 79 columns, and Claude copies it after every
change.  Wayne wrote the header.  The order: what the file means, how
to change a setting, the everyday settings (`verbosity`, `upgrade`,
`cull-days`), releases (`exports`, `release`, `bootstrap`, with
`warnings` in `PROG_NAME.py.releases`), and "Rarely needed"
(`requires-python`, `dependencies`).  `auto-dependencies` was removed.
Related: `T.ee`, `T.abfd`.
