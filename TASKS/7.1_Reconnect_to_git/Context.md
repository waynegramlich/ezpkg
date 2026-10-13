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

## 2026-10-12: Nothing to reconnect to

* `waynegramlich` has 79 GitHub repositories; none is this project under
  any name, and none was pushed after 2026-09-01.  So 7.1 is creating
  `waynegramlich/ezpkg` and pushing `main` (101 commits, all Wayne's;
  `.git` is 14 MB; no tokens or keys in the history).
* `../ai_contexts` has no remote either.
* Tracked files that would dangle on GitHub: the symlinks `aic` and
  `ai_contexts` (into `../ai_contexts`) and `claude_notes.md` (into
  `../claude_notes`, which no longer exists here).  Also tracked:
  `CLAUDE.md-` (four `@` imports) and `TASKS/`, `ISSUES/`, `RULES/`.
* Wayne chose a public repository, and untracking the three symlinks
  (`git rm --cached`, now in `.gitignore`; still on disk).  Staged for
  Wayne's commit; then Claude creates the repository with `gh repo
  create waynegramlich/ezpkg --public --source=. --remote=github` and
  pushes `main`.

## 2026-10-12: Pushed

* `gh repo create` made the public repository, but the ssh push failed:
  `~/.ssh/config` named the directory `~/.ssh/` as its `IdentityFile`
  (Wayne fixed it to `~/.ssh/id_ed25519`), and that key's passphrase is
  forgotten.  The `github` remote now uses HTTPS,
  `https://github.com/waynegramlich/ezpkg.git`, authenticated by `gh`'s
  credential helper; no ssh key is needed.  `main` tracks `github/main`.
* Verified: GitHub's `main` is `9de569e`, 102 commits.
