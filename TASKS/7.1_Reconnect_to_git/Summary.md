# Summary of `T.rtg` Reconnect to git

The project had never been on GitHub under any name, so there was
nothing to reconnect: `gh repo create` made the public
https://github.com/waynegramlich/ezpkg on 2026-10-12 and `main` was
pushed (102 commits).  The remote is named `github` (Wayne's
`remote.pushdefault`) and uses HTTPS through `gh`'s credential helper,
because the ssh key's passphrase is forgotten.  The symlinks `aic`,
`ai_contexts` and `claude_notes.md` were untracked and ignored, since
they would dangle on GitHub.  `TASKS/`, `ISSUES/` and `RULES/` are
public along with the code.
