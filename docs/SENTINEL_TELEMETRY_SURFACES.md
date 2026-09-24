# Sentinel telemetry surfaces — arch deep-read

Status: input to H5 (hosted sentinel integration design), not the H5 design
itself. Deep-read 2026-09-24 of every audit/telemetry surface the sentinel
would consume, from the Architecture lens. Verdict: the trail exists and is
structurally rich, but it is **five bespoke schemas with no shared envelope,
no sequencing, no authentication, and one silent failure mode** — the H5
design cannot treat these as a uniform event stream until the issues below
are resolved.

## The five surfaces

| # | Surface | Writer | Format | Schema |
|---|---------|--------|--------|--------|
| S1 | `confirm/confirmd.py::audit_log` → `audit.log` | confirmd (single process) | logfmt | `ts=<iso-sec> event=<name> peer=<ip> login=<login\|-> <detail>` — detail is free-form `k=v` (`id=`, `host=`, `reason=`) |
| S2 | `proxy/swap_addon.py::_audit*` → `swap.log` | mitmdump addon | logfmt | `ts=<iso-sec> host=<h> swapped=<bool> ip=<ip>` / `ts=<iso-sec> host=<h> refused=<token\|hsurr:name\|authority-mismatch> reason=<r> ip=<ip>` — event type encoded in *which field is present*, not in a name |
| S3 | `muse-job` hooks → `~/.local/share/muse-job/events/<uuid>.jsonl` | shell hooks (agent-adjacent) | JSONL | per-session; **cooperative** — the code's own comments name forged event lines that bypass the hooks as a live threat model |
| S4 | `deploy/auto-deploy.sh` audit | auto-deploy | JSONL | per-run deploy records |
| S5 | `harness/` events | harness scripts | JSONL | provisioning/tenant-record events |

## Findings (filed as GitHub issues this turn)

- **A1 — no shared event envelope.** Five schemas, two formats (logfmt vs
  JSONL), different field names for the same concepts (`peer` vs `ip` vs
  hook fields), and S2 encodes the event *type* in field presence while S1
  gives it a name. A sentinel shipper must hand-parse each surface; every
  new surface multiplies the consumer. Fix direction: a canonical envelope
  (`v`, `seq`, `ts_ns`, `source`, `event`, `attrs`) defined in the H5
  design, with per-surface mappers — not a rewrite of each writer.
- **A2 — no sequencing, no authentication.** No surface emits a sequence
  number or MAC. Log rotation, disk-full windows, and silent drops are
  indistinguishable from "nothing happened" to a downstream shipper. The
  signup doc promises *signed/sequenced* audit-log shipping (see
  `docs/APPROVALS_PLANE_GAP_ANALYSIS.md` §8) — the local primitives for
  that promise do not exist yet. This is the H5 design's prerequisite #1.
- **A3 — second-resolution timestamps collide under burst.** S1 and S2
  stamp `timespec="seconds"`. Under a swap burst or a confirm-flood
  (cf. #76), multiple events share a timestamp and their true order is
  unrecoverable without a sequence number. A2's sequence numbers subsume
  this; until then, order-by-timestamp is unreliable.
- **A4 — trust tiers are not explicit.** S3 is cooperative telemetry (the
  agent can forge lines — `muse-job` says so itself); S1/S2 are written by
  the trusted daemons; S4/S5 sit in between. The H5 design must label each
  surface with a trust tier (evidence vs claim) or the sentinel will treat
  agent-forgeable events as ground truth. Sentinel rule: S3 informs
  *liveness* dashboards, never *authorization* decisions.
- **A5 — confirmd's audit write can fail silently.** S2's `_open_audit_log`
  refuses the swap fail-closed when the audit log cannot be written
  (finding 198, #202); S1's `audit_log` caught `OSError` and did
  `pass` — a full disk silently ate the approvals trail while the
  proxy next door failed closed. Fixed this turn: the except path now
  emits to stderr (lands in the journal under systemd) so the trail gap
  is operator-visible. The residual question — whether confirmd should
  *fail the request* closed like swap does — is a product/security
  tradeoff and stays open as an issue.

## H5 prerequisites (ordered)

1. Canonical event envelope + per-surface mappers (A1).
2. Per-surface sequence numbers (A2) — process-local monotonic counters
   with restart epochs are sufficient; cross-surface global ordering is
   not required.
3. Trust-tier labels on every surface (A4) before any sentinel rule
   consumes S3.
4. Tenant attribution (H10's work) — until then the trail answers "what
   happened" but not "for whom" (already noted in APPROVALS_PLANE §8).

## Non-findings (checked, not issues)

- swap.log's disk-space guard (warn band + fail-closed refusal) is the
  correct posture for the highest-risk surface; confirmd intentionally
  differs and the difference is now documented (A5).
- S3's forgeability is already the code's stated threat model, not a
  surprise — the gap was that no *consumer* contract exists (A4 covers it).
