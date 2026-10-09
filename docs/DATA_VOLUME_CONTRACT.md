# Data-volume contract (#1205, #851 provisioning lane)

The Fly driver mounts one data volume per provisioned box
(`mounts: [{volume: "vol-<tenant>", path: "/data"}]` — research F3), and
the research's own F1 names the cold-stop model the contract protects
against: the golden image boots with an **ephemeral rootfs** — a cold
stop resets the rootfs to the image while the data volume persists. The
research's open item 3 ("what lives on /data vs baked into the image")
is answered here, not assumed: this doc pins the /data-vs-baked
inventory, the cold-stop survival rule for each entry, and the rule that
provision-time writes land under `/data`, never the ephemeral rootfs.

Get the inventory wrong and a cold stop silently re-enrolls the box
(pairing state lost), loses the generation/epoch discipline
(#947/#976), rotates the SSH host identity under the #1204 attestation
pin, or drops pending approvals and audit trail. Each entry below names
the failure mode its rule prevents.

## The mount rule

- The driver mounts the volume at `/data`. The volume starts **empty**
  on first provision.
- **Driver MUST (D-V5): every provision attaches a fresh, empty volume —
  never a recycled or cross-attached one.** A foreign volume carries the
  previous tenant's `enrollment.json`, so the identity-seed hook's
  skip-if-enrolled check passes and the box silently operates as the
  previous tenant's identity (new attestation token never presented,
  pairing state never re-enrolled). Volume reuse across tenants is a
  tenant-impersonation path, not an optimization.
- **Provision-time writes target `/data`, never the rootfs.** The
  driver and the image's first-boot steps write only under `/data`; the
  ephemeral rootfs receives only the image. A provision-time write that
  must survive a cold stop and lands anywhere else is a contract
  violation.
- Daemons reach `/data` through the machine-config env interface below.
  supervisord inherits machine env into its children, and none of the
  `[program:*]` sections in `deploy/golden-image/supervisord.conf`
  override these keys, so the values below flow through to the daemons
  unchanged.

## Machine-env interface (driver → image)

On provisioned boxes the driver sets, alongside the D-D6 provision-time
env (`SPARKVM_BOX_ID` / `SPARKVM_PLANE_URL` / `SPARKVM_ATTESTATION_TOKEN`):

| Env var | Value on provisioned boxes | Consumer |
|---|---|---|
| `SVM_PAIR_DIR` | `/data/pairing` | `pairing/spark_pair.py::_state_dir` (also read by `deploy/golden-image/identity-seed-hook.sh`) |
| `CONFIRM_DIR` | `/data/approvals` | `confirm/confirmd.py` (APPROVALS) |
| `CONFIRM_AUDIT` | `/data/confirmd/audit.log` | `confirm/confirmd.py` (AUDIT) |
| `RELAY_SESSION_JOURNAL` | `/data/relay-session-journal.jsonl` | `hosted/relay_liveness.py::journal_path` |

## Inventory: what lives where, and the cold-stop rule

`MUST persist` = loss on cold stop is a correctness break (named in the
"failure mode" column). `MAY reset` = loss is bounded and operational
only. `FUTURE` = reserved path for an unbuilt lane; nothing writes it
today.

