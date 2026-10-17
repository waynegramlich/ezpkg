# Summary of `I.owenabd` On Windows EZPkg never asks before downloading

Fixed 2026-10-16.  `EZPkg.terminal` opened only `/dev/tty`, which
Windows lacks, so a Windows user was never asked before a download.  It
now opens `CONOUT$`/`CONIN$` on Windows.  Seen and proved on a GitHub
Windows runner with `pywinpty` (`release_check.py --console`,
`check.yml` job `console`): before the fix "no 'go ahead?' on the
terminal" (run 38995866752); after it, asked and answered (runs
38996135541, 38997637067).  QEMU was not needed.  The fix showed that
on Windows a console can exist with nobody at it (CI runners, Task
Scheduler), where the question waited for ever; so a set `CI` now
means nobody to ask, and every question (`answer_from`) takes no
answer in 5 minutes (`ANSWER_SECONDS`) as no.  `release_check.py`
detaches its child from the console unless `--console`, and every
`check.yml` job has a 15-minute timeout.  README "Download Prompt"
says so.  Related: `T.gar`, `T.fwrm`, `I.wmau`.
