# Summary of `T.eui` EZPkg updates itself

Done 2026-10-19.  Part 1's `ezpkg` entry chooses which `ezpkg` runs a
program: when the running one does not meet it (`meets`, which orders
`.devN` before its release), `EZPkg.switch` fetches one that does and
runs the program again with it first on `PYTHONPATH` (`os.execve`;
Windows runs a child), once only (`EZPKG_SWITCHED`).  The switch comes
before `T.reb`'s check.  A developer's approvals pin `ezpkg` when it
came from a wheel; a release ranges the entry, but not from a source
`ezpkg` (S5.1c).  `for_export` keeps `ezpkg` in an export only when the
program imports it (`I.uedepi`).  The Quick Start's entry is
`ezpkg>=0.0.1.dev0,<0.1` until the real release.  The exports were
tried in `ux/drive.py` steps 2.11-2.13.  Related: `T.reb`, `T.abfd`.
