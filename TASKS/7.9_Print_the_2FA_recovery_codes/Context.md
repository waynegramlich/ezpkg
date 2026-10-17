# LLM Agent Context Log

## 2026-10-14: Printer fixed

* The Brother HL-L2360D (`BRN30055C56C286.local`) had a fixed
  192.168.1.10 while the LAN is now 192.168.0.x, so jobs never reached
  it.  Its Boot Method was set to Auto; it now gets 192.168.0.65 by
  DHCP and answers IPP.  The CUPS queue for it is named `unknown`, and
  there is no default printer.
* The `unknown` queue used an HP Designjet T920 PostScript PPD, the
  wrong printer entirely.  Made a new driverless queue `Brother`
  (`-m everywhere`, `ipp://BRN30055C56C286.local:631/ipp/print`) and
  Wayne's default (`lpoptions -d`, in `~/.cups/lpoptions`; `lpadmin
  -d` did not take).  `unknown` is kept until a test page prints.
* Test pages `Brother-9` and `Brother-10` completed but came out blank;
  the printer reports toner at 70% and no alerts.  Not yet known
  whether it is hardware (toner/drum after 4-5 idle years) or the
  driverless queue; the printer's own settings page would tell.
  Supplies: toner TN-630 / TN-660 (high yield), drum DR-630.  Wayne
  is weighing supplies against a new printer.
* The printer's own settings page printed (slightly faded on the left),
  so the hardware works and the blank pages came from the driverless
  queue.  Switched `Brother` to `drv:///brlaser.drv/brl2360d.ppd`
  (brlaser v6), same URI.
* Cause of the blank pages: CUPS's text filter (`lp file.txt` or a
  pipe) logs `no fontName` and renders nothing.  A PDF printed fine
  (job 14), so print the codes via an editor/browser's File -> Print.
  The old `unknown` queue was deleted.  The `no fontName` bug is
  not fixed.

## 2026-10-14: After a reboot, Emacs prints blank pages

* PostScript and PDF print fine (test jobs 20, 21).  `~/.gnu-emacs-custom`
  sets the `tango-dark` theme, so `ps-print` printed near-white text;
  Wayne added `(setq ps-print-color-p nil)` to `~/.emacs`.
* Plain text (`lp file.txt`, `echo hi | lp`, Emacs `print-buffer`, job
  24) is the `no fontName` bug: with `CHARSET=utf-8`, CUPS's
  `texttopdf` asks fontconfig for `monospace`, gets Noto Sans Mono,
  cannot parse it ("Unsupported OTF font") and draws nothing.  With
  `monospace` aliased to DejaVu Sans Mono it renders correctly
  (reproduced and fixed by running `/usr/lib/cups/filter/texttopdf`
  directly).  Fix proposed: `/etc/fonts/local.conf` with that alias,
  which needs Wayne's sudo.
* Wayne installed the alias as `/etc/fonts/local.conf`; plain text now
  prints, but `texttopdf` puts it 1 mm from the left edge.  Emacs
  `print-buffer` works but is off-center; `print-postscript-buffer`
  is centered and is the one Wayne will use.  Added
  `(setq ps-font-size '(8.5 . 10.3))` to `~/.emacs`: 35% over the
  default `(7 . 8.5)` wrapped an 80-column line at 72, and 10.3 is
  the largest that fits 80.
