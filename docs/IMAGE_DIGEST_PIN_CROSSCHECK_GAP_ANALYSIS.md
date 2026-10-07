# Image-digest pin-side cross-check gap analysis (#1111 pin slice)

**Vision vs current state for the advisory-D closure** — pinned to main
`6ba09ad` for all in-repo claims (the record half it builds on merged
as PR #1123). This is the design-ahead pass over
the second half of #1111 ("record the push-produced image digest in the
gate record **so pin_image can cross-check it**"): what the pin side
(`harness/pin_image.py`) must enforce before the loop can claim the
operator's word is no longer taken for `--image-ref`.

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below
is **current state and work to do**, not promises. The hosted product is
not live.

## 1. The vision, restated for this leg

Advisory-D (the golden-image advisory): the #905 Fly driver boots
whatever digest the pin names, so the pin must never bless a digest the
pipeline did not itself produce. The record half (#1111) stamps the
push-produced digest into the gate record's `build.image_digest`,
resolved from the registry through the local docker daemon (RepoDigests)
— never pasted from push output by hand. The pin half closes the loop:
`pin_image.py pin --image-ref <ref>` refuses unless the ref's digest
**matches the recorded digest on the same gate record the pin already
validates**. After both halves, a fat-fingered or pasted `--image-ref`
cannot pin; only the digest the publish step recorded can.

## 2. What the lane gained

- **The record half is built (PR #1123, #1111).**
  `deploy/golden-image/build-image.sh --record-pushed-digest
  <gate-record> <image-ref> [--force]` resolves the digest via
  `docker inspect` RepoDigests, enforces the strict
  `sha256:[0-9a-f]{64}` grammar, stamps atomically (tmp + rename),
  write-once (a different recorded digest refuses unless `--force`
  names the re-push case; same digest is idempotent), and refuses
  skeletons, refused gates, non-gate-record JSON, and records naming
  another build (`image_version` must equal this tree's HEAD — the
  tree is the pin). `build.image_digest` is null at skeleton emit —
  the skeleton honestly says the image is not yet pushed.
- **The completed-gate predicate is shared.** The record side's
  publish precondition (`interactive_gate.status == "complete"` and
  `verdict == "pass"`) is semantically identical to `harness/pin_image.py`'s
  `_check_gate_record` (behavioral agreement pinned by the drift test in
  `deploy/golden-image/test_golden_image.py`) — so
  every record the pin side loads already passed the same gate.
- **The pin side's ref grammar is strict.**
  `harness/pin_image.py::_split_digest_ref` requires a digest-pinned
  ref (`<host>/<repo>@sha256:<64 hex>`), pins the registry host to
  `registry.fly.io` (the F3b driver contract host), and pins the repo
  path to two name components; `validate_tag_ref` forces the human
  tag onto the same host and repo path. The digest component is
  already isolated as a return value — the cross-check has a clean
  comparison operand.
- **The pin already loads the gate record.** `write_pin` takes
  `--gate-record` (default `gate-record-<sha12>.json`) and runs it
  through `_check_gate_record` (image_version match + completed
  pass) before writing `deploy/golden-image/pinned-image.json`. The
  cross-check needs no new input path — the record is already in
  hand at the exact point the check belongs.

## 3. Findings: genuinely-new gaps (PIN-F series)

- **PIN-F1 — `write_pin` never consults `build.image_digest`.**
  The record half is currently write-only metadata: nothing reads the
  stamped digest. An operator can still `pin --image-ref` with a
  digest that disagrees with the record and the pin succeeds — the
  README's "Take `<digest-from-push>` from **your own push output only**"
  is operator discipline, not a check. Advisory-D's second half is
  unbuilt; the issue's "so pin_image can cross-check it" clause is
  unsatisfied.
- **PIN-F2 — comparison granularity must be the digest component,
  not the full ref string.** The recorded field is a bare digest
  (`build.image_digest`), so the check compares digests; host and
  repo-path rules stay independent in `_split_digest_ref` /
  `validate_tag_ref`. (The gate record stores no repo path, so
  digest-component comparison is the only available granularity —
  a same-digest ref on a different repo path passes the digest
  check by design, which is benign: the digest is content-addressed.)
  The check compares `_split_digest_ref(image_ref)[2]`
  against `gate["build"]["image_digest"]` — nothing else.
- **PIN-F3 — a null recorded digest must fail closed, with the
  remediation named.** A gate record whose `build.image_digest` is
  null (skeleton-era, or `--record-pushed-digest` never run) names no
  push-produced digest; pinning against it would bless whatever
  `--image-ref` says. The pin must refuse with the remediation in
  the error (`build-image.sh --record-pushed-digest <gate-record>
  <image-ref>`) — never skip, never warn-and-continue.
- **PIN-F4 — pin-side `--force` must not bypass the cross-check.**
  `--force`'s existing meaning on the pin side is "allow repinning
  the same `sparkvm_sha` to a different digest" (the re-push case).
  The re-push path is: `--record-pushed-digest --force` re-stamps
  the record with the new digest, then `pin` matches the new
  recorded digest. If pin `--force` skipped the check, the re-push
  case — exactly when digests change — would be the one case a
  wrong digest gets blessed. The check runs unconditionally;
  `--force` keeps its current (repin-allowance) meaning only.
- **PIN-F5 — the check belongs in `write_pin` (pin time), not in
  `read_pin` / driver time.** The driver's trust root is the
  committed `pinned-image.json` (the module docstring: "the trust
  root is the repo itself"); `read_pin` is a pure shape validator
  the #905 driver imports, and it must stay that way. The gate
  record is an operator artifact that may not travel with the repo
  — the pin already loads and validates it, so pin time is the
  only point where both operands exist.
- **PIN-F6 — the honest ceiling: the check closes paste errors,
  not a malicious operator.** The recorded digest is still
  operator self-attestation (`build-image.sh` emits it unsigned on
  the operator's host; the pin inherits the gate's self-attestation
  ceiling the module docstring already states). The cross-check's
  value is eliminating fat-finger/paste divergence between the
  publish step and the pin step — advisory-D's "take the operator's
  word" — not defending against an operator who lies in both
  places. The slice's docs must not overclaim this.

## 4. Decisions pinned (D-PIN series)

- **D-PIN1 — check location:** in `write_pin`, immediately after
  `_check_gate_record(gate, sha, gate_label)` succeeds and before
  the pin record dict is built. Both operands are validated at
  that point (ref grammar via `_split_digest_ref`, gate via
  `_check_gate_record`).
- **D-PIN2 — digest-component comparison:** compare
  `_split_digest_ref(image_ref)`'s digest against
  `gate["build"]["image_digest"]`. Host and repo-path rules stay
  where they are; the check adds no ref-shape opinions.
- **D-PIN3 — null refuses with remediation:** missing `build`
  section, or `build.image_digest` null, raises `PinnedImageError`
  naming `build-image.sh --record-pushed-digest <gate-record>
  <image-ref>` as the fix. No bypass flag.
- **D-PIN4 — mismatch refuses, both digests named:** the error
  quotes the `--image-ref` digest and the recorded digest so the
  operator can see which side drifted. `--force` does not bypass
  (D-PIN4 documents this in `--help` text).
- **D-PIN5 — no schema changes:** the gate-record schema
  (`sparkvm/golden-image-gate-record@1`) already carries
  `build.image_digest`; `pinned-image.json` (`sparkvm/pinned-image@1`)
  gains no fields — the check gates the write, it adds no data.
- **D-PIN6 — test contract for the slice:** match pins; mismatch
  refuses naming both digests; null refuses naming the
  remediation; pin `--force` + mismatch still refuses;
  same-digest pins succeed regardless of tag handle; the existing
  completed-pass drift test stays the shared-authority pin for
  the predicate both sides enforce.

## 5. Explicitly NOT new gaps (already owned)

- The record half itself (#1111 / PR #1123 — merged as `6ba09ad`;
  this doc is pinned to post-merge main).
- The completed-pass predicate agreement (drift test in
  `deploy/golden-image/test_golden_image.py`, from the #1123
  review).
- The trust-root ceiling (operator self-attestation —
  `harness/pin_image.py` module docstring; PIN-F6 restates it, it
  does not re-file it).
- #905 Fly driver consumption (`read_pin` / `pin_image_ref`
  contract — unchanged by this slice per D-PIN5/PIN-F5).

## 6. Gaps filed

- **#1124 — pin-side cross-check of `--image-ref` against the
  gate record's `build.image_digest` (#1111 pin slice):**
  implement D-PIN1–D-PIN6 in `harness/pin_image.py::write_pin`
  (comparison after `_check_gate_record`; digest-component only;
  null/mismatch fail closed with remediation/both digests named;
  `--force` never bypasses; no schema changes) plus the D-PIN6
  test contract. Closes the second half of #1111's "so pin_image
  can cross-check it" clause. (priority:p3, track:hosted-product,
  matching #1111.)
