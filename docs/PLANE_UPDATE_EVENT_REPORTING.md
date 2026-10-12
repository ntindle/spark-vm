# Plane update-event reporting — S5 (#1288)

Stage 1 shipped 2026-10-11 (distribution turn, slot 20261011-2129). This
document is the slice's design record: what Stage 1 built, and the
written trust story for the Stage-2 plane-signed health-event upgrade
(#1288's acceptance: the trust story is written before any code).

## 1. Stage 1: the operator-observed event journal

The problem (#1288, F-RC-4): health-gated promotion needs a signal the S1
trust discipline explicitly declines — S1 is operator-recorded only
("nothing plane-reported is trusted for ordering"). Stage 1 builds that
signal without touching the trust discipline: an operator-observed event
journal for the plane layer, recording deploy started/landed/deferred/
failed/rolled-back events.

### Schema

`plane-event/1`, one JSON object per line in `<store>/plane_events.jsonl`:

```
{schema, plane_id, kind, template_version, deployment_id, worker_sha256,
 observed_at, reporter, notes}
```

`kind` is a closed vocabulary from #1288: `deploy-started`,
`deploy-landed`, `deploy-deferred`, `deploy-failed`, `rolled-back`.
`template_version`/`deployment_id`/`worker_sha256` are nullable (a
deferral may name no artifact; pre-S4 records carry no artifact
identity). `observed_at` is stamped by the writer from the operator's
clock — there is no flag, argument, or code path that backfills it from
a plane claim (S1's collector-side discipline, transferred verbatim).
`reporter` is always `"operator"`.

### Stage-1 producers, named explicitly (advisory #1288/6105124730)

(a) **The operator's own entry** — `plane-inventory event --plane-id ID
--kind K [--template V] [--deployment-id D] [--worker-sha256 S]
[--notes T]`. For deferrals and out-of-band observations: the operator
watched a push fail outside the driver, or decided to hold a plane.
`deploy-started` is refused here — it is the S4 driver's alone, and an
operator-emitted started must never become "latest" and silently clear
the gate's bad-signal.

(b) **The S4 deploy driver, at the operator's command** —
`plane-deploy deploy` emits `deploy-started` after the D-RC-5 gates and
the pin read, before invoking the Cloudflare push; `deploy-landed` on
verified landing; `deploy-failed` on any failure (deployer exception,
malformed result, digest mismatch, unwired driver) with the failure
message in notes. `plane-deploy rollback` emits `rolled-back` on a
verified rollback and `deploy-failed` (with the rollback context in
notes) when the rollback push fails. Dry-run writes no journal, same
rule as the D-MT5 cost events. A D-RC-5 refusal is not an event —
refusals stay local; `deploy-deferred` is the operator's explicit
decision, not a refusal.

(c) **The S1 `deploy` command** — recording a landing is an
operator-observed landing, so `plane-inventory deploy` emits
`deploy-landed` carrying the record's artifact identity. This is the
operator-correctable path: re-recording a landing clears an unresolved
`deploy-failed`.

All three go through one shared writer (`append_plane_event` in
`fleet/plane_inventory.py`), which stamps `observed_at`, validates the
kind vocabulary and the S3 pin grammars, and fails closed on an
unregistered plane. The reader (`read_plane_events`) fails closed on
any corrupt line — the journal is the wave-health signal's trust root,
so a tampered line must never launder into an empty history.

### Consumer: the S2 promotion gate (D-RC-4)

`plane-waves promote` answers "what happened in the last window?" over
the journal: for each live-wave plane, the latest event with
`observed_at >= waves.json updated_at` (the event window starts when
the wave went live — failures from earlier rollouts never block a
fresh wave). A plane whose latest event in the window is
`deploy-failed` is a **bad-signal** refusal: promotion is refused and
the operator records a fresh landing or reassigns the rollout. The
check is additive and ordered after the degraded check, before the
not-converged check.

- `deploy-deferred` never blocks (an operator decision, not a failure).
- `rolled-back` never blocks (a rollback is the recovery action; the
  S1 record's version/status already gates its outcome).
- A missing journal (pre-S5 stores) carries no signal — D-RC-6's
  "missing events do not block promotion" holds.

### Read path

`plane-inventory events [--plane-id ID] [--kind K] [--since-hours H]`
prints the matching events in journal (append) order as JSON — the
controller's "what happened in the last window?" query, and the
operator's audit view of a rollout.

## 2. Stage 2: plane-signed health events — the trust story (no code)

**Status: named scope only. Nothing here is implemented, and nothing
below authorizes an implementation.** #1288's acceptance requires this
story to exist in writing before any code is written; this section is
that story. If a future slice implements it, the slice's first job is
to re-verify every claim below against the plane runtime as it exists
then — a trust story rots faster than code.

### The question

F-RC-4's named upgrade: a plane attesting "I am healthy on template V"
with a signature the operator can verify, so the promotion gate can
consume plane-observed health instead of operator-observed health. The
G13/G17 forgery question, transferred to planes, is: **who can forge
that attestation?**

### The forgery analysis

A tenant Muse with shell on the box behind the plane is **not** the
plane. The plane is a Cloudflare Worker; its code and environment are
provisioned by the operator's deploy pipeline, not by the tenant. The
signing key lives in the worker's environment bindings (a Workers
secret), which the tenant cannot read: the tenant's shell is on a box
that talks to the plane over HTTPS, and nothing in that path exposes
the worker's env. Forgery therefore requires one of:

1. **Compromise of the operator's deploy pipeline** — the attacker
   ships a worker build that signs false attestations. This is the
   operator's own supply chain; the S3 pin discipline
   (`deployment_id`, `worker_sha256`) already names it as the trust
   root, and a forged attestation here is downstream of a forged
   deploy, which the controller cannot defend against at the event
   layer anyway.
2. **Exfiltration of the signing key from the worker env** — requires
   a Cloudflare-side breach or a worker-vm escape; outside the
   controller's threat model, and symmetric with every other secret in
   the worker env (the box Bearer <redacted>, the D1 credentials).
3. **Replay of a genuine attestation** — the signature must bind
   `(plane_id, template_version, deployment_id, worker_sha256,
   observed_at, nonce)` so a captured "healthy on V" cannot be replayed
   as "healthy on W", and the operator must reject attestations older
   than the rollout window (the same staleness rule the gate applies to
   S1 records).

What the story explicitly does **not** claim: that a tenant Muse
cannot lie to the operator through other channels (it can — the
operator's own observations remain the backstop), or that a
plane-signed event is as trustworthy as an operator observation (it is
not — it is a strictly weaker signal, and the gate must keep treating
operator-observed state as authoritative when the two disagree).

### The upgrade path, sketched

When (not if) a slice builds this: ed25519, one keypair per plane
provisioned at plane creation, public keys in the controller store
next to the plane record (the S1 store is the operator's trust root —
the keys live there, not in the journal); the plane signs a
health-attestation object on a fixed cadence or on deploy landing; the
operator-side collector verifies the signature and appends the event
with `reporter: "plane-signed"` (a distinct reporter value — never
`"operator"`, so the journal stays honest about provenance); the S2
gate consumes plane-signed events only as a *supplement* to
operator-observed state, never as a replacement for the S1 record
checks. Key rotation is a new plane record field with the old key
retained for the verification window — the rotation story is part of
the slice, not an afterthought.

### What would invalidate this story

- If tenant planes ever run tenant-supplied worker code (the "not the
  plane" separation collapses — the signer and the tenant become the
  same principal).
- If the worker env becomes readable from the box side (any
  plane→box secret-exposure path).
- If the controller ever treats a plane-signed event as overriding an
  operator observation (the weaker-signal rule above).

Any of these flips Stage 2 back to "do not build."
