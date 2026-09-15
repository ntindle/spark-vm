#!/usr/bin/env python3
"""bdrived — the bdrive daemon.

Listens on a unix socket (/run/bdrive/bdrive.sock, mode 0770, owned by
bdrive, group bdrive-clients). The bdrive CLI (and, from the jail, the
orchestrator) speaks newline-delimited JSON. Every connection is peer-
checked with SO_PEERCRED (review finding 33): only the jail's mapped
agent uid and, later, the obox uid are accepted — group membership
alone is not the check.

Config (environment):
    BDRIVE_SOCKET     socket path (default /run/bdrive/bdrive.sock)
    BDRIVE_PEER_UIDS  comma-separated accepted peer uids
                      (default "2000000", the jail's mapped agent uid;
                      the obox uid is appended in round 9)
    ... plus driver.py's BDRIVE_* variables.

Protocol (one JSON object per line):
    {"op": "ping"} -> {"ok": true, "service": "bdrive", "v": 1}
    {"op": "open", "job": "j", "url": "..."} ->
        {"ok": true, "session": "s-...", "observation": {...}}
    {"op": "act", "session": "s-...", "ref_scope": "rs-...",
     "actions": [{...}]} ->
        {"ok": true, "receipts": [...], "observation": {...}}
    {"op": "close", "session": "s-..."} -> {"ok": true}
    {"op": "file_purchase_approval", "approval": {...}} ->
        {"ok": true, "id": "..."}

Errors: {"ok": false, "error": "..."}. A rejected peer gets its
connection closed with no response.
"""

import json
import os
import queue
import socket
import struct
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import driver  # noqa: E402

MAX_REQUEST_BYTES = 1024 * 1024
# The socket is world-connectable BY DESIGN: a userns-mapped peer (the
# jail agent at host uid 2000000+guest_uid) can never carry a host
# group, so DAC cannot be the gate. SO_PEERCRED in _handle is the
# gate (finding 33): non-peer uids are dropped before a single byte
# is read. The 0711 parent dir keeps the socket unlistable by others.
SOCK_MODE = 0o777


def peer_uid(conn):
    """SO_PEERCRED: (pid, uid, gid) of the connecting process."""
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                          struct.calcsize("iii"))
    _pid, uid, _gid = struct.unpack("iii", raw)
    return uid


def allowed_uids():
    raw = os.environ.get("BDRIVE_PEER_UIDS", "2000000")
    uids = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            uids.add(int(part))
    return uids


class Daemon:
    def __init__(self, socket_path=None):
        self.socket_path = socket_path or os.environ.get(
            "BDRIVE_SOCKET", "/run/bdrive/bdrive.sock")
        self.uids = allowed_uids()
        self.driver = driver.Driver()
        self.lock = threading.Lock()
        self._sock = None
        # Playwright's sync API is thread-affine: every driver call must
        # run in the thread that started it. Connections are handled on
        # per-connection threads (I/O isolation), so driver invocations
        # are marshalled to a single dedicated driver thread via a queue.
        self._tasks = queue.Queue()
        self._driver_thread = threading.Thread(target=self._drive,
                                               daemon=True)

    def _drive(self):
        """The only thread that ever touches driver/playwright."""
        while True:
            fn, ev, box = self._tasks.get()
            try:
                box["result"] = fn()
            except Exception as e:  # noqa: BLE001 - marshalled to caller
                box["error"] = e
            finally:
                ev.set()

    def _on_driver_thread(self, fn):
        """Run fn on the driver thread; re-raise its exceptions here."""
        ev = threading.Event()
        box = {}
        self._tasks.put((fn, ev, box))
        ev.wait()
        if "error" in box:
            raise box["error"]
        return box["result"]

    def log(self, msg):
        print("bdrived: %s" % msg, flush=True)

    def serve(self):
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        parent = os.path.dirname(self.socket_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(self.socket_path)
        os.chmod(self.socket_path, SOCK_MODE)
        # The parent dir is 0711 (set by the unit's RuntimeDirectoryMode):
        # anyone can traverse to the socket, nobody but the daemon can
        # list the dir. The mode is NOT the gate; SO_PEERCRED below is.
        self._sock.listen(16)
        self.log("listening on %s (peer uids: %s)"
                 % (self.socket_path, sorted(self.uids)))
        self._driver_thread.start()
        try:
            while True:
                conn, _ = self._sock.accept()
                t = threading.Thread(target=self._handle, args=(conn,),
                                     daemon=True)
                t.start()
        finally:
            self._sock.close()

    def _handle(self, conn):
        try:
            uid = peer_uid(conn)
        except OSError:
            conn.close()
            return
        if uid not in self.uids:
            # Finding 33: reject silently; group membership alone is
            # not the check.
            self.log("rejected peer uid %d" % uid)
            conn.close()
            return
        try:
            with conn:
                f = conn.makefile("r", encoding="utf-8")
                line = f.readline(MAX_REQUEST_BYTES + 2)
                if not line:
                    return
                try:
                    req = json.loads(line)
                except ValueError:
                    self._reply(conn, {"ok": False,
                                       "error": "invalid JSON"})
                    return
                with self.lock:
                    resp = self._dispatch(req)
                self._reply(conn, resp)
        except BrokenPipeError:
            pass
        except Exception as e:  # never kill the daemon on a bad request
            self.log("handler error: %s" % e)
            try:
                self._reply(conn, {"ok": False, "error": "internal"})
            except OSError:
                pass

    def _reply(self, conn, obj):
        conn.sendall((json.dumps(obj) + "\n").encode("utf-8"))

    def _dispatch(self, req):
        if not isinstance(req, dict):
            return {"ok": False, "error": "request must be an object"}
        op = req.get("op")
        try:
            if op == "ping":
                return {"ok": True, "service": "bdrive", "v": 1}
            if op == "open":
                sid, obs = self._on_driver_thread(
                    lambda: self.driver.open_session(
                        job=req.get("job"), url=req.get("url")))
                return {"ok": True, "session": sid, "observation": obs}
            if op == "act":
                receipts, obs = self._on_driver_thread(
                    lambda: self.driver.act(
                        req.get("session"), req.get("ref_scope"),
                        req.get("actions")))
                return {"ok": True, "receipts": receipts,
                        "observation": obs}
            if op == "close":
                self._on_driver_thread(
                    lambda: self.driver.close_session(req.get("session")))
                return {"ok": True}
            if op == "file_purchase_approval":
                aid = self.driver.file_purchase_approval(
                    req.get("approval"))
                return {"ok": True, "id": aid}
            return {"ok": False, "error": "unknown op: %r" % op}
        except driver.DriverError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            self.log("dispatch error: %s" % e)
            return {"ok": False, "error": "internal"}


def main():
    d = Daemon()
    d.serve()


if __name__ == "__main__":
    main()
