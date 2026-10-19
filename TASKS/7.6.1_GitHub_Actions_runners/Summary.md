# Summary of `T.gar` GitHub Actions runners

Done 2026-10-16; closed 2026-10-19.  `.github/workflows/check.yml`
runs `release_check.py TARGET VERSION` by hand (`gh workflow run
check.yml -f target=testpypi -f version=V`) on `ubuntu-latest`,
`windows-latest`, `macos-latest` and `macos-15-intel` for Python
3.11-3.15 (`fail-fast: false`), plus a `python-org` job (python.org's
macOS Python with no certificates, which proved and now guards
`I.btosc`'s `nopip6` fix) and a `--console` job per system
(`I.owenabd`): 25 jobs, about 3 minutes.  `release_check.py` sets
`USERPROFILE` as well as `HOME`, and a failed job uploads its scratch
directory.  Left over and moved to `T.utpat`: `release.yml` calling
`check.yml` after `publish`.  History in `History.md`.  Related:
`T.towam`, `T.fwrm`, `I.wmau`.
