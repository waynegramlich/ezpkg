# Summary of `I.pfaibne` `.pth` files are installed but never executed

Every case writes coverage's `a1_coverage.pth`, its hook for measuring
subprocesses, and no case runs it, because only `site.addsitedir()` executes
`.pth` files and every case uses `sys.path.insert`.  Any package relying on a
`.pth` is quietly half-installed. Switching to `site.addsitedir()` is the
obvious experiment.

Last thought: Claude (2026-10-01): Closed with Wayne's agreement. Step 6.9.2
has `alt_venv.py` run `.pth` files through `site.addsitedir`, and the bootstrap
installs nothing but `alt_venv`, which ships none.
