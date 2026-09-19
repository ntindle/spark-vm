# Security policy

spark-vm handles real credentials (the transparent-swapping egress proxy,
the `cred` store, human-approval flows). We take reports seriously and we
ask you to take disclosure seriously too.

## Reporting a vulnerability

**Do not open a public issue or PR for a security problem.** Public
disclosure before a fix is available puts every deployment at risk.

Instead, report it privately through a
[GitHub Security Advisory draft](https://github.com/ntindle/spark-vm/security/advisories/new)
("Report a vulnerability" on the repo's Security tab). That opens a
private channel with the maintainer. If private advisories aren't
available, reach the maintainer (ntindle) through the contact information
on their GitHub profile and ask for a private channel before sharing
details.

Please include:

- what component is affected (`proxy/`, `cred/`, `muse-job/`, `confirm/`, …)
- what an attacker can do, concretely, and what access they need first
- steps to reproduce, or a proof of concept if you have one
- anything you've ruled out (saves a review round)

## What to expect

- Acknowledgement of the report.
- A fix developed privately, then shipped as a normal PR with credit to
  the reporter (unless you'd rather stay anonymous).
- The advisory is published after the fix is available and deployments
  have had a chance to update.

## Scope notes

- This project is self-hosted by design; "localhost-only" assumptions are
  documented per component. A report that a localhost-only service has no
  auth is most useful when it shows a realistic path for an untrusted
  party to reach it.
- The `hsurr:` placeholder convention means configs in the repo should
  never contain real secrets. If you find a real credential committed
  anywhere, treat it as a security report, not a regular issue.

## Maintainer TODO

- [ ] Enable private vulnerability reporting if not already on
  (Settings → Code security → Private vulnerability reporting).
- [ ] Publish a preferred direct contact for security reports.
