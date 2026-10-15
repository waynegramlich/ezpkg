# Summary of `T.suh2` Set up hardware 2FA

Done 2026-10-14.  Two YubiKey 5 keys (FIDO2+CCID, the only model
available), labeled `GitHubA` and `GitHubB` and registered under those
names on github.com, test.pypi.org and pypi.org, each key verified by
signing in with it.  The account is `waynegramlich` everywhere; the old
test.pypi.org account was recovered by password reset, and the
pypi.org one is new.  GitHub keeps SMS and GitHub Mobile as fallbacks,
with security keys preferred; dropping SMS is for later.  Recovery
codes for all three are saved offline; printing them waits on the
printer (`T.p2rc`).  No API tokens exist: publishing uses Trusted
Publishing (`T.wrw`).  GitHub's 2FA page is
https://github.com/settings/security.
