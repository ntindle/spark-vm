# Gate-channel rollout lane convergence (2026-10-19, operator estate)

**Status: analysis, not a commitment.** Every code-state claim below was
verified against the repo tree at main `4959fbc66c1c9a00bb0a6189076437a7a4b4b0af`
(2026-10-19 ~22:4x CDT). Issue/PR numbers are GitHub references as of
2026-10-19 (not code-verifiable from the tree). Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to do,
not promises. No code ships in this analysis; nothing here deploys
anything.

This converges the **box layer** — the #777 (G15/G18) rollout controller
and release-gate channel for the operator's own N-box fleet — against
the 2026-10-17 vision pin (`docs/GATE_CHANNEL_ROLLOUT_GAP_ANALYSIS.md`,
F-GR-1..6, decisions D-GR-1..4). It is NOT the tenant-plane lane
(#1261, `fleet/plane_deploy.py`): that lane was converged separately in
`docs/FLEET_UPDATE_ROLLOUT_CONVERGENCE_2026-10-19.md` (#1261 + #1292
closed). Box rollout and tenant-plane rollout share vocabulary, not
machinery — D-GR-1's tracker split (#1633 operator-estate vs #1634
hosted per-tenant instantiation) still holds.

## Movement since the 2026-10-17 pin (3 of 6 findings resolved)

| Finding | 2026-10-17 state | 2026-10-19 state (this pin) |
|---|---|---|
| F-GR-1 — toolset updater release-gated (#1629) | UNBUILT | **SHIPPED.** `deploy/toolset-update.sh` carries `_toolset_gate_cap` (G18 S1b; fail-closed posture as the repo updater's `gate_cap`); `fleet/README.md`'s S1b section now names it shipped. Issue closed. |
| F-GR-2 — G17 S2 mapping rows, no legacy producer (#1630) | UNBUILT | **OPEN, unchanged.** `fleet/events.py:126-127` still declares `skipped-frozen` / `deferred-arc` as "S2/S3-forward outcomes with no legacy producer". D-GR-2 stands: vocabulary not reopened; #1630 is a producer-build issue. |
| F-GR-3 — fifth alert rule, correlated gate-stale (#1631) | UNBUILT | **SHIPPED.** `fleet/inventory.py:993` fires the fleet-scoped `correlated-gate-stale` page from the collector's answer-age field (D-GR-3 honored — NOT the event stream). Issue closed. |
| F-GR-4 — operator sees gate staleness in `fleet status` (#1632) | UNBUILT | **CLOSED BY VERIFICATION.** The D-GA-2 decision (`docs/ROLLOUT_ALERT_STACK_GAP_2026-10-17.md`, adversarially reviewed Product + Architecture, 2026-10-17) amended the acceptance: no new `fleet status` command is owed — per-box gate-stale folds into the alert board as per-box detail beneath the `correlated-gate-stale` page, verified on main against `fleet events watch`, the G21 console alert board, and `/fleet/alerts`; the last contradicting doc line (`fleet/README.md:142`) was truth-repaired (PR #1790, merged 2026-10-19). Issue closed. |
| F-GR-5 — G15 S2: operator tooling + wave assignment (#1633) | UNBUILT | **OPEN, unchanged.** `fleet/gate_publish.py` carries only the S1a document fields (`--freeze`, `key_id` dual-accept) — no `freeze`/`unfreeze`/`promote`/`halt` CLI surface; `fleet/api.py:666-668` `/fleet/waves` still returns the reserved shape ("unavailable until G15 S2"); `fleet/events.py:340` still `"rollout": None,  # G15 S2 assigns waves`. |
| F-GR-6 — G15 S3 hosted remainders (#1634) | UNBUILT | **OPEN, unchanged** (track: hosted-product): per-tenant gate documents, per-tenant waves (H11), hot-standby publisher, no-consent-gate (G13 §1/T4). D-GR-4 cross-references stand. |

## Decisions pinned by this convergence

- **D-GC-1:** the operator-estate rollout lane is 4/6 converged. The
  three resolved findings are closed through their trackers (#1629,
  #1631, #1632) — no re-verification duty is owed again on these rows;
  the next convergence pin starts from the two open findings.
- **D-GC-2:** #1557 stays open as the lane umbrella per D-GR-1. Its
  acceptance ("each remainder either lands, or the design corpus
  records it as deferred with an explicit owner") is not met while
  F-GR-2/F-GR-5/F-GR-6 stand — the umbrella closes when its last
  finding closes.
- **D-GC-3:** #1630's acceptance stands as written (hook leg emits
  `skipped-frozen` / `deferred-arc` per G18 §7, or the design corpus
  records deferral with an explicit owner). The 4/6 convergence does
  not weaken it: a consumer inferring gate silence from those outcomes
  still counts only silence today.
- **D-GC-4:** #1633 remains the single owner of the operator-estate S2
  halves (tooling + wave assignment). The tenant-plane wave machine
  (#1261's, converged) does not satisfy it — box rollout and
  tenant-plane rollout are distinct machinery (D-GR-1).

## Open trackers after this pin

- #1630 (p3, open-source): G17 S2 mapping rows — hook log shapes need a
  legacy producer.
- #1633 (p3, open-source): G15 S2 — operator tooling + wave assignment
  for the rollout controller.
- #1634 (p3, hosted-product): G15 S3 hosted remainders — per-tenant
  gates, per-tenant waves, hot-standby publisher, no-consent-gate.
- #1557 (umbrella, open): closes when its last finding closes (D-GC-2).
