# Summary of `T.qvm` QEMU virtual machines

Rejected 2026-10-16 (Wayne): GitHub's runners (`T.gar`) passed the
Quick Start on Windows and both kinds of Mac at the first try, so a
Windows VM for debugging by hand is not worth its setup (Windows 11
evaluation ISO, 64 GB of disk, 4 of the 9 GB of RAM).  macOS had
already been dropped, since Apple's license allows it only on Apple
hardware.  Its one live finding, that `EZPkg` never asks before
downloading on Windows (no `/dev/tty`), moved to `T.towam`.  A person
at a Windows console checks the fix (`T.fwrm`).
