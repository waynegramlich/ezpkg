# 12 `.pth` files are installed but never executed

(CLOSED 2026-10-01)  Every case writes coverage's `a1_coverage.pth`, its hook
for measuring subprocesses, and no case runs it, because only
`site.addsitedir()` executes `.pth` files and every case uses
`sys.path.insert`.  Any package relying on a `.pth` is quietly half-installed.
Switching to `site.addsitedir()` is the obvious experiment.

Various thoughts:
* Wayne (2026-09-22): I have no idea what this issue is about.  Let's do the
  experiment when we get the chance.
* Claude (2026-10-01): Closed with Wayne's agreement.  Step 6.9.2 has
  `alt_venv.py` run `.pth` files through `site.addsitedir`, and the
  bootstrap installs nothing but `alt_venv`, which ships none.
