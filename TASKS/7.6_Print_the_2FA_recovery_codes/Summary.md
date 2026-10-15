# Summary of `T.p2rc` Print the 2FA recovery codes

Done 2026-10-14: the recovery codes for github.com, test.pypi.org and
pypi.org (`T.suh2`) are printed; keep the paper apart from the keys.
Getting there took fixing the Brother HL-L2360D: it had a fixed
192.168.1.10 on what is now a 192.168.0.x LAN (set to DHCP; it is
192.168.0.65), its queue had an HP PostScript PPD (replaced by the
`Brother` queue with brlaser v6, Wayne's default), and CUPS's
plain-text filter printed blank pages (`no fontName`) because it
cannot read Noto Sans Mono, fixed by `/etc/fonts/local.conf` aliasing
`monospace` to DejaVu Sans Mono.  In Emacs, `print-postscript-buffer`
is the one to use; `~/.emacs` sets `ps-print-color-p` to nil (the
`tango-dark` theme) and `ps-font-size` to `(8.5 . 10.3)`, the largest
that fits 80 columns.  The left side of the page prints faded, which
is the printer's hardware.
