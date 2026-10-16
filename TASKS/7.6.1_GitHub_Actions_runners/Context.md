# LLM Agent Context Log

## 2026-10-16: The idea

* A matrix workflow over `windows-latest`, `macos-latest` (Apple
  Silicon), `macos-13` (Intel) and Pythons 3.11 and up, running
  `./release_check.py testpypi` on each.  Free for public repositories.
* Needs a way to answer the download prompt without a terminal.
* Runners' Pythons come with certificates, so `I.btosc` still needs a
  real Mac (`T.fwrm`).

## 2026-10-16: Written

* `.github/workflows/check.yml`: by hand only (Wayne: keep release runs
  at two minutes for now).  Matrix `ubuntu-latest`, `windows-latest`,
  `macos-latest`, `macos-15-intel` (macOS 13 runners were retired
  December 2025; Intel ends with macOS 15 in fall 2027) by Python
  3.11-3.14, `fail-fast: false`.  Inputs reach the script through
  `env`.  `TMPDIR` is `runner.temp`, so a failure uploads
  `release_check-*` (with `include-hidden-files`, for `.ezpkg`).
  `GH_TOKEN` and `actions: read` let an empty `version` use `gh`.
* `release_check.py` sets `USERPROFILE` as well as `HOME`.  Still
  passes locally against test.pypi.org.
* Next: Wayne commits and pushes (a `workflow_dispatch` workflow must
  be on `main` to start), then `gh workflow run check.yml -f
  target=testpypi`.

## 2026-10-16: The first run passed everywhere

* Wayne committed and pushed (`3b192ab`).  Run 38973983823 (`gh
  workflow run check.yml -f target=testpypi`), `ezpkg
  0.0.1.dev202610160145`: all 16 jobs passed, in under a minute.
* Checked in the `windows-latest` 3.11 log: `cowsay 6.1` loaded from
  `D:\a\_temp\release_check-*\home\.ezpkg\versions\...-win-amd64`, so
  `USERPROFILE` gave it the fresh home.  The prompt answered itself, as
  expected with no terminal (and on Windows, always: `T.qvm`).

## 2026-10-16: A job for `I.btosc`

* Wayne: find out whether python.org's macOS Python really fails, then
  replan.  `check.yml` job `python-org` (`macos-latest`,
  `continue-on-error`): installs python.org's `python-3.14.8` and
  `3.15.0` `macos11.pkg` with `sudo installer`, never runs `Install
  Certificates.command`, prints `ssl.get_default_verify_paths()`, the
  framework's `etc/openssl/` and any `SSL_` variables, then unsets
  `SSL_CERT_FILE`/`SSL_CERT_DIR` and runs `release_check.py --python`
  that Python.  `--python` is new: `release_check.py` fetches with
  `urllib` itself, so it runs on `setup-python`'s 3.12.
* Proposed fix if it fails (not decided): `nopip6` falls back to
  `curl` (Keychain) when `urlopen` fails; about three lines.
* Python 3.15.0 is out; the main matrix stops at 3.14.

## 2026-10-16: `I.btosc` confirmed

* Run 38976280642: the 16 matrix jobs passed again.
* `python-org (3.15.0)`, a clean python.org install: `cafile=None`, an
  empty `etc/openssl/`, and the Quick Start stopped at once with
  `ezpkg: choose pip failed: URLError(SSLCertVerificationError(1,
  '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable
  to get local issuer certificate (_ssl.c:1144)'))`, exactly as
  simulated on 2026-10-01.
* `python-org (3.14.8)` passed, but proves nothing: the runner image
  already had a 3.14 framework whose `etc/openssl/cert.pem` (dated
  Oct 13) links to `certifi`, i.e. `Install Certificates.command` had
  been run.  To make it a fair test, remove that link first.

## 2026-10-16: `nopip6` (Wayne: check locally first, then the rest)

* Local check (scratch copies, never the project): `SSL_CERT_FILE` an
  empty file and `SSL_CERT_DIR` missing reproduce the Mac's line with
  `nopip5`.  Linux's `curl` reads those variables too, so a `curl`
  wrapper that unsets them stands in for Apple's.  With it, the
  fallback passes `release_check.py` to the cow; without it, the
  `urllib` error is reported unchanged.  `pip` needs no Python
  certificates (it fetched `cowsay` with them hidden).
* `nopip6`: `def g(u)` in the `try` (6 lines): `urlopen`, else `curl
  -fsSL`, else re-raise the `urllib` error.  All four copies,
  `BOOTSTRAPS` (`c12d783a...` "nopip6 of 2026-10-16"), `SHIPPING`,
  `FAST_CASES`, the `bootstrap.py` row (measured 3.12 s / 0.16 s beside
  `nopip5`'s 3.19 / 0.14) and paragraph.  Two fingerprint tests edited
  `None, 30`, which `nopip6` lacks; now `None, 60`, asserted present.
  Quick suite: 273 OK, 18 skipped.
* README: a `def g(u)` bullet proposed in an HTML comment in "How
  `EZPkg` Actually Works" (Wayne's call).
* `check.yml`: Python 3.15 in the matrix; the `python-org` job deletes
  the image's leftover `cert.pem` so 3.14.8 is a fair test.
  `continue-on-error` stays until both pass.
* `release_check.py` runs the checkout's `quick_start.py`, so the
  check tests `nopip6` without a new upload.
