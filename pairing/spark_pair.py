#!/usr/bin/env python3
"""spark-pair: pairing-code box enrollment client for the spark-vm control plane.

Implements issue #844's box side and the human-approval side:

  Box (no inbound ports; everything is outbound HTTPS to the control plane):
    spark-pair.py init                      # generate ed25519 keypair locally
    spark-pair.py request --name mybox       # ask control plane for a code
    spark-pair.py redeem                     # wait for approval, prove key
                                             # possession, save the box token

  Owner (any machine; needs an owner API key):
    spark-pair.py approve --pairing-id <id>  # verify fingerprint, approve

The private key never leaves the box. The pairing code expires (15 min).
The bearer token issued at redeem is short-lived (24 h); rotation is #846.

Stdlib only. State lives in ~/.config/spark-pair (override with --dir or
SVM_PAIR_DIR). Key/token files are written mode 0600. Nothing secret is
ever printed.
"""
import argparse
import base64
import getpass
import json
import os
import sys
import time
import urllib.request
import urllib.error

import ed25519

DEFAULT_CONTROL = "https://api.sparkvm.dev"
USER_AGENT = "spark-pair/1"
POLL_INTERVAL = 5


def _state_dir(args):
    d = args.dir or os.environ.get("SVM_PAIR_DIR") or os.path.expanduser(
        "~/.config/spark-pair")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def _write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _read_json_file(path):
    with open(path) as f:
        return json.load(f)


def _http(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"User-Agent": USER_AGENT,
                 "Content-Type": "application/json",
                 **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"ok": False, "error": f"http={e.code}"}
        return e.code, payload
    except Exception as e:  # network down, DNS, TLS...
        return 0, {"ok": False, "error": f"transport: {e}"}


def _key_paths(d):
    return (os.path.join(d, "box.key"), os.path.join(d, "box.pub"))


def cmd_init(args):
    key_path, pub_path = _key_paths(_state_dir(args))
    if os.path.exists(key_path) and not args.force:
        print(f"key already exists at {key_path} (use --force to replace)")
        return 1
    seed, pub = ed25519.generate_keypair()
    _write_private(key_path, base64.b64encode(seed))
    with open(pub_path, "w") as f:
        f.write(base64.b64encode(pub).decode())
    print(f"keypair written to {key_path} (0600) + {pub_path}")
    print()
    print("Box key fingerprint — the owner must verify this at approval:")
    print("  " + ed25519.fingerprint(pub))
    return 0


