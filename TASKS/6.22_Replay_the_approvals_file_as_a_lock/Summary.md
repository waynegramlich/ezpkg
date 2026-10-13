# Summary of `T.rafal` Replay the approvals file as a lock

`prog.altvenv` is now a lock as well as a check.  On an ordinary run
`AltVEnv.locked()` turns the approved wheels into `name==version`
constraints for `pip download --constraint`, so the recorded versions
are fetched even when newer ones exist, and `verify` still checks
their SHA-256.  `ALT_VENV_APPROVE=write` ignores the lock and always
fetches afresh (never from a cached request record), so it means
"upgrade and record"; `skip` ignores it too.  The file carries a
`# Resolved: <UTC time>` line.  `request_for` builds the request
record key (requirements plus lock plus date) for both `provide` and
the `zipapp` export, fixing an export that missed a locked run's
record.  A lock that `dependencies` moved past fails with a hint to
regenerate; a non-wheel line in the file is named.  `ALT_VENV_EXPORT=pins`
was later removed: the `exclude-newer` date of `T.srdisb` serves a
`.py` sent on its own.  Related: `T.ewar` (exports), `T.srdisb` (the
date in Part 1), `T.rd` (README promises this).
