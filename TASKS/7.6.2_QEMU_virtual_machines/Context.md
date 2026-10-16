# LLM Agent Context Log

## 2026-10-16: The idea

* For debugging by hand when a runner fails.  Wayne's machine has KVM,
  `qemu-system-x86_64` and `swtpm`; but a Ryzen 7 3700U with about 9 GB
  of RAM, so one VM at a time.
* Windows 11: the 90-day Enterprise evaluation ISO with OVMF and
  `swtpm`.  Microsoft's ready-made developer VMs were reported
  suspended; check.
* No macOS here (Wayne, 2026-10-16): Apple's license allows macOS only
  on Apple hardware, so macOS is tested on GitHub's runners (`T.gar`)
  and friends' Macs (`T.fwrm`).  OSX-KVM was considered and dropped.
