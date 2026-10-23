# Summary of `T.towam` Test on Windows and macOS

Done 2026-10-22.  The Quick Start (`./release_check.py testpypi`)
passes on Windows and macOS, the task's test, on GitHub's runners
(`T.gar`): `check.yml` 25/25 on `0.0.1.dev202610222321`, and
`email_check.yml` 13/13 for releases.  Along the way it found and fixed
`I.btosc` (python.org's macOS Python has no certificates: `nopip6`
fetches with `curl`) and `I.owenabd` (Windows was never asked before a
download).  `T.qvm` (QEMU) and `T.fwrm` (friends) were not needed.
Related: `T.gar`, `T.qvm`, `T.fwrm`, `I.wmau`.
