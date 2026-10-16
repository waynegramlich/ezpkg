# 7.6 Test on Windows and macOS

Three commonly used operating systems for software development are Linux,
Windows and macOS.  `EZPkg` is primarily developed on Linux.  Since there
are differences between the operating systems, it is prudent to do additional
testing on Windows and macOS.  This can be done with either virtual machines
(e.g. Oracle VirtualBox, QEMU) or real hardware (e.g. a friend's real
machine).  However, since Apple insists that macOS can only be run on official
Apple hardware, the only legal options are some outfit that has set up the
Apple hardware for the task (e.g. GitHub Actions runners) or a friend's Mac.

This task is done when the Quick Start (`./release_check.py testpypi`)
passes on Windows and macOS.