def cmd_request(args):
    d = _state_dir(args)
    key_path, pub_path = _key_paths(d)
    if not os.path.exists(key_path):
        print("no keypair yet — run `spark-pair.py init` first")
        return 1
    seed = base64.b64decode(open(key_path, "rb").read())
    pub = base64.b64decode(open(pub_path).read())
    if ed25519.publickey_from_seed(seed) != pub:
        print("key/pub mismatch — refusing to request (re-run init --force)")
        return 1
    control = args.control or os.environ.get("SVM_CONTROL") or DEFAULT_CONTROL
    status, resp = _http("POST", control.rstrip("/") + "/v1/pairing/request",
                         {"name": args.name,
                          "pubkey": base64.b64encode(pub).decode(),
                          "fingerprint": ed25519.fingerprint(pub)})
    if status != 201 or not resp.get("ok"):
        print(f"request failed: {resp.get('error', status)}")
        return 1
    # The single-use code lives here until redeem: 0600 like the key.
    _write_private(os.path.join(d, "pairing.json"),
                   json.dumps({"pairing_id": resp["pairing_id"],
                               "code": resp["code"],
                               "expires_at": resp["expires_at"],
                               "control": control}, indent=2).encode())
    mins = max(1, int((resp["expires_at"] - time.time()) // 60))
    print()
    print("  Give this pairing code to the box owner:")
    print()
    print(f"    {resp['code']}")
    print()
    print("  And confirm the key fingerprint matches what the box shows:")
    print(f"    {ed25519.fingerprint(pub)}")
    print()
    print(f"  Code expires in ~{mins} min. Then run: spark-pair.py redeem")
    return 0


def cmd_redeem(args):
    d = _state_dir(args)
    key_path, _ = _key_paths(d)
    pairing_path = os.path.join(d, "pairing.json")
    if not os.path.exists(key_path) or not os.path.exists(pairing_path):
        print("need `init` + `request` first")
        return 1
    seed = base64.b64decode(open(key_path, "rb").read())
    pairing = _read_json_file(pairing_path)
    control = (args.control or pairing.get("control")
               or os.environ.get("SVM_CONTROL") or DEFAULT_CONTROL)
    pid = pairing["pairing_id"]
    base = control.rstrip("/") + f"/v1/pairing/{pid}"

    deadline = pairing["expires_at"]
    print("Waiting for owner approval (Ctrl-C to stop, re-run to resume)...")
    challenge = None
    while True:
        if time.time() > deadline:
            print("pairing expired — run `request` again for a fresh code")
            return 1
        status, resp = _http("GET", base + "/status")
        if status == 410 or resp.get("status") in ("expired", "consumed"):
            print(f"pairing {resp.get('status', 'gone')} — run `request` again")
            return 1
        if status != 200 or not resp.get("ok"):
            print(f"status check failed: {resp.get('error', status)}")
            return 1
        if resp.get("status") == "approved" and resp.get("challenge"):
            challenge = resp["challenge"]
            break
        time.sleep(POLL_INTERVAL)

    # Prove possession: sign the server-issued challenge with the box key.
    sig = ed25519.sign(seed, base64.b64decode(challenge))
    status, resp = _http("POST", base + "/redeem",
                         {"signature": base64.b64encode(sig).decode()})
    if status != 201 or not resp.get("ok"):
        print(f"redeem failed: {resp.get('error', status)}")
        return 1
    enroll_path = os.path.join(d, "enrollment.json")
    _write_private(enroll_path, json.dumps(
        {"box_id": resp["box_id"], "token": resp["token"],
         "token_expires_at": resp["token_expires_at"],
         "control": control}, indent=2).encode())
    os.remove(pairing_path)
    print(f"enrolled as {resp['box_id']} — token saved to {enroll_path} (0600)")
    exp = time.strftime("%Y-%m-%d %H:%M %Z",
                        time.localtime(resp["token_expires_at"]))
    print(f"token expires {exp} (rotation: issue #846)")
    return 0


def _owner_key(args):
    key = args.owner_key or os.environ.get("SVM_OWNER_KEY")
    if not key:
        key = getpass.getpass("Owner API key: ").strip()
    if not key:
        print("owner API key required (SVM_OWNER_KEY or --owner-key)")
        sys.exit(1)
    return key


def cmd_approve(args):
    control = args.control or os.environ.get("SVM_CONTROL") or DEFAULT_CONTROL
    base = control.rstrip("/") + "/v1/pairing"
    if args.bootstrap:
        # One-shot fresh-database bootstrap: no owner key exists yet, so the
        # server accepts the typed pairing code with no Authorization
        # header (see pairing/README.md). Requires --pairing-id: there is
        # no owner key to list with.
        if not args.pairing_id:
            print("--bootstrap requires --pairing-id (no owner key to list with)")
            return 1
        auth = {}
    else:
        auth = {"Authorization": "Bearer " + _owner_key(args)}

    if args.pairing_id:
        pid = args.pairing_id
    else:
        status, resp = _http("GET", base, headers=auth)
        if status != 200 or not resp.get("ok"):
            print(f"list failed: {resp.get('error', status)}")
            return 1
        pairs = resp.get("pairings", [])
        if not pairs:
            print("no pending pairings")
            return 0
        print("Pending pairings:")
        for p in pairs:
            # The server never returns pairing codes (stored hashed);
            # match by the id the box printed at request time.
            print(f"  {p['id']}  {p['box_name']}  {p['fingerprint']}")
        print()
        pid = input("Pairing id to approve: ").strip()
    if not pid:
        print("no pairing selected")
        return 1

    status, resp = _http("GET", f"{base}/{pid}", headers=auth)
    if status != 200 or not resp.get("ok"):
        print(f"fetch failed: {resp.get('error', status)}")
        return 1
    p = resp["pairing"]
    if p["status"] != "pending":
        print(f"pairing is {p['status']} — nothing to approve")
        return 1
    print()
    print(f"  Box name:    {p['box_name']}")
    print(f"  Fingerprint: {p['fingerprint']}")
    print()
    print("Compare the fingerprint above with what the BOX displays.")
    print("They must match exactly — otherwise someone is enrolling")
    print("a different key under this box's name.")
    code = input("Type the pairing code shown on the box to approve: ").strip()
    if not code:
        print("approval aborted")
        return 1
    # The server normalizes (case/spacing/dashes) and compares against the
    # stored code hash; a mismatch is a 403 and nothing is approved.
    status, resp = _http("POST", f"{base}/{pid}/approve", {"code": code},
                         headers=auth)
    if status != 200 or not resp.get("ok"):
        print(f"approve failed: {resp.get('error', status)}")
        return 1
    print(f"approved {pid} — the box can now redeem its token")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="spark-pair",
                                 description="pairing-code box enrollment")
    ap.add_argument("--dir", help="state dir (default ~/.config/spark-pair)")
    ap.add_argument("--control", help="control-plane base URL")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="generate the box ed25519 keypair")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("request", help="request a pairing code")
    s.add_argument("--name", required=True, help="human box name")
    s.set_defaults(fn=cmd_request)

    s = sub.add_parser("redeem", help="wait for approval, redeem box token")
    s.set_defaults(fn=cmd_redeem)

    s = sub.add_parser("approve", help="owner: verify fingerprint + approve")
    s.add_argument("--pairing-id", help="pairing id (lists pending if omitted)")
    s.add_argument("--owner-key", help="owner API key (else SVM_OWNER_KEY)")
    s.add_argument("--bootstrap", action="store_true",
                   help="fresh-database bootstrap: no owner key yet; the "
                        "typed pairing code alone approves (requires "
                        "--pairing-id)")
    s.set_defaults(fn=cmd_approve)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
