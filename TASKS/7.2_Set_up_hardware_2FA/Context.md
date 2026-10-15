# LLM Agent Context Log

## 2026-10-13: Keys ordered

* Wayne ordered two Yubico Security Keys (FIDO2), arriving 2026-10-14.
* This machine (Ubuntu 24.04) already has `libfido2` and udev's
  `60-fido-id.rules`, so browsers should see a key when plugged in.
  If a browser ignores the key's touch, a udev rule is the first suspect.
* Start here when they arrive, one site at a time, both keys on each:
  1. GitHub (Settings -> Password and authentication -> Security keys),
     first, since it becomes the publishing gate under `T.wrw`.
  2. pypi.org: new account, verify the email, Account settings -> Two
     factor authentication -> add a security device; save the recovery
     codes.
  3. test.pypi.org: a separate account, same steps, same username if
     free.
  4. Everywhere: an authenticator app as fallback, recovery codes kept
     offline, the backup key stored apart from the primary.
* No API token on either PyPI; Trusted Publishing (`T.wrw`) replaces it.
* Offered while waiting: start `T.wrw` (build script around
  `release_wheel`, `release.yml`), which needs no account.

## 2026-10-14: Keys arrived

* Both keys in hand; starting with GitHub.  `fido2-token` (package
  `fido2-tools`) is not installed, which browsers do not need.
* Keys are labeled `GitHubA` (primary) and `GitHubB` (backup); both
  also serve pypi.org and test.pypi.org.  Only one fits at a time,
  which is fine: each is registered separately.
* GitHub settings moved; the 2FA page is https://github.com/settings/security
  (no `Access` heading any more).  Wayne's GitHub already had 2FA:
  SMS (preferred) and GitHub Mobile.  Plan: add both keys, make
  security keys preferred, download recovery codes to offline storage
  (printer unplugged), drop SMS later once the keys have proven out.
* GitHub done (R1-R17): GitHubA and GitHubB registered, security keys
  preferred, recovery codes downloaded, sign-in with GitHubA verified.
  Testing GitHubB's sign-in next; then pypi.org.
* Both keys verified for GitHub sign-in (R18-R20).  GitHub finished;
  pypi.org next (P-steps).
* test.pypi.org: Wayne's old `waynegramlich` account existed (the
  register form refused the name); recovered by password reset
  (X1-X4), and 2FA is being added (T4-).  Expect the same on pypi.org.
* test.pypi.org done (T4-T10): both keys, recovery codes saved (one
  used up in PyPI's confirmation).  pypi.org next.
* Correction: the first test.pypi.org pass registered no key (logins
  never asked for one).  Redone as K1-K11: both keys now listed and
  each verified in a private window.  pypi.org next; Wayne thinks he
  never had an account there.
* pypi.org: new `waynegramlich` account, both keys, recovery codes
  saved; each key verified.  All three sites done 2026-10-14.  Only
  the paper copy of the recovery codes is left, which waits on the
  printer and moved to its own task.
