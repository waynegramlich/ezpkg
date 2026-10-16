# 7.6.1 GitHub Actions runners

Run the Quick Start as a new user (`release_check.py`) on GitHub's
Linux, Windows and macOS runners, for every supported Python, against
the `ezpkg` just published.

## The Plan

* A new workflow, `.github/workflows/check.yml`, with inputs `target`
  (`testpypi` or `pypi`) and `version`.  It can be started by hand
  (`gh workflow run check.yml -f target=testpypi -f version=X`).
  For now it is only started by hand, so a release run stays at about
  two minutes and early problems show up fast (Wayne, 2026-10-16).
  Later, `release.yml` calls it as a third job after `publish`,
  passing the version it built (about five minutes).
* A matrix of runners and Pythons:
  * `ubuntu-latest`, `windows-latest`, `macos-latest` (Apple
    Silicon), and an Intel macOS runner while GitHub still offers one.
  * Python 3.11 to 3.15, from `actions/setup-python`.
  * Every combination runs, even after one fails
    (`fail-fast: false`).
* Each job runs `python release_check.py TARGET VERSION`, and keeps
  its scratch directory as an artifact when it fails.
* No special permissions, and no environment approval: it uploads
  nothing.  Free on a public repository.

## Known Changes

* `release_check.py` gives the Quick Start a fresh home with `HOME`,
  but on Windows `Path.home()` reads `USERPROFILE`, so it must set that
  as well.
* The Windows download prompt belongs to `T.qvm`, since it needs a
  person at a Windows console.

## Limits

* A runner is a clean machine, but not a stranger's: its Pythons come
  from `setup-python`, with working certificates, so `I.btosc` still
  needs a real Mac (`T.fwrm`).
* It shows the bootstrap fetching and running `cowsay`, but not a
  person answering the prompt.
