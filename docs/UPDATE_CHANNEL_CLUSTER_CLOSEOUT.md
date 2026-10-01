# Tenant-box update channel — cluster close-out (G11–G20)

Written 2026-10-01 by the hourly gap turn (slot 20261001-0059). This is the
composition audit and closure record for the tenant-box update-channel design
series: the full G11–G20 run is now **designed**. Nothing in this doc is
implemented — implementation is tracked on the issues named below.

## Series record

| Gap | Issue | Design doc | Status |
|---|---|---|---|
| G11 — in-place vs reimage | #553 | `UPDATE_CHANNEL_POLICY.md` §1 | closed on design |
| G12 — tenant-visible update state | #554 | `UPDATE_CHANNEL_POLICY.md` §2 | closed on design |
| G13 — update trust model | #555 | `TENANT_UPDATE_TRUST_MODEL.md` | designed; **closed this turn** |
| G14 — updates vs idle/suspend | #556 | `UPDATE_IDLE_SUSPEND_CLOCK.md` | designed; **closed this turn** |
| G15 — staged rollout / canary / freeze | #606 | `ROLLOUT_CONTROLLER_DESIGN.md` | designed; **closed this turn** |
| G16 — fleet version inventory | #607 | `FLEET_VERSION_INVENTORY_DESIGN.md` (S1 shipped as `fleet/`) | closed on design |
| G17 — update event reporting | #608 | `UPDATE_EVENT_REPORTING.md` | closed on design |
| G18 — fleet→box release-gating channel | #609 | `RELEASE_GATE_CHANNEL_DESIGN.md` | designed; **closed this turn** |
| G19 — audit retention + tenant read path | #660 | `UPDATE_AUDIT_RETENTION_AND_ACCESS.md` | designed; **closed this turn** |
| G20 — migration-tooling input hardening | #661 | `MIGRATION_INPUT_HARDENING.md` | closed on design |

## Composition audit

The seams between the ten docs were re-read for contradictions. Verdict:
**no contradictions found.** The shared load-bearing decisions are stated
identically everywhere they appear:

- **Fail-closed gating (G15 §5, G18 §2/§4):** no signal → frozen. Controller
  down means the whole fleet holds, including the security channel — the
  tradeoff is explicit in both docs, not discovered by one.
- **The two-part freeze bound:** delivery within `sync_cadence`,
  effectuation within `sync_cadence + tick_interval` — stated in G18 §4,
  referenced (not redefined) from G15 §5.
- **Provisioned trust root (G13 §6 S2, G15 §5, G17 §4 S3):** one pinned
  operator key at provision time, fingerprint in every record; tenant-fleet
  gates consume only box-identity-attested events — unattested events are
  logged, never gate-consumed.
- **The journal chain (G13 §2, G19 §1):** registrations outlive everything
  naming their ref; chain-safe deletion keeps attribution interpretable.
- **The 90/30-day journal discipline (G16 OQ2, G17 §4 S2, `fleet/README.md`):**
  90 days of per-box records, compacted to per-day outcome histograms after
  30 days. G16's OQ2 punts to G17's discipline and the S1 README carries it.
- **Never-interrupt-an-arc (G11, G15 §7, G18 §3):** a tenant box mid-arc
  defers even a critical CVE until the arc ends; the security channel gets
  compressed parameters, never a bypass.
- **`maintenance` producer rule (G14 D1/D8, G18 §7):** the window's
  enter/exit stays scheduler-owned; session-clock freezes apply during
  gate-held reimages exactly as during any maintenance window.

## Findings from this audit (filed, not deferred)

1. **G16's S2–S3 slices were orphaned.** The G16 doc footer said
   "tracked on #607" — the closed design issue itself. G17's S2/S3 were
   similarly unowned. Now tracked on **#779** (G16/G17 S2–S3).
2. **G18 §7's owed pointer comment** ("folded into UPDATE_EVENT_REPORTING's
   S1 alert set when the S1b slice lands — pointer comment on #608") names a
   closed issue. Redirected: the comment lands on **#777** (G15/G18
   implementation) when S1b ships. This doc §7 line updated accordingly.
   The same audit then swept the other five design docs for the identical
   stale pattern and fixed each: ROLLOUT_CONTROLLER_DESIGN.md footer
   (#606 → #777), RELEASE_GATE_CHANNEL_DESIGN.md footer (#609 → #777),
   UPDATE_IDLE_SUSPEND_CLOCK.md header (#556 → #776),
   UPDATE_AUDIT_RETENTION_AND_ACCESS.md §6 (#660 → #778),
   UPDATE_EVENT_REPORTING.md footer (#608 → #779) — plus two cross-doc
   stalenesses (TENANT_UPDATE_TRUST_MODEL.md §4 "still open" on #556;
   UPDATE_IDLE_SUSPEND_CLOCK.md cross-refs owning Q5/#608).
3. **G17 S3 has a design remainder:** the signed box→plane channel
   *mechanism* is still design work, owned by the G13 residual per G17 §4 S3.
   Carried explicitly on **#775** (G13 implementation).
4. **Citation nit (no behavior):** G17 §4 S2 says G16's OQ2 "names S3" — G16's
   OQ2 is the retention question, which punts to G17's §4 S2 discipline.
   Substantively true, imprecisely cited. Left in place; corrected here.

## Implementation inventory (the remaining work)

| Issue | Owns |
|---|---|
| #775 | G13 trust model: control-plane update journal + registration CLI + attested event ingestion (S1–S3) |
| #776 | G14 idle/suspend: scheduler suspend-awareness + wake-path hook + clock-pause guards (S1–S3), plus Q1–Q5 |
| #777 | G15/G18 rollout controller + gate channel (S1a–S3), incl. the G15 OQ1 concurrent-releases question and S3 hot-standby |
| #778 | G19 retention GC + tenant read path (S1–S3), plus Q1–Q4 |
| #779 | G16 S2–S3 / G17 S1–S3: fleet-side event canonicalizer + alert rules, push endpoint, gate integration, attested ingestion, plus OQ3/OQ5 |

All five are `enhancement` with the slice breakdowns in their bodies. When a
slice ships, its implementer updates the corresponding design doc's footer —
G16's "tracked on #607" pattern must not recur.

## What this does not claim

- No box-side implementation exists beyond the two per-box updaters
  (`deploy/auto-deploy.sh`, the #532 toolset updater chassis). Every fleet
  component — controller, collector, event sink, journals, gate hooks —
  is a design awaiting slices.
- The fleet layer only pays off at N>1. For the operator's own estate,
  every doc's S1 is the pull/SSH/registry instantiation that ships first;
  the hosted tenant-fleet instantiations additionally wait on G13
  attestation and H11.
