#!/usr/bin/env python3
"""bdrive v1 conformance tests — one per behavior.

Each test drives the real stack (Playwright Chromium + driver.py, and
the bdrived socket daemon) against a LOCAL dummy site. Credentials are
DUMMY PLACEHOLDERS ONLY ("hsurr:dummy:...") — no real values anywhere;
one test asserts the placeholder reaches the DOM literally, proving
bdrive never holds a real value.

Run:  python3 test_bdrive.py   (needs BDRIVE_* env left at defaults;
the suite overrides them itself)
"""
import base64
import html
import json
import os
import socket
import stat
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import driver as driver_mod
import bdrived as daemon_mod

# Dummy credentials: placeholders only. The swap proxy would replace
# these on egress; the dummy site is local so they must arrive
# literally — that is exactly what test_placeholder_stays_placeholder
# asserts.
DUMMY_USER = "hsurr:dummy:user"
DUMMY_PASS = "hsurr:dummy:pass"


# ---------------------------------------------------------------- dummy site
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, body, code=200, headers=None):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send("<h1>Home</h1>"
                       "<a href='/login'>login</a> "
                       "<a href='/buttons'>buttons</a> "
                       "<a href='/form'>form</a> "
                       "<a href='/cookie'>cookie</a> "
                       "<a href='/slow'>slow</a> "
                       "<a href='/a'>a</a>")
        elif path == "/login":
            self._send(
                "<h1>Login</h1>"
                "<form method='post' action='/login'>"
                "<label for='u'>Username</label>"
                "<input id='u' name='username' type='text'>"
                "<label for='p'>Password</label>"
                "<input id='p' name='password' type='password'>"
                "<button type='submit'>Sign in</button>"
                "</form>")
        elif path == "/buttons":
            self._send(
                "<h1>Buttons</h1>"
                "<button id='b1' onclick=\"this.textContent='Clicked!';"
                "this.setAttribute('data-done','1')\">Click me</button>")
        elif path == "/form":
            self._send(
                "<h1>Form</h1>"
                "<label>Query <input id='q' type='text' value='preset'></label>"
                "<label><input id='agree' type='checkbox'> I agree</label>"
                "<label>Color <select id='color'>"
                "<option value='red'>Red</option>"
                "<option value='green'>Green</option>"
                "<option value='blue'>Blue</option>"
                "</select></label>"
                "<input id='otp' type='text' aria-label='Code'>")
        elif path == "/cookie":
            self._send("<h1>Cookies</h1><div id='c'>none</div>"
                       "<script>document.getElementById('c').textContent="
                       "document.cookie || 'none';</script>",
                       headers={"Set-Cookie": "flavor=choc; Path=/"})
        elif path == "/slow":
            self._send("<h1>Slow</h1><div id='s'>waiting</div>"
                       "<script>setTimeout(() => {"
                       "document.getElementById('s').textContent='Ready!';"
                       "}, 1200);</script>")
        elif path == "/a":
            self._send("<h1>Page A</h1><a href='/b'>go to B</a>")
        elif path == "/b":
            self._send("<h1>Page B</h1><a href='/a'>go to A</a>")
        else:
            self._send("not found", code=404)

    def do_POST(self):
        if urlparse(self.path).path == "/login":
            n = int(self.headers.get("Content-Length", 0))
            fields = parse_qs(self.rfile.read(n).decode("utf-8"))
            user = fields.get("username", [""])[0]
            self._send("<h1>Welcome, %s</h1>" % html.escape(user))
        else:
            self._send("not found", code=404)


class DummySite:
    def __init__(self):
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever,
                                       daemon=True)

    @property
    def base(self):
        return "http://127.0.0.1:%d" % self.port

    def start(self):
        self.thread.start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()


# ---------------------------------------------------------------- helpers
def _env(**over):
    env = {
        "BDRIVE_PROXY": "",  # dummy site is local; proxy is a deploy concern
        "BDRIVE_HEADLESS": "1",
    }
    env.update(over)
    return env


class DriverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old = dict(os.environ)
        tmpbase = cls._tmp("base")
        # First-use is confirmed for the class-scoped driver; dedicated
        # tests below cover the gate itself.
        marker = os.path.join(tmpbase, "first-use-confirmed")
        os.makedirs(tmpbase, exist_ok=True)
        with open(marker, "w") as f:
            f.write("test")
        os.environ.update(_env(BDRIVE_PROFILE_DIR=cls._tmp("profile"),
                               BDRIVE_SHOTS_DIR=cls._tmp("shots"),
                               BDRIVE_FIRST_USE_FILE=marker))
        cls.site = DummySite()
        cls.site.start()
        cls.drv = driver_mod.Driver()
        cls.drv.start()

    @classmethod
    def _tmp(cls, name):
        import tempfile
        d = tempfile.mkdtemp(prefix="bdrive-test-")
        return os.path.join(d, name)

    @classmethod
    def tearDownClass(cls):
        cls.drv.stop()
        cls.site.stop()
        os.environ.clear()
        os.environ.update(cls._old)

    def setUp(self):
        self.base = self.site.base

    def _open(self, url=None):
        sid, obs = self.drv.open_session(job="test-job", url=url)
        self.addCleanup(self.drv.close_session, sid)
        return sid, obs

    def _act(self, sid, actions, ref_scope=None):
        return self.drv.act(sid, ref_scope, actions)

    def _ref(self, obs, role, name_part):
        for line in obs["ax"].splitlines():
            if "[%s]" % role in line and name_part in line:
                return line.split()[0]
        self.fail("no %s ref containing %r in:\n%s"
                  % (role, name_part, obs["ax"]))

    def _fill(self, sid, obs, name_part, text, **kw):
        """Fill a textbox by name; returns the new observation."""
        ref = self._ref(obs, "textbox", name_part)
        _, obs2 = self._act(sid, [{"action": "fill", "ref": ref,
                                   "text": text, **kw}],
                            ref_scope=obs["ref_scope"])
        return obs2

    def _run_in_thread(self, fn):
        """Run fn on a worker thread and return its result (re-raising).

        Playwright's sync API is thread-affine: a second Driver cannot
        start in the main thread while the class-scoped Driver is
        alive, so tests needing their own Driver run it here.
        """
        box = {}

        def run():
            try:
                box["result"] = fn()
            except Exception as e:  # noqa: BLE001 - re-raised below
                box["error"] = e

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(180)
        if "error" in box:
            raise box["error"]
        return box.get("result")

    # -- sessions and state -------------------------------------------
    def test_open_returns_session_and_state(self):
        sid, obs = self._open(self.base + "/")
        self.assertTrue(sid.startswith("s-"))
        self.assertIn("Home", obs["title"] or obs["ax"])
        self.assertTrue(obs["url"].startswith(self.base))
        self.assertTrue(obs["ref_scope"].startswith("rs-"))

    def test_goto_navigates(self):
        sid, obs = self._open()
        receipts, obs2 = self._act(sid, [{"action": "goto",
                                          "url": self.base + "/login"}])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertTrue(obs2["url"].endswith("/login"))

    def test_goto_rejects_non_http(self):
        sid, _ = self._open()
        with self.assertRaises(driver_mod.DriverError):
            self._act(sid, [{"action": "goto",
                             "url": "ftp://example.com/x"}])

    def test_snapshot_lists_refs(self):
        sid, obs = self._open(self.base + "/login")
        receipts, obs2 = self._act(sid, [{"action": "snapshot"}],
                                   ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertIn("@e", obs2["ax"])
        self.assertIn("[textbox]", obs2["ax"])
        self.assertIn("[button]", obs2["ax"])
        self.assertNotEqual(obs["ref_scope"], obs2["ref_scope"])

    # -- clicking / typing --------------------------------------------
    def test_click_button(self):
        sid, obs = self._open(self.base + "/buttons")
        ref = self._ref(obs, "button", "Click me")
        receipts, obs2 = self._act(sid, [{"action": "click", "ref": ref}],
                                   ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertIn("Clicked!", obs2["ax"])

    def test_fill_replaces(self):
        sid, obs = self._open(self.base + "/form")
        ref = self._ref(obs, "textbox", "Query")
        receipts, obs2 = self._act(
            sid, [{"action": "fill", "ref": ref, "text": "hello"}],
            ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        # fill REPLACES: the preset value is gone
        self.assertNotIn('value="preset"', obs2["ax"])
        self.assertIn('value="hello"', obs2["ax"])

    def test_type_appends(self):
        sid, obs = self._open(self.base + "/form")
        ref = self._ref(obs, "textbox", "Query")
        self._act(sid, [{"action": "type", "ref": ref, "text": "+more"}],
                  ref_scope=obs["ref_scope"])
        _, obs2 = self._act(sid, [{"action": "snapshot"}])
        self.assertIn('value="preset+more"', obs2["ax"])

    def test_press_enter_submits(self):
        sid, obs = self._open(self.base + "/login")
        obs = self._fill(sid, obs, "Username", DUMMY_USER)
        obs = self._fill(sid, obs, "Password", DUMMY_PASS)
        pref = self._ref(obs, "textbox", "Password")
        receipts, obs2 = self._act(
            sid, [{"action": "press", "key": "Enter", "ref": pref}],
            ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertIn("Welcome", obs2["ax"] + obs2["title"])

    def test_select_option(self):
        sid, obs = self._open(self.base + "/form")
        ref = self._ref(obs, "combobox", "Color")
        receipts, _ = self._act(
            sid, [{"action": "select", "ref": ref, "value": "green"}],
            ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertEqual(receipts[0]["selected"], ["green"])

    def test_select_rejects_non_select(self):
        sid, obs = self._open(self.base + "/form")
        ref = self._ref(obs, "textbox", "Query")
        receipts, _ = self._act(
            sid, [{"action": "select", "ref": ref, "value": "x"}],
            ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "not_started")
        self.assertEqual(receipts[0]["actionability_reason"], "not_select")

    def test_check_checkbox(self):
        sid, obs = self._open(self.base + "/form")
        ref = self._ref(obs, "checkbox", "I agree")
        self.assertIn("(unchecked)", obs["ax"])
        receipts, obs2 = self._act(sid, [{"action": "check", "ref": ref}],
                                    ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertIn("(checked)", obs2["ax"])

    # -- observation ----------------------------------------------------
    def test_look_png(self):
        sid, obs = self._open(self.base + "/")
        receipts, _ = self._act(sid, [{"action": "look"}],
                                ref_scope=obs["ref_scope"])
        r = receipts[0]
        self.assertEqual(r["status"], "completed")
        raw = base64.b64decode(r["png_base64"])
        self.assertTrue(raw.startswith(b"\x89PNG"))
        self.assertTrue(os.path.isfile(r["path"]))

    def test_get_text_page(self):
        sid, obs = self._open(self.base + "/a")
        receipts, _ = self._act(sid, [{"action": "get_text"}],
                                ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertIn("Page A", receipts[0]["text"])

    def test_get_text_password_refused(self):
        # Spec section 11: no read-back path for password inputs.
        sid, obs = self._open(self.base + "/login")
        ref = self._ref(obs, "textbox", "Password")
        receipts, _ = self._act(sid, [{"action": "get_text", "ref": ref}],
                                ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "not_started")
        self.assertEqual(receipts[0]["actionability_reason"],
                         "read_restricted")

    def test_sensitive_fill_masks(self):
        # A field filled with a relayed value (OTP): the snapshot hides
        # its value and ref-scoped get_text is refused.
        sid, obs = self._open(self.base + "/form")
        ref = self._ref(obs, "textbox", "Code")
        receipts, obs2 = self._act(
            sid, [{"action": "fill", "ref": ref, "text": "123456",
                   "sensitive": True}],
            ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertNotIn("123456", obs2["ax"])
        receipts2, _ = self._act(
            sid, [{"action": "get_text", "ref": ref}],
            ref_scope=obs2["ref_scope"])
        self.assertEqual(receipts2[0]["status"], "not_started")
        self.assertEqual(receipts2[0]["actionability_reason"],
                         "read_restricted")

    def test_wait_text_appears(self):
        sid, obs = self._open(self.base + "/slow")
        receipts, _ = self._act(sid, [{"action": "wait", "text": "Ready!"}],
                                ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")

    def test_wait_needs_exactly_one(self):
        sid, obs = self._open(self.base + "/")
        with self.assertRaises(driver_mod.DriverError):
            self._act(sid, [{"action": "wait"}], ref_scope=obs["ref_scope"])

    # -- navigation -----------------------------------------------------
    def test_back_and_reload(self):
        sid, obs = self._open(self.base + "/a")
        self._act(sid, [{"action": "goto", "url": self.base + "/b"}])
        receipts, obs2 = self._act(sid, [{"action": "back"}])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertTrue(obs2["url"].endswith("/a"))
        receipts, _ = self._act(sid, [{"action": "reload"}])
        self.assertEqual(receipts[0]["status"], "completed")

    def test_cookies_clear(self):
        sid, _ = self._open(self.base + "/cookie")
        _, obs = self._act(sid, [{"action": "get_text"}])
        receipts, _ = self._act(sid, [{"action": "cookies_clear"}])
        self.assertEqual(receipts[0]["status"], "completed")
        # fresh page load: the Set-Cookie fires again, so verify via the
        # context directly that the jar is empty.
        cookies = self.drv._ctx.cookies()
        self.assertEqual(cookies, [])

    def test_open_action_new_tab(self):
        sid, obs = self._open(self.base + "/a")
        receipts, obs2 = self._act(sid, [{"action": "open",
                                          "url": self.base + "/b"}],
                                   ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertTrue(obs2["url"].endswith("/b"))

    # -- receipts and guards --------------------------------------------
    def test_unknown_action_rejected(self):
        sid, obs = self._open(self.base + "/")
        with self.assertRaises(driver_mod.DriverError) as cm:
            self._act(sid, [{"action": "frobnicate"}],
                      ref_scope=obs["ref_scope"])
        self.assertIn("not in the v1 set", str(cm.exception))

    def test_v1_1_actions_rejected(self):
        # hover/scroll/fill_card are v1.1, not v1.
        sid, obs = self._open(self.base + "/")
        for name in ("hover", "scroll", "fill_card", "get_html",
                     "upload", "download"):
            with self.assertRaises(driver_mod.DriverError,
                                   msg=name):
                self._act(sid, [{"action": name}], ref_scope=obs["ref_scope"])

    def test_stale_ref_scope_rejected(self):
        sid, obs = self._open(self.base + "/buttons")
        ref = self._ref(obs, "button", "Click me")
        self._act(sid, [{"action": "snapshot"}])  # new scope issued
        receipts, _ = self._act(sid, [{"action": "click", "ref": ref}],
                                ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "not_started")
        self.assertEqual(receipts[0]["actionability_reason"], "stale_ref")

    def test_post_navigation_rule(self):
        sid, obs = self._open(self.base + "/")
        ref = self._ref(obs, "link", "login")
        receipts, _ = self._act(
            sid, [{"action": "goto", "url": self.base + "/a"},
                  {"action": "click", "ref": ref}],
            ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "completed")
        self.assertEqual(receipts[1]["status"], "not_started")
        self.assertEqual(receipts[1]["actionability_reason"],
                         "post_navigation")

    def test_post_navigation_allows_look(self):
        sid, obs = self._open(self.base + "/")
        receipts, _ = self._act(
            sid, [{"action": "goto", "url": self.base + "/a"},
                  {"action": "look"}],
            ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[1]["status"], "completed")

    def test_first_failure_stops_array(self):
        sid, obs = self._open(self.base + "/buttons")
        receipts, _ = self._act(
            sid, [{"action": "click", "ref": "@e999"},
                  {"action": "snapshot"}],
            ref_scope=obs["ref_scope"])
        self.assertEqual(receipts[0]["status"], "not_started")
        self.assertEqual(receipts[1]["status"], "not_started")
        self.assertEqual(receipts[1]["actionability_reason"], "aborted")

    def test_proxy_health_gate_refuses_open(self):
        def run():
            old = dict(os.environ)
            os.environ.update(_env(BDRIVE_PROXY="http://127.0.0.1:1",
                                   BDRIVE_PROFILE_DIR=self._tmp("p2")))
            try:
                d2 = driver_mod.Driver()
                try:
                    d2.open_session()
                    return "no-error"
                except driver_mod.DriverError as e:
                    return "gate: %s" % e
            finally:
                os.environ.clear()
                os.environ.update(old)

        result = self._run_in_thread(run)
        self.assertIn("proxy unhealthy", result, result)

    def test_placeholder_stays_placeholder(self):
        # bdrive never holds a real value: the dummy placeholder must
        # reach the DOM literally (the swap happens at egress).
        sid, obs = self._open(self.base + "/login")
        ref = self._ref(obs, "textbox", "Password")
        self._act(sid, [{"action": "fill", "ref": ref, "text": DUMMY_PASS}],
                  ref_scope=obs["ref_scope"])
        val = self.drv._get_session(sid).page.locator(
            "xpath=" + self.drv._get_session(sid).refs[ref]["xpath"]
        ).input_value()
        self.assertEqual(val, DUMMY_PASS)

    def test_session_expiry(self):
        def run():
            old = dict(os.environ)
            marker = os.path.join(self._tmp("fu-ok"), "m")
            os.makedirs(os.path.dirname(marker), exist_ok=True)
            with open(marker, "w") as f:
                f.write("test")
            os.environ.update(_env(BDRIVE_SESSION_TTL="0",
                                   BDRIVE_PROFILE_DIR=self._tmp("p3"),
                                   BDRIVE_FIRST_USE_FILE=marker))
            try:
                d2 = driver_mod.Driver()
                d2.start()
                try:
                    sid, _ = d2.open_session()
                    time.sleep(0.05)
                    try:
                        d2.act(sid, None, [{"action": "snapshot"}])
                        return "no-error"
                    except driver_mod.DriverError as e:
                        return "expired: %s" % e
                finally:
                    d2.stop()
            finally:
                os.environ.clear()
                os.environ.update(old)

        result = self._run_in_thread(run)
        self.assertIn("unknown or expired", result, result)

    # -- first-use confirmation (spec section 16) -----------------------
    def _first_use_driver(self, marker_path, approvals_dir):
        """Build a driver whose first use is NOT confirmed."""
        os.makedirs(approvals_dir, exist_ok=True)
        if os.path.exists(marker_path):
            os.unlink(marker_path)
        old = dict(os.environ)
        os.environ.update(_env(
            BDRIVE_PROFILE_DIR=self._tmp("p-fu"),
            BDRIVE_FIRST_USE_FILE=marker_path,
            BDRIVE_APPROVALS_DIR=approvals_dir))
        return old

    def test_first_use_blocks_open_and_files_request(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="bdrive-fu-")
        marker = os.path.join(tmp, "first-use-confirmed")
        pending = os.path.join(tmp, "pending")

        def run():
            old = self._first_use_driver(marker, pending)
            try:
                d2 = driver_mod.Driver()
                d2.start()
                try:
                    try:
                        d2.open_session(job="job-fu")
                        return "no-error"
                    except driver_mod.DriverError as e:
                        return "blocked: %s" % e
                finally:
                    d2.stop()
            finally:
                os.environ.clear()
                os.environ.update(old)

        result = self._run_in_thread(run)
        self.assertIn("first_use_confirmation_required", result, result)
        # A structured first-use request is now pending for the human.
        names = os.listdir(pending)
        self.assertEqual(len(names), 1, names)
        with open(os.path.join(pending, names[0])) as f:
            item = json.load(f)
        self.assertEqual(item["kind"], "first_use")
        self.assertEqual(item["job"], "job-fu")
        self.assertIn(item["id"], result)
        mode = stat.S_IMODE(os.stat(os.path.join(pending,
                                                 names[0])).st_mode)
        self.assertEqual(mode, 0o640)

    def test_first_use_files_only_once(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="bdrive-fu2-")
        marker = os.path.join(tmp, "first-use-confirmed")
        pending = os.path.join(tmp, "pending")

        def run():
            old = self._first_use_driver(marker, pending)
            try:
                d2 = driver_mod.Driver()
                d2.start()
                try:
                    for _ in range(2):
                        try:
                            d2.open_session()
                        except driver_mod.DriverError:
                            pass
                    return os.listdir(pending)
                finally:
                    d2.stop()
            finally:
                os.environ.clear()
                os.environ.update(old)

        names = self._run_in_thread(run)
        self.assertEqual(len(names), 1, names)

    def test_first_use_marker_allows_open(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="bdrive-fu3-")
        marker = os.path.join(tmp, "first-use-confirmed")
        pending = os.path.join(tmp, "pending")
        # The human approved on the grant channel page: the marker exists.
        os.makedirs(tmp, exist_ok=True)
        with open(marker, "w") as f:
            json.dump({"approval_id": "fu-test", "answered_by": "human"},
                      f)

        def run():
            old = dict(os.environ)
            os.environ.update(_env(
                BDRIVE_PROFILE_DIR=self._tmp("p-fu3"),
                BDRIVE_FIRST_USE_FILE=marker,
                BDRIVE_APPROVALS_DIR=pending))
            try:
                d2 = driver_mod.Driver()
                d2.start()
                try:
                    sid, _ = d2.open_session(
                        job="job-fu", url=self.site.base + "/")
                    d2.close_session(sid)
                    return "opened"
                finally:
                    d2.stop()
            finally:
                os.environ.clear()
                os.environ.update(old)

        self.assertEqual(self._run_in_thread(run), "opened")
        # Confirmed first use files nothing.
        self.assertFalse(os.path.exists(pending) and
                         os.listdir(pending))


class DaemonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old = dict(os.environ)
        import tempfile
        cls.tmp = tempfile.mkdtemp(prefix="bdrived-test-")
        marker = os.path.join(cls.tmp, "first-use-confirmed")
        with open(marker, "w") as f:
            f.write("test")
        os.environ.update(_env(
            BDRIVE_SOCKET=os.path.join(cls.tmp, "bdrive.sock"),
            BDRIVE_PEER_UIDS=str(os.getuid()),
            BDRIVE_PROFILE_DIR=os.path.join(cls.tmp, "profile"),
            BDRIVE_SHOTS_DIR=os.path.join(cls.tmp, "shots"),
            BDRIVE_APPROVALS_DIR=os.path.join(cls.tmp, "pending"),
            BDRIVE_FIRST_USE_FILE=marker))
        cls.site = DummySite()
        cls.site.start()
        cls.daemon = daemon_mod.Daemon()
        cls.thread = threading.Thread(target=cls.daemon.serve, daemon=True)
        cls.thread.start()
        time.sleep(0.5)
        cls.sock_path = os.environ["BDRIVE_SOCKET"]

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()
        os.environ.clear()
        os.environ.update(cls._old)

    def _call(self, req):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.sock_path)
        with s:
            s.sendall((json.dumps(req) + "\n").encode())
            chunks = []
            while True:
                data = s.recv(65536)
                if not data:
                    break
                chunks.append(data)
        return json.loads(b"".join(chunks).decode())

    def test_daemon_ping_ok(self):
        resp = self._call({"op": "ping"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["service"], "bdrive")

    def test_daemon_rejects_bad_peer(self):
        # Finding 33: SO_PEERCRED, not group membership, is the check.
        # Swap the allowlist to a uid that is not us; the daemon must
        # close the connection with no response.
        old = self.daemon.uids
        self.daemon.uids = {1}
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.sock_path)
            s.settimeout(3)
            with s:
                s.sendall(b'{"op":"ping"}\n')
                try:
                    data = s.recv(1024)
                except ConnectionResetError:
                    # The daemon closed without reading our bytes, so
                    # the kernel RST instead of FIN — still zero bytes.
                    data = b""
            self.assertEqual(data, b"")
        finally:
            self.daemon.uids = old

    def test_daemon_act_roundtrip(self):
        r = self._call({"op": "open", "job": "j1",
                        "url": self.site.base + "/buttons"})
        self.assertTrue(r["ok"], r)
        sid, obs = r["session"], r["observation"]
        self.addCleanup(self._call, {"op": "close", "session": sid})
        ref = next(l.split()[0] for l in obs["ax"].splitlines()
                   if "[button]" in l and "Click me" in l)
        r2 = self._call({"op": "act", "session": sid,
                         "ref_scope": obs["ref_scope"],
                         "actions": [{"action": "click", "ref": ref}]})
        self.assertTrue(r2["ok"], r2)
        self.assertEqual(r2["receipts"][0]["status"], "completed")
        self.assertIn("Clicked!", r2["observation"]["ax"])

    def test_daemon_unknown_op(self):
        resp = self._call({"op": "brew_coffee"})
        self.assertFalse(resp["ok"])

    def test_file_purchase_approval_structured(self):
        # Findings 49/50: structured fields; the requester comes from
        # the file owner (this process), never an argument.
        approval = {"host": "example.com", "amount": 42.50,
                    "currency": "usd", "job": "job-9",
                    "purpose": "test widget x1"}
        resp = self._call({"op": "file_purchase_approval",
                           "approval": approval})
        self.assertTrue(resp["ok"], resp)
        path = os.path.join(os.environ["BDRIVE_APPROVALS_DIR"],
                            resp["id"] + ".json")
        self.assertTrue(os.path.isfile(path))
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o640)
        with open(path) as f:
            item = json.load(f)
        self.assertEqual(item["kind"], "purchase")
        self.assertEqual(item["host"], "example.com")
        self.assertEqual(item["amount"], 42.50)
        self.assertEqual(item["currency"], "USD")
        self.assertEqual(item["job"], "job-9")
        self.assertTrue(item["purpose_untrusted"])
        # Finding 50: the owner is the filer — confirmd maps owner to
        # requester and accepts only bdrive/swapd.
        self.assertEqual(os.stat(path).st_uid, os.getuid())

    def test_file_purchase_approval_validation(self):
        bad = {"host": "example.com", "amount": -5,
               "currency": "USD", "job": "j"}
        resp = self._call({"op": "file_purchase_approval",
                           "approval": bad})
        self.assertFalse(resp["ok"])
        self.assertIn("amount", resp["error"])
        bad2 = {"host": "", "amount": 5, "currency": "USD", "job": "j"}
        resp2 = self._call({"op": "file_purchase_approval",
                            "approval": bad2})
        self.assertFalse(resp2["ok"])

    def test_cli_ping(self):
        import subprocess
        env = dict(os.environ)
        p = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "bdrive"), "ping"],
            capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('"ok": true', p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
