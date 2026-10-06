# Golden image recipe for the provisioned spark-vm box (#1087, F-P1).
#
# This Dockerfile is the golden image's PRODUCER: the build artifact that
# docs/GOLDEN_IMAGE_GATE_PROCEDURE.md gates per build before publish. The
# #905 Fly driver boots this image per provision — docs/FLY_DRIVER_RESEARCH.md
# recommends the golden-image path over the exec-install (F1b) alternative.
#
# D-P1 (docs/PROVISIONING_METERING_CONVERGENCE_2026-10-06.md): the baked
# manifest records the exact commit + release tag the image was baked from;
# rebuilds pin FORWARD deliberately, never silently. build-image.sh computes
# SPARKVM_SHA / SPARKVM_VERSION from the clean checkout it builds from and
# refuses to build from a dirty tree (the manifest generator refuses dirty
# trees too — a dirty tree under a clean SHA would lie to the injector
# preflight).
#
# Base-image pin decision (documented trade): the base is pinned to the
# ubuntu:24.04 tag; the resolved base digest is captured in the gate record
# by build-image.sh. Digest-pinning the base is a #1087 follow-up, not this
# slice — rebuilding the same recipe later pulls the newest 24.04 base, and
# the gate record is what makes that visible.
#
# No systemd inside the image (Fly Machines run Docker images with an
# ephemeral rootfs — FLY_DRIVER_RESEARCH.md F1): tini is PID 1, supervisord
# owns the daemons. This answers the supervision-redesign open item 1 for
# the golden-image path; the F1b exec-install path keeps its own answer.
#
# Deliberately NOT baked (provision/first-boot scope, not the recipe):
#  - muse CLI + muse-job plugin approval: the install is operator/account
#    bound (user-authorized --yolo, bills the user's Meta pay-as-you-go);
#    the gate procedure's interactive gate validates the claim.
#  - the swapd CA: generated per tenant at first boot; the private key is
#    never baked (manifest baked[] claim; the baked-secrets scan enforces it).
#  - tenant agent users: the recipe bakes the /etc/skel skeleton + a locked
#    `agent` build user; first boot instantiates real tenant users from it.
#  - sshd host keys: generated on first boot by sparkvm-sshd-firstboot.sh —
#    baking one keypair into every tenant's image would be a leak.

ARG SPARKVM_VERSION=0.6.0
ARG SPARKVM_SHA=""
# cua-driver pin mirrors scripts/self_update_pins.conf; bump deliberately
# with a changelog note, exactly like the toolset updater's pin.
ARG CUA_DRIVER_VERSION=0.28.2

FROM ubuntu:24.04 AS base

# Fail closed on a missing pin: an image that cannot name its commit must
# never build (D-P1). build-image.sh always passes both args.
ARG SPARKVM_VERSION
ARG SPARKVM_SHA
ARG CUA_DRIVER_VERSION
RUN test -n "$SPARKVM_SHA" || { echo "SPARKVM_SHA build-arg required (D-P1)" >&2; exit 1; } \
 && test "$SPARKVM_VERSION" != "" || { echo "SPARKVM_VERSION build-arg required" >&2; exit 1; }

ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright

