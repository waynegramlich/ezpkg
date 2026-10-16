# 21 On Windows EZPkg never asks before downloading

`EZPkg.terminal` (`ezpkg.py`) finds the person to ask by opening
`/dev/tty`, which Linux and macOS have and Windows does not.  On Windows
the open always fails, so `EZPkg` decides nobody is there, as under
`cron`, and the download prompt answers yes by itself.  A real person
at a Windows console is never asked before packages are downloaded,
which breaks README's "Download Prompt" promise ("It would be rude to
do downloads without asking at least once, so `EZPkg` asks").  The
discrepancy question (`T.kdaiis`) and the `EZPKG_APPROVE=write`
questions go through the same door, so they are never asked on Windows
either.  Found by reading the code on 2026-10-16; nobody has run it on
Windows by hand.  The GitHub runners (`T.gar`) pass, as they would
anyway, since they have no terminal.  Must be fixed before `T.utpat`
(Wayne).

Various thoughts:
* Claude (2026-10-16): The Windows console's own names are `CONIN$`
  and `CONOUT$`, which `open` accepts, and which reach the console even
  when standard input is a pipe, as `/dev/tty` does.  Without a
  console (a double-clicked `pythonw`, a service) they fail to open,
  which keeps the "nobody to ask" behaviour.  Checking it needs a
  person at a Windows console (`T.fwrm`).
