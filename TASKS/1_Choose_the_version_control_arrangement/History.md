# 1 Choose the version control arrangement: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Task 1 of `LOGBOOK.md` on 2026-10-04.

## Task 1: Choose the Version Control Arrangement  (CLOSED 2026-09-20)

Claude needs to checkpoint constantly, so that any mistake is one
command away from being undone.  The git history should record only
meaningful units of work.  One repository cannot do both: the frequent
checkpoints bury the history that makes the log worth reading.

The task was to decide how to get both, and who operates what.

### Task 1 Summary

Two version control systems share one working directory.  Mercurial is
Claude's and git is Wayne's.  Claude checkpoints into `hg` freely and
never runs `git` at all; Wayne commits to `git` by hand and never runs
`hg`.  Each repository ignores the other, so `.hgignore` excludes
`.git/` and `.gitignore` excludes `.hg/`.  `CLAUDE.md` holds the
detailed working agreement and travels in every git commit, which keeps
the rules versioned alongside the work they govern.

(CLOSED 2026-09-20)
