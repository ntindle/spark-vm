# Hosted plane-push gap analysis: the phone-approval loop without a sender

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `41bb330` (2026-10-04 ~00:1x CDT)
and the plane worker checkout
`~/workspace/goals/sparkvm-dev-website-v2-cloudflare-management-infra/control-plane/worker.py`
(the checkout the #846/#873/#952 plane halves were deployed from —
the only `push` mention in it is the `APPROVAL_TTL_MIN` comment at
L1009: "below this a window is a race against push"). Issue/PR numbers
are GitHub references as of 2026-10-04 (not code-verifiable from the
tree). Honesty rules apply (`docs/POSITIONING.md`): this describes
current state and work to do, not promises. Nothing here sends a push.

**Non-overlap map (what this doc is not):**
- The box-local H14 push plane (`confirm/push.py` +
  `docs/PUSH_NOTIFICATIONS.md`) — operator-deployed, per-box VAPID
  identity, subscribed through the confirmd page. This doc's plane
  service is a different sender with a different consumer (tenant
  owner, not operator).
- The alert fan-out intake (`docs/ALERT_PUSH_FANOUT_SPEC.md`, G23 /
  #797) — designs operator paging for fleet alerts; consumer is the
  operator, not the tenant. This doc is the tenant/owner half and does
  not re-design the intake.
- The first-approval summons (`docs/FIRST_APPROVAL_SUMMONS.md`, #428) —
  owns the no-subscription-yet bootstrap via email fallback. #428's §4
  retirement rule retires email "when the push service (H14) ships" —
  H14 exists, but its 201-accepted signal is box-local and never
  reaches the plane, so the criterion is unsatisfiable in the hosted
  lane. This doc owns the plane sender that *extends* S3's
  201-accepted criterion to the hosted lane (making it satisfiable),
  not a second push service.
- The approvals decision path (`docs/APPROVALS_PLANE_GAP_ANALYSIS.md`,
  #849; #873 durable channel; #874 box ingest; #876 filing upload;
  #954 dashboard decide surface). The push plane carries nudges; state
  and decisions stay on those surfaces.

## 1. The loop this leg completes

The hosted vision for sensitive agent actions is: the agent files an
approval → the human's phone buzzes → two taps → the agent unparks —
without the approvals page open. Every leg of that loop now exists
except the buzz:

| Leg | State |
|---|---|
| Filing → plane record | SHIPPED: box→plane filing upload (#952), plane-side records (#872) |
| Owner decide surface | SHIPPED: dashboard box card approve/deny (#954) |
| Decision → box | SHIPPED: `approval_decision` on the durable channel (#873), box ingest (#874) |
| The buzz | **nothing** — no plane push sender, no owner subscription path |

The plane worker *assumes* a push exists: `APPROVAL_TTL_MIN = 60` is
commented "below this a window is a race against push" — but the plane
cannot send one. The box-local H14 push does not close the gap: its
subscriptions live behind the confirmd page, which a hosted tenant
owner never reaches, and its VAPID identity is operator-per-box, not
tenant-scoped.

## 2. Decisions pinned (what the service must be)

Decisions this analysis settles — a design that violates one is a
different design and must re-litigate here:

- **D1. box → plane → device, never box → push-service.** The tenant
  box is an untrusted producer (the #902 hostile-plane class, applied
  outward). The box holds no VAPID private key and no push-service
  credential — the same custody rule #428's S2 enforces for the
  AgentMail sender ("the tenant box's swap path never sends and never
  holds the credential"). The plane is the only signer.
- **D2. Only plane-originated events enqueue.** A push is caused by
  the plane observing its own state (a #872 record filed, a TTL
  expiring, a token revoked), never by a box claiming something
  happened. This is what lets the plane rate-limit and dedup: the
  enqueue key is the plane-side `(box_id, aid)` the #952 endpoint
  already dedups on, not box-supplied text.
- **D3. One plane identity, per-(box, device) subscriptions.**
  The plane owns a single VAPID keypair (operator-generated, worker
  secret). Subscriptions are keyed `(owner_principal, box_id, device)`
  in the D1 database. This analysis pins the custody rule itself (the
  D-series' stated job): subscription secrets rest in the D1 database,
  readable only by the owner principal's own authenticated reads, with
  no box-legible surface and never in worker logs; the VAPID private
  key is a worker secret, never in the D1 database, never committed.
  This reconciles with the analogous open question G50.9 (plane-side
  secret-value custody, `[DESIGN]` in the credential-vending lane) —
  both lanes adopt owner-only-reads + no-box-legibility, and any
  divergence must be reconciled here.
- **D4. "Go look" payloads.** Pushes carry `aid` + a TTL, never
  secrets and never un-scrubbed box-controlled strings (the #902
  control-char class survives the trust flip: hostile *boxes* now).
  Answering an approval on the dashboard is what closes the loop on
  the device — the push cannot be recalled, so reminders must
  re-check state before sending (D6).
- **D5. Tenant/owner consumer only.** Operator paging stays G23's
  job. This service does not page the operator and does not duplicate
  the intake spec.
- **D6. Reminders are leases, not echoes.** A filed approval pages
  once; a T-minus reminder re-reads the plane record first (answered
  / expired → no send). The decision enqueue (#873) is the
  cancellation signal the worker re-checks, not a push-recall API.
- **D7. The first-summons bootstrap stays email.** Web Push needs a
  subscription that only exists after first contact — #428's email
  fallback owns the no-subscription-yet case. This service's S1 (the
  sender-service slice, GP1) does not solve cold start; its acceptance
  is #428's §4 retirement criterion becoming satisfiable in the hosted
  lane: the plane recording a push-service-accepted delivery (201) for
  the tenant.

## 3. Gaps filed

- **[GP1] #967 — plane Web Push sender service (S1 design):** the
  missing sender. D1-database subscription store schema, per-plane VAPID
  custody, the worker send path, enqueue API for
  plane-originated events per D2, send result taxonomy (accepted /
  410 re-register / dead-letter) that #428's §4 retirement criterion can
  consume. **Acceptance:** #428's §4 retirement criterion (a
  plane-recorded push-service-accepted delivery, 201, for the tenant)
  becomes satisfiable in the hosted lane and flips.

  **Design hypothesis, to be validated in the S1 design:** RFC 8291
  `aes128gcm` needs ECDH P-256 + HKDF + AES-GCM + ECDSA VAPID signing.
  The plane worker is Python with stdlib-only imports — the stdlib has
  none of these. Candidate mechanisms: WebCrypto SubtleCrypto via JS
  interop (one `import js` precedent exists at worker.py L895, but it
  is JSON-parsing only — SubtleCrypto use is unproven) or vendored
  pure-Python P-256 + AES. An explicit validation step decides
  in-worker sender vs a separate sender service; the S1 shape is
  contingent on it.

  **Validation result (2026-10-04, `hosted/push_crypto.py`): VALIDATED —
  in-worker sender.** A stdlib-only implementation (pure-Python P-256
  ECDH, HKDF-SHA-256, AES-128-GCM, RFC 6979 deterministic ECDSA for
  VAPID) reproduces every RFC 8291 section 5 / Appendix A intermediate
  value (ECDH secret, PRK_key, IKM, PRK, CEK, nonce, full 144-octet
  body) plus a NIST AES-GCM vector and an RFC 6979 KAT; fresh ephemeral
  sends are verified via receiver-side decrypt emulation, and one
  golden ephemeral body is pinned byte-for-byte (independently
  cross-checked during authoring). Cost per send (ephemeral keygen +
  ECDH + KDF + AES-GCM + VAPID sign, 200 B payload): ~38 ms on the
  loop's dev VM — no separate sender service needed on performance
  grounds. Security posture: not constant-time (assessed
  non-exploitable in the plane's threat model — the box gets no timing
  oracle on the crypto), deterministic ECDSA nonces (RFC 6979, so no
  RNG failure can leak the VAPID key), peer keys curve-validated per
  RFC 8291 section 7. Caveats: the VAPID private key must never leave
  the plane; caller-supplied salts must be unique per message. S1
  proceeds in-worker; no JS-interop dependency.
- **[GP2] #968 — owner subscription management surface:** owner-auth
  `POST /v1/push/subscriptions` / `DELETE` on the plane (D1 database,
  D3-custody), plus dashboard subscribe/unsubscribe affordance on the
  box detail card (extends #954's card — no new page). 410 →
  re-subscribe prompt.
- **[GP3] #969 — event→push mapping + anti-spam bounds:** which plane
  events page (approval filed; T-15m TTL reminder per D6; decided →
  cancel outstanding; token-expiry warning (#846 24h cadence);
  box revoked; heartbeat-stale) and the per-(box, window) rate bound
  the hostile-box model requires (a compromised box must not turn the
  owner's phone into its spam cannon — the filing endpoint is
  box-reachable by design).
- **[GP4] #970 — payload-discipline conformance:** a
  *construction-time* payload scrub (control-char strip + explicit
  length bound with ellipsis), *modeled on* #902's `_plane_text` class
  — which is display-only and not directly reusable (its docstring:
  "Stored values and control-flow comparisons always use the raw
  value — this is for terminal display only";
  `pairing/spark_pair.py` L812; no length bounding). Defense-in-depth:
  D4's aid+TTL-only payloads make the surface nearly vacuous today;
  the scrub pins the rule for future payload fields. Tests prove the
  scrub against hostile fixtures.

## 4. What this does not claim

- No subscription exists yet, so **no hosted approval currently
  pages anyone**. The two-tap loop works only with the page open
  (#954). This doc does not change that; it names the missing
  sender.
- The 60-minute approval TTL ("a race against push") remains a race
  the plane cannot win until GP1 lands. Shortening the TTL without
  the sender would just strand approvals faster.
- Operator push for incidents (G22 S2b tenant incident variant)
  stays gated on G24's tenant scoping per the ALERT spec §G23 S3 —
  this doc does not unlock it.