# --- OS layer -------------------------------------------------------------
# unattended-upgrades keeps the image's OS current per #532 (verified and
# repaired by the toolset updater on every run); the rest is the spark-vm
# install inventory (SETUP.md) the image must carry instead of apt-installing
# at provision time.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    ca-certificates curl git jq unzip sudo \
    openssh-server supervisor tini \
    unattended-upgrades \
    xvfb xfce4 xfce4-terminal dbus-x11 \
    python3 python3-venv python3-pip \
    nodejs npm gh \
 && rm -rf /var/lib/apt/lists/*

# --- users ----------------------------------------------------------------
# swapd owns the proxy stack (mirrors proxy/deploy.sh's install targets);
# locked password, no SSH login — the narrow writers run via `sudo -u swapd`.
# `agent` is the skeleton tenant user: first boot instantiates real tenant
# users from /etc/skel (populated from /home/agent below).
RUN useradd --system --create-home --home-dir /home/swapd --shell /bin/bash swapd \
 && useradd --create-home --home-dir /home/agent --shell /bin/bash --password '*' agent \
 && passwd -l agent \
 && mkdir -p /etc/sparkvm /run/sshd

# --- repo tree -------------------------------------------------------------
# The build context IS the clean checkout build-image.sh verified; COPY keeps
# the baked bytes identical to the tree that passed CI (no network fetch of
# the repo inside the build — the box's flaky egress is not in the loop).
COPY . /opt/sparkvm
RUN test -f /opt/sparkvm/VERSION \
 && test "$(cat /opt/sparkvm/VERSION)" = "$SPARKVM_VERSION" \
 || { echo "recipe VERSION mismatch: tree $(cat /opt/sparkvm/VERSION) != arg $SPARKVM_VERSION" >&2; exit 1; }

# --- swap proxy stack -------------------------------------------------------
# Installs exactly what proxy/deploy.sh --no-restart installs (the script is
# the rebuild documentation — the repo is the only source). supervisord owns
# the daemons; no systemd inside the image.
RUN python3 -m venv /home/swapd/.venvs/mitm \
 && /home/swapd/.venvs/mitm/bin/pip install -q "mitmproxy==11.0.2" \
 && chown -R swapd:swapd /home/swapd/.venvs \
 && cd /opt/sparkvm && ./proxy/deploy.sh --no-restart

# --- playwright (pinned to scripts/self_update_pins.conf) -------------------
RUN python3 -m venv /opt/venvs/playwright \
 && /opt/venvs/playwright/bin/pip install -q "playwright==1.62.0" \
 && /opt/venvs/playwright/bin/playwright install chromium --with-deps \
 && /opt/venvs/playwright/bin/playwright install-deps chromium || true

# --- cua-driver (pinned binary, checksum-verified — same discipline as
# --- deploy/toolset-update.sh's cua-driver layer) -----------------------------
# Installs into the skeleton agent home's cua/bin (cua/ dir is copied below).
RUN set -e; \
    arch="$(uname -m)"; \
    case "$arch" in x86_64) a=x86_64 ;; aarch64) a=aarch64 ;; *) echo "unsupported arch $arch" >&2; exit 1 ;; esac; \
    tag="cua-driver-rs-v${CUA_DRIVER_VERSION}"; \
    asset="cua-driver-rs-${CUA_DRIVER_VERSION}-${a}-binary.tar.gz"; \
    base="https://github.com/trycua/cua/releases/download"; \
    work="$(mktemp -d)"; \
    curl -fsSL --max-time 300 -o "$work/checksums.txt" "$base/$tag/checksums.txt"; \
    curl -fsSL --max-time 600 -o "$work/$asset" "$base/$tag/$asset"; \
    want="$(grep -E "[[:space:]]$asset\$" "$work/checksums.txt" | awk '{print $1}')"; \
    test -n "$want" || { echo "cua-driver: no checksum entry for $asset" >&2; exit 1; }; \
    ( cd "$work" && printf '%s  %s\n' "$want" "$asset" | sha256sum -c - >/dev/null ); \
    members="$(tar -tzf "$work/$asset")"; \
    echo "$members" | grep -qE '(^/|(^|\/)\.\.)' && { echo "cua-driver: tarball has absolute or dot-dot members — refusing" >&2; exit 1; }; \
    mkdir -p /home/agent/cua/bin; \
    tar -xzf "$work/$asset" -C /home/agent/cua/bin; \
    rm -rf "$work"; \
    chmod 0755 /home/agent/cua/bin/cua-driver; \
    chown -R agent:agent /home/agent/cua

# --- CUA desktop stack + cred-ui (agent skeleton) -------------------------------
# cua/bin (cua-desktop.sh supervisor, cua-bridge.py, keepalive) is the
# orchestration the supervisord cua-stack program drives; the driver binary
# above landed in the same bin dir.
RUN mkdir -p /home/agent/cua \
 && cp -r /opt/sparkvm/cua/. /home/agent/cua/ \
 && chown -R agent:agent /home/agent/cua \
 && chmod 0755 /home/agent/cua/bin/cua-driver \
 && mkdir -p /home/agent/.local/bin /home/agent/.local/share/spark-vm \
 && chown -R agent:agent /home/agent/.local
# cred-ui runtime installs outside the checkout (cred-ui/install.sh):
# install to the skeleton agent home; first boot instantiates tenant users
# from /etc/skel (see below).
RUN CRED_UI_INSTALL_DIR=/home/agent/.local/share/spark-vm/cred-ui \
    SYSTEMD_USER_DIR=/tmp/cred-ui-systemd-unused \
    su agent -s /bin/bash -c 'bash /opt/sparkvm/cred-ui/install.sh' \
 && rm -rf /tmp/cred-ui-systemd-unused

# --- gate fixture (public dummy only — never a secret) ----------------------
# The manifest's baked[] names the gate fixture; install it at build time so
# the interactive gate (GOLDEN_IMAGE_GATE_PROCEDURE.md step 1) starts from a
# known state. The fixture credential value is the public dummy string
# GATE-FIXTURE-DUMMY-NOT-A-SECRET — it is baked into the repo on purpose.
RUN /opt/sparkvm/harness/install-gate-fixture.sh

# --- image manifest (the D-P1 artifact) --------------------------------------
# Records image_version (full SHA) + built_from_version (release tag) +
# baked[] + registry_paths + units. check-image-manifest.sh preflights it
# at gate time and the provision-time injector preflights it before box-live.
RUN /opt/sparkvm/harness/generate-image-manifest.sh --out /etc/sparkvm/image-manifest.json \
 && /opt/sparkvm/harness/check-image-manifest.sh /etc/sparkvm/image-manifest.json \
      --expect-version "$SPARKVM_SHA"

# --- skeleton home for first-boot tenant instantiation ------------------------
RUN cp -a /home/agent/. /etc/skel/ && chown -R root:root /etc/skel

# --- sshd: key-only, host keys generated on first boot -------------------------
# openssh-server's postinst generates host keys at PACKAGE INSTALL time —
# inside the docker build. Without the explicit removal below, every
# machine provisioned from this image would share ONE host keypair (the
# firstboot wrapper would find the keys present and become a permanent
# no-op). The removal is the design, not the scan: rm the baked keys here,
# document it, and pin it with a test so a future edit cannot silently
# drop the line.
COPY deploy/golden-image/sparkvm-sshd-firstboot.sh /usr/local/bin/sparkvm-sshd-firstboot.sh
COPY deploy/golden-image/supervisord.conf /etc/supervisor/conf.d/sparkvm.conf
RUN chmod 0755 /usr/local/bin/sparkvm-sshd-firstboot.sh \
 && rm -f /etc/ssh/ssh_host_* \
 && printf 'PasswordAuthentication no\nChallengeResponseAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n' \
      > /etc/ssh/sshd_config.d/sparkvm.conf \
 && chmod 0644 /etc/ssh/sshd_config.d/sparkvm.conf

# The baked-secrets discipline: no credential values, no private keys, no
# credential-shaped filenames anywhere in the baked tree. The gate's Step 0b
# scan (scan-baked-secrets.sh) runs against the built image in CI and by
# build-image.sh; it must exit 0 before the image publishes.

LABEL org.opencontainers.image.title="spark-vm golden image" \
      org.opencontainers.image.version="$SPARKVM_VERSION" \
      org.opencontainers.image.revision="$SPARKVM_SHA" \
      org.opencontainers.image.source="https://github.com/ntindle/spark-vm"

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
