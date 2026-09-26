# Competitor watch — 2026-09-25 (post post-late-evening)

Lead-resolution pass against the 2026-09-25 post-late-evening pass
(`docs/COMPETITOR_WATCH_2026-09-25_POST_LATE_EVENING.md`). Survey window
**2026-09-25 ~17:25–17:45 CDT** — read-only fetches and searches; no
logins, no writes. Scope note: this pass deliberately did NOT re-survey
the full tracked set — it was **9/9 VERIFIED NO-CHANGE** ~35 minutes
earlier (post-late-evening window ~16:24–17:05), so a re-read adds
nothing; the value this slot is in retiring the carried verification
leads. Carried items C56 and C52 resolved; C54 carried again.
`_POST_POST_LATE_EVENING` is collision-free on origin/main's watch-doc
list for this date (recursive `_POST_` family — the 09-23/24
`_POST_MID_EVENING` precedent).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **snippet-level** = seen only
via search snippet. **UNVERIFIED** = a public page exists but could
not be fetched this run (never reported as NO-CHANGE). **VERIFIED
absent** = the vendor's own page was read this run and the item is
confirmed not present on it.

Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a-20260925-1724.md`, `surveyor-b-20260925-1724.md`), not
the repo.

## 1. Lead resolution — C56 VENDOR-VERIFIED (CVE-2026-82533, DeepSeek Harness)

The post-late-evening pass's carried lead — vendor-primary
verification of CVE-2026-82533 — is **retired this run** on the
vendor's own infrastructure:

- **Vendor repo confirmed upstream:** `deepseek-ai/deepseek-harness`
  (read live via the GitHub API this run — the harness source of
  record).
- **Fix-release chain on the vendor's own release list** (all read
  live this run): `dsh-v0.1.2-alpha.1` published
  **2026-08-27T17:06:37Z** (the fix release), `dsh-v0.1.2-alpha.2`
  2026-08-30T13:52:14Z (first npm release, per the multi-source
  timeline), `dsh-v0.1.2-rc.1` 2026-09-03, latest at survey time
  `dsh-v0.1.7-rc.2` (2026-09-24). The corpus timeline
  (alpha.1 Aug 27 → alpha.2 Aug 30 → rc.1 Sep 3) now matches the
  vendor's own tag publication times exactly.
- **The vendor's own alpha.1 release notes name the fix** (release
  body, read in full this run): "Require the one-time token in the
  launch URL when accessing the Web interface over a network"
  (Chinese: 网络访问 Web 界面时启用链接中的一次性 token 认证鉴权)
  — the one-time-token auth remediation for the unauthenticated
  local control API. The same notes update SAFETY.md: "DeepSeek
  Harness has not been security-audited, and sandboxing, approvals,
  and permissions do not guarantee isolation" — a vendor-admitted
  isolation disclaimer worth noting alongside the fix.
- **The fix commit is on the vendor repo** (read live this run):
  `3e24087bfaeabe40b58ba2f7b936895b8f93fe27`, message
  "fix(web): authenticate the browser Host API", committed
  2026-08-25T06:23:45Z. The OSV CVE record for CVE-2026-82533
  (published 2026-09-08T16:59:47Z; summary "DeepSeek Harness <
  0.1.2-alpha.1 Authentication Bypass via Host Header Spoofing")
  references this vendor release tag (ADVISORY) and this exact
  commit (FIX), closing the triangle: CVE → vendor release → fix
  commit, all on deepseek-ai infrastructure.

The corpus grade for the CVE fix facts moves **THIRD-PARTY →
VENDOR-VERIFIED**. The DSec "escape catalog" facts stay THIRD-PARTY
(Sep-25 Tech Times coverage of the Sep-19 arXiv paper, C49).

**Adjacent color (THIRD-PARTY, not filed):** a community
incident-analysis writeup (tia-n-list) records that the harness's
own GitHub Discussions documented three further vulnerabilities —
DSH-01 node:vm sandbox escape via constructor chain (CVSS 8.8),
DSH-02 dynamic plugin host code escape (CVSS 8.8), DSH-03 the same
unauthenticated /api RPC bridge — plus a later Discussion-#817
security audit finding 7 more issues (incl. unauthenticated LAN RPC
when binding 0.0.0.0); and that the project ships no SECURITY.md
with private vulnerability reporting returning 403 — a disclosure-
posture note. Dennysentinel's post-fix open question stands: "No
public source addresses whether agents can obtain valid session
tokens under the new authentication scheme." The localhost-trust
warning for spark-vm's confirmd/cred-ui pattern (C56's filed
threat-model note) survives the vendor fix unresolved in public.

## 2. Lead resolution — C52 VENDOR-VERIFIED (Docker kits mechanics pages)

The post-late-evening pass's carried lead — the "Learn more about
kits" mechanics docs page — is **retired this run**: both pages
read in full on docs.docker.com live this run.

- The release-notes "Learn more about kits" link resolves to
  **https://docs.docker.com/ai/sandboxes/customize/** — the **v3
  kits page** (Early Access): a kit packages software and
  configuration as a container image with a YAML descriptor;
  **workload** role = base environment + launch command (passed to
  `sbx run`/`sbx create`); **mixin** role = tools, config, runtime
  behavior (added with `--kit`); **kit sets** combine a workload +
  mixins into one pinned, publishable reference; v3 requires
  `sbx` ≥ v0.45; v3 cannot combine with v1/v2 in one sandbox; the
  built-in agent names (`claude`, `codex`) still select **v2**
  kits; V2 remains supported.
- **https://docs.docker.com/ai/sandboxes/customize/kits/** now
  renders as **"Kits v2"** — maintenance/migration guidance for
  the existing scheme: `spec.yaml` with `schemaVersion: "2"`;
  `kind: mixin` vs `kind: sandbox`; kit arguments (`${{
  kit.args.<name> }}` substitution, "Don't use kit arguments for
  API tokens, passwords, or other secrets"); **credential model**
  — "Credentials stay on the host and go through a proxy instead
  of entering the VM", OAuth token responses intercepted with
  sentinel replacement ("the token never enters the sandbox",
  `passthrough: true` opts out), proxy injects credentials only
  into domains named in `apiKey.inject`; network egress declared
  under `permissions.network.allow/deny` ("outbound traffic is
  restricted to the domains permitted by the kit's network
  rules"); agent image requirements (non-root `agent` user,
  UID 1000, passwordless sudo, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`
  preserved across sudo).