| State | In-image default | /data path | Rule | Owner | Failure mode if the rule breaks |
|---|---|---|---|---|---|
| Pairing state — `box.key`, `box.pub`, `pairing.json`, `enrollment.json`, `last_heartbeat.json`, `heartbeat.log`, `phone_home_generation.json`, `phone_home_backoff.json` | `~/.config/spark-pair` (client default; the identity-seed hook resolves to `/root/.config/spark-pair`) | `/data/pairing` | **MUST persist** | Follows #1220 (status quo: root; Options A/B named there — this contract does not pre-decide) | Cold stop silently re-enrolls the box (new `box.key` = new identity; attestation token is single-use, so the re-enroll fails closed and the box strands); generation/backoff loss breaks the #947 epoch fence and the #1022 backoff resume |
| confirmd stores — `pending/`, `answered/`, `consumed/` | `/home/swapd/approvals` | `/data/approvals` | **MUST persist** | `swapd` | Pending approvals vanish on cold stop — the plane thinks decisions are outstanding that the box can never deliver; answered/consumed loss re-opens replay windows the #873 write-once gate closed |
| confirmd audit log | `/home/swapd/confirmd/audit.log` | `/data/confirmd/audit.log` | **MUST persist** | `swapd` | The refusal trail (the evidence the #849 loop and the sentinel feed consume) gaps on every cold stop |
| Relay session journal | `/var/lib/sparkvm/relay-session-journal.jsonl` | `/data/relay-session-journal.jsonl` | **MUST persist** | The relay emitter's user (the emitter is not yet wired to a box daemon; the contract pins the path — ownership follows the emitter when it lands) | Box→plane event buffer loss drops session-liveness frames silently; the parent dir is `/data` itself, which the mount guarantees |
| sshd host keys | `/etc/ssh/ssh_host_*_key` | `/data/ssh/ssh_host_*_key` (symlinked from `/etc/ssh`) | **MUST persist** | `root` | Regeneration on every cold stop rotates the host identity under the #1204 attestation pin — every cold stop looks like a new machine to the relay's `ssh_info` |
| swap proxy log | `/home/swapd/swap.log` | — (stays on the rootfs) | MAY reset | `swapd` | Operational log only, logrotate-bounded; audit *shipping* rides the relay journal and plane records, not this file |
| supervisord program logs (`/var/log/*`) | `/var/log/*` | — (stays on the rootfs) | MAY reset | `root` | Operational logs only |
| Tenant homes | `/home/agent` skeleton (baked) | `/data/homes/<tenant>` | FUTURE | — | Reserved: per-tenant users are not provisioned yet (multi-tenant model undecided, #1159) |
| Credential-vend grants | — | `/data/vend/` | FUTURE | — | Reserved: the box-side vend path is unbuilt (#891); when it lands its lease store goes here, not the rootfs |

## First-boot layout (`deploy/golden-image/data-prep.sh`)

The volume starts empty, and several writers cannot create their own
parents: confirmd never `makedirs` the audit log's parent (`open(AUDIT,
"a")` fails loud on a missing dir), and the relay journal's contract is
explicit — the parent must exist, "a missing dir fails loud, never
silently created somewhere the operator didn't choose". So the image
owns first-boot layout:

- `data-prep.sh` runs as **root**, supervisord priority 5, one-shot
  (`autorestart=false`, `startsecs=0`), idempotent. It creates the
  pinned subdirs with the owner/mode from the inventory table
  (`/data/pairing`, `/data/approvals`, `/data/confirmd`, `/data/ssh` —
  0700 each), then creates the `/etc/ssh/ssh_host_*_key →
  /data/ssh/ssh_host_*_key` symlinks.
- **`/data` absent (self-hosted / dev boots) is not an error**: the
  script exits 0 with a loud log line and changes nothing — every
  default in the inventory table's "In-image default" column keeps
  working exactly as today.
- **The sshd firstboot script is defensive, not trusting**: before
  generating keys it ensures `/data/ssh` + the symlinks itself when
  `/data` exists. supervisord priority ordering is start-ordering, not a
  completion barrier (noted in `supervisord.conf`), so the entrypoint
  that needs the keys guarantees its own precondition. `ssh-keygen -A`
  writes through the symlinks; the "missing" check follows them, so a
  cold stop finds the keys present and skips generation.
- Writers that *can* create their own dirs still do (`_state_dir`
  `makedirs` 0700; confirmd `makedirs` its stores) — the contract pins
  the paths, not who creates them; data-prep only covers the parents
  the writers cannot make.

## Host-key rotation & #1204 precedence (Security B4)

Pinning the host keys removes the accidental rotation that previously
bounded the useful lifetime of a compromised host private key. The
tradeoff is explicit: **a stolen host key is now useful indefinitely,
in exchange for attestation stability across cold stops.** The rotation
procedure below is the compensating control — it must exist before the
pin matters, not be discovered in an incident.

- **Rotation:** delete the `/data/ssh/ssh_host_*` *targets* (leave the
  `/etc/ssh` symlinks dangling) and reboot. The firstboot script's
  missing-check follows the dangling symlinks, sees no keys, and
  `ssh-keygen -A` regenerates through them onto the volume. Rotation
  **invalidates the #1204 attestation pin** — the new fingerprint must
  be re-attested over the provisioning channel before the box is
  trusted again.
- **#1204 precedence:** #1204's decided design is driver-minted,
  env-injected host keys ("attestation holds by construction"). When
  that lands, **env-provided keys win**: the driver writes them through
  the `/etc/ssh` symlinks onto the volume (the same indirection — no
  new path), and the firstboot script's missing-check then skips
  generation. Box-self-generated keys remain the fallback for
  non-hosted (self-hosted/dev) boots, where no driver injects keys.
- **Conflict rule:** if real rootfs key files and volume keys ever
  coexist, the volume's key wins and the rootfs file is quarantined
  loudly (`*.rootfs-conflict-*` next to it, 0600) — never silently
  overwritten. See `ensure_link` in both boot scripts.

## What stays baked (and why)

Everything else in the image — the swap proxy stack, confirmd code,
cred-ui, the CUA desktop stack, the agent skeleton, the venvs — is
immutable program code. Per-machine secrets are never baked (the
Dockerfile strips package-generated host keys; the baked-secrets scan
enforces it). Logs that are purely operational stay on the rootfs
(`MAY reset` rows above). The inventory table is closed: a new
durable-state path on a provisioned box must be added to this doc with
its cold-stop rule before the code that writes it ships.

## Self-hosted boxes

Unaffected. Without `/data` every default in the inventory table
applies, data-prep.sh is a no-op, and the sshd firstboot script behaves
exactly as before. The contract is provisioned-box-only.

## Consumed by

- #905 (Fly driver): implements `mounts: [{volume, path: "/data"}]`
  and sets the machine-env interface against this inventory.
- #1204 (host-key attestation): the attestation mechanism can pin the
  host identity because the keys now survive cold stops.
- #1219 (scheduler wiring) + #1220 (pairing-state ownership): the
  `/data/pairing` path is pinned here; the owner is theirs to settle.
- #891 (box-side vend path): `/data/vend/` is reserved for its lease store.

## Decisions

- **D-V1 — /data subdirs are image-owned at first boot, not driver-written.** The driver mounts an empty volume; the image's root one-shot lays out the pinned subdirs. Rationale: the driver stays substrate-thin (mount + env), and the layout travels with the image that consumes it — a driver written against this doc cannot drift from the image's expectations.
- **D-V2 — env interface, not config files.** Daemons already read these env vars; the contract standardizes the values instead of adding a config layer. The values are set by the driver (machine env), so no image rebuild is needed to change them.
- **D-V3 — host keys via symlink, not a config change to sshd.** sshd keeps reading `/etc/ssh`; the indirection lives in the first-boot scripts. No sshd config change, no new failure mode in the daemon's config parsing.
- **D-V4 — defensive consumers, not barrier ordering.** supervisord cannot barrier-order one-shots, so the sshd entrypoint ensures its own `/data/ssh` precondition. A future consumer with the same need follows the same pattern instead of assuming data-prep finished.
- **D-V5 — fresh volume per provision, never recycled.** See "The mount rule": a foreign volume is a tenant-impersonation path (stale `enrollment.json` skips the identity-seed hook), so the driver MUST attach an empty volume every provision.
- **D-V6 — rotation is delete-targets-and-reboot; #1204 env injection wins.** See "Host-key rotation & #1204 precedence": the pin's tradeoff (indefinite key lifetime post-compromise vs stability) is explicit, the rotation procedure is documented before it is needed, and the two host-key designs compose with env-provided keys taking precedence.
