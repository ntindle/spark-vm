#!/usr/bin/env python3
"""
cred-ui -- localhost-only web UI for the swapd credential store.

A small page for adding, listing, and removing credentials without
touching a terminal. Writes go through the same narrow sudo writers the
`cred` CLI uses:

    sudo -u swapd /usr/local/bin/cred-store-set <name>      (value on stdin)
    sudo -u swapd /usr/local/bin/cred-registry-set ...

Reads go through:

    sudo -u swapd cat /home/swapd/credentials.json
    sudo -u swapd ls /home/swapd/secrets

Security properties (keep them if you touch this file):

  - Binds 127.0.0.1 only. Reach it over an SSH tunnel; never expose it
    on a public interface.
  - NEVER returns a secret value in any response. The list endpoint
    returns names, placements, hosts, and a has_value flag only.
  - The set endpoint never logs the request body or the value.
  - Name/host/entry values are validated against strict regexes before
    they reach subprocess argv. No shell is used anywhere.
  - Every response carries Cache-Control: no-store.

Stdlib only.
"""

import json
import re
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIND = "127.0.0.1"
PORT = 18740

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ENTRY_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
HOST_RE = re.compile(r"^[A-Za-z0-9_.-]{1,253}(:[0-9]{1,5})?$")
HEADER_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
PARAM_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

STORE_SET = ["sudo", "-u", "swapd", "/usr/local/bin/cred-store-set"]
REGISTRY_SET = ["sudo", "-u", "swapd", "/usr/local/bin/cred-registry-set"]
REGISTRY_CAT = ["sudo", "-u", "swapd", "cat", "/home/swapd/credentials.json"]
SECRETS_LS = ["sudo", "-u", "swapd", "ls", "/home/swapd/secrets"]
SECRET_RM = ["sudo", "-u", "swapd", "rm"]


def run(argv, inp=None):
    p = subprocess.run(argv, input=inp, capture_output=True, timeout=15)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def read_registry():
    rc, out, _ = run(REGISTRY_CAT)
    if rc != 0:
        return {}
    try:
        reg = json.loads(out)
    except ValueError:
        return {}
    return reg if isinstance(reg, dict) else {}


def list_secret_names():
    rc, out, _ = run(SECRETS_LS)
    if rc != 0:
        return set()
    return {n for n in out.split() if NAME_RE.match(n)}


def snapshot():
    reg = read_registry()
    have = list_secret_names()
    creds = []
    for name in sorted(set(reg) | have):
        entry = reg.get(name, {}) if isinstance(reg.get(name), dict) else {}
        hosts = entry.get("allowed_hosts", [])
        placements = {
            k: v.get("placement") for k, v in entry.items()
            if k != "allowed_hosts" and isinstance(v, dict)
        }
        creds.append({
            "name": name,
            "has_value": name in have,
            "registered": name in reg,
            "allowed_hosts": hosts if isinstance(hosts, list) else [],
            "entries": placements,
        })
    return {"creds": creds}


def placement_json(kind, arg):
    if kind == "bearer_header":
        return json.dumps("bearer_header")
    if kind == "url_path_segment":
        return json.dumps("url_path_segment")
    if kind == "custom_header":
        if not HEADER_RE.match(arg or ""):
            raise ValueError("bad header name")
        return json.dumps({"custom_header": arg})
    if kind == "query_param":
        if not PARAM_RE.match(arg or ""):
            raise ValueError("bad query param name")
        return json.dumps({"query_param": arg})
    raise ValueError("unknown placement")


class Handler(BaseHTTPRequestHandler):
    server_version = "cred-ui/1.0"

    def log_message(self, fmt, *args):  # quieter logs; never log bodies
        pass

    def _send(self, code, obj, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n <= 0 or n > 1_000_000:
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return None

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            try:
                with open("index.html", "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(500, {"error": "index.html missing"})
        elif path == "/api/creds":
            try:
                self._send(200, snapshot())
            except Exception as e:  # noqa: BLE001
                self._send(500, {"error": "read failed: %s" % e})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        data = self._read_json()
        if data is None:
            self._send(400, {"error": "bad JSON body"})
            return
        try:
            if path == "/api/set":
                self._send(200, api_set(data))
            elif path == "/api/delete":
                self._send(200, api_delete(data))
            elif path == "/api/host/add":
                self._send(200, api_host(data, add=True))
            elif path == "/api/host/remove":
                self._send(200, api_host(data, add=False))
            else:
                self._send(404, {"error": "not found"})
        except ValueError as e:
            self._send(400, {"error": str(e)})
        except RuntimeError as e:
            self._send(500, {"error": str(e)})


def api_set(data):
    name = data.get("name", "")
    value = data.get("value", "")
    entry = data.get("entry", "access_token") or "access_token"
    kind = data.get("placement", "bearer_header")
    arg = data.get("placement_arg", "")
    hosts = data.get("hosts", []) or []

    if not NAME_RE.match(name):
        raise ValueError("bad credential name (use [A-Za-z0-9_-])")
    if not ENTRY_RE.match(entry) or entry == "allowed_hosts":
        raise ValueError("bad entry name")
    if not isinstance(value, str) or not value:
        raise ValueError("empty secret value")
    if not isinstance(hosts, list) or not all(HOST_RE.match(h or "") for h in hosts):
        raise ValueError("bad host (use hostname or hostname:port)")
    pjson = placement_json(kind, arg)

    # Secret values are stripped of a trailing newline only -- pastes from
    # password managers and textareas commonly include one.
    secret = value.rstrip("\r\n").encode("utf-8")

    rc, _, err = run(STORE_SET + [name], inp=secret)
    if rc != 0:
        raise RuntimeError("store failed: %s" % err.strip()[-200:])
    rc, _, err = run(REGISTRY_SET + ["set", name, entry, pjson])
    if rc != 0:
        raise RuntimeError("register failed (secret IS stored): %s" % err.strip()[-200:])
    for h in hosts:
        rc, _, err = run(REGISTRY_SET + ["add-host", name, h])
        if rc != 0:
            raise RuntimeError("add-host %s failed: %s" % (h, err.strip()[-200:]))
    return {"ok": True, "name": name}


def api_delete(data):
    name = data.get("name", "")
    if not NAME_RE.match(name):
        raise ValueError("bad credential name")
    # Remove the stored value (ignore "no such file" -- registry may exist alone).
    run(SECRET_RM + ["/home/swapd/secrets/" + name])
    rc, _, err = run(REGISTRY_SET + ["remove", name])
    if rc != 0 and "not registered" not in err:
        raise RuntimeError("unregister failed: %s" % err.strip()[-200:])
    return {"ok": True, "name": name}


def api_host(data, add):
    name = data.get("name", "")
    host = data.get("host", "")
    if not NAME_RE.match(name):
        raise ValueError("bad credential name")
    if not HOST_RE.match(host or ""):
        raise ValueError("bad host")
    rc, _, err = run(REGISTRY_SET + ["add-host" if add else "remove-host", name, host])
    if rc != 0:
        raise RuntimeError("host update failed: %s" % err.strip()[-200:])
    return {"ok": True}


def main():
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    print("cred-ui listening on http://%s:%d (localhost only)" % (BIND, PORT), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