The v2-page structure note: the same host-side-proxy +
sentinel-value credential model Docker documents is the pattern
spark-vm's own `hsurr:` placeholder/proxy-swap implements — the
vendor docs independently corroborate the architecture choice.
The C52 corpus row's "Follow-up lead: Kits v2 page mechanics not
yet read" note is closed; no corpus-row changes beyond that.

## 3. In-lane moves — none; no launches, no pricing changes

No Sep-25-dated in-lane launches or pricing moves surfaced in this
pass's scan scope (a lead-resolution pass, not a full market
sweep). **In-lane no-launch verdict dated 2026-09-25 stands.**

Adjacent only (not filed): Docker's Sandbox Kit Spec → CNCF
neutral governance (Apache 2.0) is already corpus at C52
(mid-morning pass, VENDOR-VERIFIED on docker.com/blog) — the
ecosystem-partner list (AWS, Box, Datadog, Dynatrace, JFrog,
NanoClaw, OpenClaw, Palo Alto Networks, Snyk) and the
spec repo `docker/sandbox-kit-spec` remain filed there.

## Carried

- **C54** — full article-body read still blocked: the Perplexity
  URL (`https://www.perplexity.ai/hub/blog/escaping-space-part-i`)
  returns HTTP 403 (`upstream_access_rejected`) on direct fetch
  this run, same bot-block as prior passes — carried again, never
  claimed as NO-CHANGE. Third-party layer widened this pass: a
  second dennysentinel.com analysis of "Escaping SPACE: Part I"
  (2026-09-24, "The Kernel Held. The Allowlist Didn't.") —
  THIRD-PARTY — confirms the vendor-red-team framing: 216 runs,
  0/108 VM escapes, egress-allowlist bypass; "Perplexity … is a
  vendor red team writing up its own product's failures with
  per-model numbers, a remediation, and a re-test reported whether
  or not it flattered the original design."
- **C37** Pro fee still structurally omitted (watched lines —
  not re-read this pass; carried).
- **C26** conflicts unchanged (not re-read this pass; carried).
- Vercel Drives NOT re-checked (P49 once-daily morning cadence —
  next the 2026-09-26 morning pass).
