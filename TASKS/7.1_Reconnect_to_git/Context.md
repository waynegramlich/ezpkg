# LLM Agent Context Log

## 2026-10-12: What is there now (read-only look)

* The project directory is now `~/public_html/projects/ezpkg`.  `.git`
  came with it: 100 commits on `main`, the rename uncommitted.
* No git remote is configured.  `~/.gitconfig` sets
  `remote.pushdefault=github`, but this repository has no `github`
  remote.
* `gh` is logged in as `waynegramlich` (ssh, `repo` scope), and neither
  `waynegramlich/alt_venv` nor `waynegramlich/ezpkg` exists, so either
  the repository was never on GitHub or it is under another name or
  account.
* `.git/AUTO_MERGE` and `ORIG_HEAD` (18:49-18:51) are left over from
  Claude's `git stash` / `stash pop` during the rename; harmless.
* The test wheel's metadata already says
  `Homepage: https://github.com/waynegramlich/ezpkg` (`ezpkg_test.py`).
