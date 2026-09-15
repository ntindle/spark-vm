#!/usr/bin/env python3
"""bdrive driver core — Playwright browser automation, narrow action set.

Round 8 (spec section 16.1): the v1 action set only —
    open, goto, snapshot, click, fill, type, press, select, check,
    look, get_text, wait, back, reload, state, cookies_clear
Anything outside this set is rejected, not interpreted. No eval, no
shell, no CDP, no file access outside the profile.

Runs inside bdrived (as the bdrive user on the host); importable for
tests against a local dummy site with dummy credentials.

Config (environment):
    BDRIVE_PROFILE_DIR   persistent Chromium profile (default
                         /home/bdrive/profile)
    BDRIVE_PROXY         proxy server URL for all browser traffic
                         (default http://127.0.0.1:18080); empty
                         disables the proxy (tests only)
    BDRIVE_HEADLESS      1/0 (default 1)
    BDRIVE_APPROVALS_DIR pending-approvals dir (default
                         /home/swapd/approvals/pending)
    BDRIVE_SHOTS_DIR     where `look` saves PNGs (default
                         /home/bdrive/shots)
    BDRIVE_SESSION_TTL   idle session expiry seconds (default 1800)
"""

import base64
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

V1_ACTIONS = {
    "open", "goto", "snapshot", "click", "fill", "type", "press",
    "select", "check", "look", "get_text", "wait", "back", "reload",
    "state", "cookies_clear",
}

# After a navigation inside one actions array, only these ref-free
# observations may follow (spec section 4). `wait` is allowed only in
# its exact-text forms here (text/text_gone), never time_ms, and never
# with a ref.
POST_NAV_ACTIONS = {"look", "get_text", "state", "wait"}

DEFAULT_TIMEOUT_MS = 15000
MAX_TEXT_CHARS = 20000

# JavaScript run once per frame. Returns the actionable elements with
# an approximate AX role, accessible name, and a unique XPath. The
# browser never holds real credential values (placeholders only), but
# values are still omitted below for password inputs — defense in
# depth for the read restrictions in spec section 11.
SNAPSHOT_JS = r"""
() => {
  const out = [];
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none';
  };
  const labelText = (el) => {
    let n = el.getAttribute('aria-label');
    if (n && n.trim()) return n.trim();
    const lb = el.getAttribute('aria-labelledby');
    if (lb) {
      n = lb.split(/\s+/).map(id => {
        const t = document.getElementById(id);
        return t ? t.textContent : '';
      }).join(' ').trim();
      if (n) return n;
    }
    if (el.id) {
      const lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (lab && lab.textContent.trim()) return lab.textContent.trim();
    }
    const wrap = el.closest('label');
    if (wrap) {
      const clone = wrap.cloneNode(true);
      clone.querySelectorAll('input,select,textarea,button').forEach(x => x.remove());
      if (clone.textContent.trim()) return clone.textContent.trim().slice(0, 120);
    }
    return '';
  };
  const nameOf = (el) => {
    const n = labelText(el);
    if (n) return n;
    const t = el.tagName;
    if (el.alt && el.alt.trim()) return el.alt.trim().slice(0, 120);
    if ((t === 'BUTTON' || (t === 'A' && el.hasAttribute('href')))
        && el.textContent.trim())
      return el.textContent.trim().slice(0, 120);
    if (el.placeholder) return el.placeholder.trim().slice(0, 120);
    if (el.title && el.title.trim()) return el.title.trim().slice(0, 120);
    return '';
  };
  const roleOf = (el) => {
    const r = el.getAttribute('role');
    if (r) return r.trim().toLowerCase().split(/\s+/)[0];
    const t = el.tagName;
    if (t === 'BUTTON') return 'button';
    if (t === 'A' && el.hasAttribute('href')) return 'link';
    if (t === 'INPUT') {
      const ty = (el.type || 'text').toLowerCase();
      if (ty === 'checkbox') return 'checkbox';
      if (ty === 'radio') return 'radio';
      if (['button', 'submit', 'reset', 'image'].includes(ty)) return 'button';
      if (['hidden', 'file'].includes(ty)) return null;
      return 'textbox';
    }
    if (t === 'TEXTAREA') return 'textbox';
    if (t === 'SELECT') return 'combobox';
    if (t === 'IMG' && el.alt) return 'img';
    return null;
  };
  const xpathOf = (el) => {
    if (el.id) return '//*[@id="' + el.id + '"]';
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.documentElement) {
      let i = 1, sib = cur.previousElementSibling;
      while (sib) { if (sib.tagName === cur.tagName) i++; sib = sib.previousElementSibling; }
      parts.unshift(cur.tagName.toLowerCase() + '[' + i + ']');
      cur = cur.parentElement;
    }
    return '/' + parts.join('/');
  };
  const els = document.querySelectorAll(
    'h1, h2, h3, h4, h5, h6, button, a[href], input, textarea, select, ' +
    'img[alt], [role="button"], [role="link"], [role="checkbox"], ' +
    '[role="radio"], [role="textbox"], [role="combobox"], ' +
    '[role="menuitem"]');
  els.forEach((el) => {
    const tag = el.tagName;
    if (/^H[1-6]$/.test(tag)) {
      // Headings are orientation, not targets: listed without a ref.
      if (!visible(el)) return;
      const name = el.textContent.trim().slice(0, 120);
      if (name) out.push({role: 'heading', name: name, tag: tag,
                          xpath: '', visible: true, enabled: true,
                          actionable: false});
      return;
    }
    const role = roleOf(el);
    if (!role) return;
    const ty = el.tagName === 'INPUT' ? (el.type || 'text').toLowerCase() : '';
    const item = {
      role: role, name: nameOf(el), tag: el.tagName, type: ty,
      xpath: xpathOf(el), visible: visible(el), enabled: !el.disabled,
      actionable: true,
    };
    if (role === 'checkbox' || role === 'radio') item.checked = !!el.checked;
    if (role === 'textbox' && ty !== 'password' && el.value !== undefined)
      item.value = String(el.value).slice(0, 200);
    out.push(item);
  });
  return out;
}
"""


class DriverError(Exception):
    pass


class Session:
    def __init__(self, sid, page, job):
        self.id = sid
        self.page = page
        self.job = job
        self.last_used = time.time()
        self.ref_scope = None
        self.refs = {}          # ref -> dict(frame, xpath, role, name, tag, type)
        self.sensitive_refs = set()  # refs bdrive typed this job:
                                       # unreadable (finding 75)


def _proxy_healthy(proxy_url, timeout=5):
    """Belt-and-braces gate: the proxy must answer before a session opens."""
    import http.client
    from urllib.parse import urlparse
    u = urlparse(proxy_url)
    host, port = u.hostname, u.port or 80
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", "/")
        resp = conn.getresponse()
        conn.close()
        return resp is not None  # any HTTP response (even 400) means it is up
    except OSError:
        return False


class Driver:
    def __init__(self):
        self.profile_dir = os.environ.get("BDRIVE_PROFILE_DIR",
                                          "/home/bdrive/profile")
        self.proxy = os.environ.get("BDRIVE_PROXY", "http://127.0.0.1:18080")
        self.headless = os.environ.get("BDRIVE_HEADLESS", "1") == "1"
        self.approvals_dir = os.environ.get("BDRIVE_APPROVALS_DIR",
                                            "/home/swapd/approvals/pending")
        self.shots_dir = os.environ.get("BDRIVE_SHOTS_DIR",
                                        "/home/bdrive/shots")
        self.session_ttl = int(os.environ.get("BDRIVE_SESSION_TTL", "1800"))
        # Driver enablement (review finding 74): the human acknowledges
        # once, on the confirmation page, that the persistent profile
        # is in use. confirmd writes this marker on approve. bdrive
        # never writes it itself. (This is NOT the grant channel's
        # first-use confirmation — that already covers first use of
        # credentials via refused swaps; this gate is about the
        # browser profile.)
        self.enablement_file = os.environ.get(
            "BDRIVE_ENABLEMENT_FILE",
            "/home/swapd/approvals/driver-enablement-confirmed")
        self._pw = None
        self._ctx = None
        self.sessions = {}

    # -- lifecycle ---------------------------------------------------
    def start(self):
        from playwright.sync_api import sync_playwright
        if self._pw is not None:
            return
        os.makedirs(self.profile_dir, exist_ok=True)
        os.makedirs(self.shots_dir, exist_ok=True)
        self._pw = sync_playwright().start()
        proxy = {"server": self.proxy} if self.proxy else None
        self._ctx = self._pw.chromium.launch_persistent_context(
            self.profile_dir,
            headless=self.headless,
            proxy=proxy,
            args=["--disable-dev-shm-usage"],
        )

    def stop(self):
        for sid in list(self.sessions):
            self.close_session(sid)
        if self._ctx is not None:
            self._ctx.close()
            self._ctx = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None

    # -- sessions ----------------------------------------------------
    def open_session(self, job=None, url=None):
        """Refuses to start a session if the proxy health check fails."""
        if self._ctx is None:
            self.start()
        if self.proxy and not _proxy_healthy(self.proxy):
            raise DriverError("proxy unhealthy: %s" % self.proxy)
        self._check_enablement(job)
        self._reap_expired()
        sid = "s-" + uuid.uuid4().hex[:12]
        page = self._ctx.new_page()
        if url:
            self._goto(page, url, DEFAULT_TIMEOUT_MS)
        sess = Session(sid, page, job)
        sess.last_used = time.time()
        self.sessions[sid] = sess
        obs = self._observe(sess)
        return sid, obs

    def close_session(self, sid):
        sess = self.sessions.pop(sid, None)
        if sess is None:
            raise DriverError("unknown session: %s" % sid)
        try:
            sess.page.close()
        except Exception:
            pass

    def _get_session(self, sid):
        self._reap_expired()
        sess = self.sessions.get(sid)
        if sess is None:
            raise DriverError("unknown or expired session: %s" % sid)
        sess.last_used = time.time()
        return sess

    def _reap_expired(self):
        now = time.time()
        for sid, sess in list(self.sessions.items()):
            if now - sess.last_used > self.session_ttl:
                try:
                    sess.page.close()
                except Exception:
                    pass
                del self.sessions[sid]

    # -- the act() entry point ---------------------------------------
    def act(self, sid, ref_scope, actions):
        sess = self._get_session(sid)
        if not isinstance(actions, list) or not actions:
            raise DriverError("actions must be a non-empty array")
        for a in actions:
            if not isinstance(a, dict) or a.get("action") not in V1_ACTIONS:
                raise DriverError("unknown action (not in the v1 set): %r"
                                  % (a.get("action") if isinstance(a, dict)
                                     else a))
        receipts = []
        navigated = False
        failed = False
        for spec in actions:
            name = spec["action"]
            if failed:
                receipts.append({"action": name, "status": "not_started",
                                 "actionability_reason": "aborted"})
                continue
            if navigated and not self._post_nav_ok(name, spec):
                receipts.append({"action": name, "status": "not_started",
                                 "actionability_reason": "post_navigation",
                                 "detail": "after goto/reload/back only "
                                           "ref-free look/get_text/state "
                                           "or exact-text wait may follow "
                                           "in the same array"})
                failed = True
                continue
            try:
                receipt = self._run_action(sess, ref_scope, spec)
            except _NotStarted as e:
                receipt = {"action": name, "status": "not_started",
                           "actionability_reason": e.reason,
                           "detail": e.detail}
                failed = True
            except _Unknown as e:
                receipt = {"action": name, "status": "unknown",
                           "detail": e.detail}
                failed = True
            receipts.append(receipt)
            if name in ("goto", "back", "reload"):
                navigated = True
        obs = self._observe(sess)
        return receipts, obs

    def _post_nav_ok(self, name, spec):
        if name not in POST_NAV_ACTIONS:
            return False
        if name == "wait":
            keys = [k for k in ("text", "text_gone", "time_ms")
                    if spec.get(k) is not None]
            return keys == ["text"] or keys == ["text_gone"]
        if name in ("look", "state"):
            return True
        if name == "get_text":
            return spec.get("ref") is None
        return False

    # -- action implementations --------------------------------------
    def _run_action(self, sess, ref_scope, spec):
        name = spec["action"]
        timeout = int(spec.get("timeout_ms") or DEFAULT_TIMEOUT_MS)
        page = sess.page
        if name == "goto":
            url = spec.get("url", "")
            self._goto(page, url, timeout)
            return {"action": name, "status": "completed", "url": page.url}
        if name == "back":
            try:
                page.go_back(timeout=timeout)
            except Exception as e:
                raise _NotStarted("timeout", "back: %s" % _short(e))
            return {"action": name, "status": "completed", "url": page.url}
        if name == "reload":
            try:
                page.reload(timeout=timeout)
            except Exception as e:
                raise _NotStarted("timeout", "reload: %s" % _short(e))
            return {"action": name, "status": "completed", "url": page.url}
        if name == "open":
            # Finding 78 nit: close the previous page — a new tab must
            # not leak the old one.
            old_page = sess.page
            new_page = self._ctx.new_page()
            try:
                url = spec.get("url")
                if url:
                    self._goto(new_page, url, timeout)
            except Exception:
                try:
                    new_page.close()
                except Exception:
                    pass
                raise
            sess.page = new_page
            sess.last_used = time.time()
            try:
                old_page.close()
            except Exception:
                pass
            return {"action": name, "status": "completed",
                    "url": new_page.url}
        if name == "snapshot":
            return {"action": name, "status": "completed"}
        if name == "state":
            return {"action": name, "status": "completed",
                    "url": page.url, "title": self._title(page),
                    "ready_state": self._ready(page)}
        if name == "cookies_clear":
            self._ctx.clear_cookies()
            return {"action": name, "status": "completed"}
        if name == "look":
            full = bool(spec.get("full_page"))
            png = page.screenshot(full_page=full, timeout=timeout)
            fname = "look-%s-%d.png" % (sess.id,
                                        int(time.time() * 1000))
            path = os.path.join(self.shots_dir, fname)
            with open(path, "wb") as f:
                f.write(png)
            return {"action": name, "status": "completed",
                    "path": path,
                    "png_base64": base64.b64encode(png).decode("ascii")}
        if name == "get_text":
            ref = spec.get("ref")
            if ref is None:
                try:
                    text = page.evaluate(
                        "() => document.documentElement.innerText || ''")
                except Exception as e:
                    raise _NotStarted("timeout", "get_text: %s" % _short(e))
                return {"action": name, "status": "completed",
                        "text": text[:MAX_TEXT_CHARS]}
            tgt = self._resolve(sess, ref_scope, ref)
            self._check_readable(sess, tgt, ref)
            loc = self._locator(sess, tgt)
            try:
                if tgt["tag"] in ("INPUT", "TEXTAREA"):
                    val = loc.input_value(timeout=timeout)
                elif tgt["tag"] == "SELECT":
                    val = loc.input_value(timeout=timeout)
                else:
                    val = loc.text_content(timeout=timeout) or ""
            except Exception as e:
                raise _NotStarted(*_pw_reason(e, "get_text"))
            return {"action": name, "status": "completed",
                    "text": val[:MAX_TEXT_CHARS]}
        if name == "wait":
            return self._do_wait(page, spec, timeout)
        # locator actions below: all need a current ref
        ref = spec.get("ref")
        tgt = self._resolve(sess, ref_scope, ref)
        loc = self._locator(sess, tgt)
        if name == "click":
            kind = spec.get("kind", "left")
            if kind not in ("left", "right", "double"):
                raise DriverError("click kind must be left/right/double")
            try:
                if kind == "double":
                    loc.dblclick(timeout=timeout)
                elif kind == "right":
                    loc.click(timeout=timeout, button="right")
                else:
                    loc.click(timeout=timeout)
            except Exception as e:
                raise _NotStarted(*_pw_reason(e, "click"))
            return {"action": name, "status": "completed", "ref": ref}
        if name == "fill":
            text = spec.get("text")
            if not isinstance(text, str):
                raise DriverError("fill needs a string text")
            try:
                loc.fill(text, timeout=timeout)
            except Exception as e:
                raise _NotStarted(*_pw_reason(e, "fill"))
            # Finding 75: EVERY value bdrive types is unreadable for
            # the rest of the job — no caller-supplied flag. The agent
            # already knows what it typed; read-back is refused.
            sess.sensitive_refs.add(ref)
            return {"action": name, "status": "completed", "ref": ref}
        if name == "type":
            text = spec.get("text")
            if not isinstance(text, str):
                raise DriverError("type needs a string text")
            try:
                loc.click(timeout=timeout)
                loc.press_sequentially(text, timeout=timeout)
            except Exception as e:
                raise _NotStarted(*_pw_reason(e, "type"))
            # Finding 75: as above — all typed values are unreadable.
            sess.sensitive_refs.add(ref)
            return {"action": name, "status": "completed", "ref": ref}
        if name == "press":
            key = spec.get("key")
            if not isinstance(key, str) or not key:
                raise DriverError("press needs a key name")
            try:
                if ref is not None:
                    loc.press(key, timeout=timeout)
                else:
                    page.keyboard.press(key)
            except Exception as e:
                raise _NotStarted(*_pw_reason(e, "press"))
            return {"action": name, "status": "completed"}
        if name == "select":
            if tgt["tag"] != "SELECT":
                raise _NotStarted("not_select",
                                  "select needs a native <select>, got %s"
                                  % tgt["tag"])
            value = spec.get("value")
            if not isinstance(value, str):
                raise DriverError("select needs a string value")
            try:
                chosen = loc.select_option(value=value, timeout=timeout)
            except Exception as e:
                raise _NotStarted(*_pw_reason(e, "select"))
            if not chosen:
                raise _NotStarted("no_such_option",
                                  "no option with value %r" % value)
            return {"action": name, "status": "completed", "ref": ref,
                    "selected": chosen}
        if name == "check":
            if tgt["tag"] != "INPUT" or tgt.get("type") not in (
                    "checkbox", "radio"):
                raise _NotStarted("not_checkable",
                                  "check needs a checkbox/radio")
            try:
                loc.check(timeout=timeout)
            except Exception as e:
                raise _NotStarted(*_pw_reason(e, "check"))
            return {"action": name, "status": "completed", "ref": ref}
        raise DriverError("unreachable")  # V1_ACTIONS gate above

    def _do_wait(self, page, spec, timeout):
        keys = [k for k in ("text", "text_gone", "time_ms")
                if spec.get(k) is not None]
        if len(keys) != 1:
            raise DriverError(
                "wait needs exactly one of text/text_gone/time_ms")
        key = keys[0]
        try:
            if key == "time_ms":
                page.wait_for_timeout(int(spec["time_ms"]))
            elif key == "text":
                page.get_by_text(spec["text"], exact=True).first.wait_for(
                    state="visible", timeout=timeout)
            else:
                page.get_by_text(spec["text_gone"],
                                 exact=True).first.wait_for(
                    state="detached", timeout=timeout)
        except Exception as e:
            raise _NotStarted(*_pw_reason(e, "wait"))
        return {"action": "wait", "status": "completed", "waited": key}

    # -- helpers ------------------------------------------------------
    def _goto(self, page, url, timeout):
        if not isinstance(url, str) or not url.lower().startswith(
                ("http://", "https://")):
            raise DriverError("goto: http/https URL required")
        try:
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        except Exception as e:
            msg = _short(e)
            if "net::" in msg or "ERR_" in msg:
                raise _Unknown("goto may have committed then failed: %s"
                               % msg)
            raise _NotStarted(*_pw_reason(e, "goto"))

    def _resolve(self, sess, ref_scope, ref):
        if not ref:
            raise _NotStarted("no_ref", "this action needs a ref")
        if ref_scope != sess.ref_scope:
            raise _NotStarted("stale_ref",
                              "ref_scope mismatch: take a fresh snapshot")
        tgt = sess.refs.get(ref)
        if tgt is None:
            raise _NotStarted("unknown_ref", "no such ref in this snapshot")
        return tgt

    def _locator(self, sess, tgt):
        frames = sess.page.frames
        if tgt["frame"] >= len(frames):
            raise _NotStarted("stale_ref", "frame is gone; re-snapshot")
        return frames[tgt["frame"]].locator("xpath=" + tgt["xpath"])

    def _check_readable(self, sess, tgt, ref):
        """Spec section 11: no read-back of password inputs, nor of any
        field bdrive typed in this job (finding 75 — every typed value
        is unreadable, no caller flag)."""
        if tgt["tag"] == "INPUT" and tgt.get("type") == "password":
            raise _NotStarted("read_restricted",
                              "ref %s is a password input" % ref)
        if ref in sess.sensitive_refs:
            raise _NotStarted("read_restricted",
                              "ref %s was typed by bdrive this job" % ref)

    def _title(self, page):
        try:
            return page.title()
        except Exception:
            return ""

    def _ready(self, page):
        try:
            return page.evaluate("() => document.readyState")
        except Exception:
            return "unknown"

    # -- observation ---------------------------------------------------
    def _observe(self, sess):
        sess.ref_scope = "rs-" + uuid.uuid4().hex[:12]
        sess.refs = {}
        try:
            lines = self._render_ax(sess)
        except Exception as e:
            lines = ["(snapshot failed: %s)" % _short(e)]
        return {
            "url": sess.page.url,
            "title": self._title(sess.page),
            "ready_state": self._ready(sess.page),
            "ref_scope": sess.ref_scope,
            "ax": "\n".join(lines),
        }

    def _render_ax(self, sess):
        lines = []
        counter = [0]
        frames = sess.page.frames
        for fi, frame in enumerate(frames):
            try:
                items = frame.evaluate(SNAPSHOT_JS)
            except Exception:
                continue
            if fi > 0:
                lines.append("-- frame %d (%s) --" % (fi, frame.url[:80]))
            for it in items:
                if not it.get("actionable", True):
                    bits = ["-", "[%s]" % it["role"]]
                    if it["name"]:
                        bits.append('"%s"' % it["name"][:60])
                    lines.append(" ".join(bits))
                    continue
                counter[0] += 1
                ref = "@e%d" % counter[0]
                sess.refs[ref] = {"frame": fi, "xpath": it["xpath"],
                                  "role": it["role"], "name": it["name"],
                                  "tag": it["tag"], "type": it.get("type")}
                bits = [ref, "[%s]" % it["role"]]
                if it["name"]:
                    bits.append('"%s"' % it["name"][:60])
                if it["tag"] == "INPUT" and it.get("type") == "password":
                    bits.append("(password)")
                if "checked" in it:
                    bits.append("(checked)" if it["checked"]
                                else "(unchecked)")
                if not it["visible"]:
                    bits.append("(hidden)")
                if not it["enabled"]:
                    bits.append("(disabled)")
                if it.get("value") and ref not in sess.sensitive_refs:
                    bits.append('value="%s"' % it["value"][:40])
                lines.append(" ".join(bits))
        return lines or ["(no actionable elements)"]

    # -- purchase approvals (spec section 7, findings 49/50) ------------
    @staticmethod
    def _approval_times(ttl_hours):
        """Finding 77: approval timestamps are ISO strings, matching
        what confirmd's _parse_expiry and the proxy reaper expect.
        Epoch floats never expire on the page — do not use them."""
        now = datetime.now(timezone.utc)
        return (now.isoformat(),
                (now + timedelta(hours=ttl_hours)).isoformat())

    def _write_approval(self, item, prefix):
        """Write a structured approval item to the pending dir, 0640."""
        os.makedirs(self.approvals_dir, exist_ok=True)
        path = os.path.join(self.approvals_dir, item["id"] + ".json")
        # 0640: readable by the approvals group (bdrive + swapd), not world.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(item, f, indent=2)
                f.write("\n")
        except BaseException:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        return item["id"]

    def _pending_enablement_id(self):
        """Id of an already-filed driver-enablement request, if one is
        pending."""
        try:
            names = os.listdir(self.approvals_dir)
        except OSError:
            return None
        for name in sorted(names):
            if not name.startswith("en-") or not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.approvals_dir, name)) as f:
                    it = json.load(f)
            except (OSError, ValueError):
                continue
            if it.get("kind") == "driver_enablement":
                return it.get("id")
        return None

    def _check_enablement(self, job):
        """Driver enablement (review finding 74): the persistent profile
        may hold the user's logged-in sessions, so the very first
        session needs a one-time human acknowledgement on the
        confirmation page. bdrive files a structured enablement request
        and refuses until the human approves it, which writes the
        marker file. bdrive never writes the marker itself. This is
        not the grant channel's first-use confirmation — that already
        covers first use of credentials via refused swaps.
        """
        if os.path.exists(self.enablement_file):
            return
        aid = self._pending_enablement_id()
        if aid is None:
            aid = self.file_enablement_approval(job)
        raise DriverError(
            "driver_enablement_required approval=%s "
            "(confirm on the grant channel page)" % aid)

    def file_enablement_approval(self, job):
        created, expires = self._approval_times(24)
        item = {
            "kind": "driver_enablement",
            "id": "en-" + uuid.uuid4().hex[:12],
            "job": job or "",
            "summary": "Driver enablement (job %s)" % (job or "?"),
            "created": created,
            "expires": expires,
        }
        return self._write_approval(item, "en-")

    def file_purchase_approval(self, approval):
        """Validate and file a structured purchase approval.

        Finding 49: the item carries structured fields, never free
        text as the binding. Finding 50: the requester is derived by
        confirmd from the FILE OWNER — this process must run as the
        bdrive user, so the owner is bdrive. obox cannot file.
        Finding 76: the caller names a live session; bdrive stamps the
        session's current URL and title into the item itself, so the
        confirmation page can show both the agent-claimed host and
        where the browser actually is.
        """
        if not isinstance(approval, dict):
            raise DriverError("approval must be an object")
        host = approval.get("host")
        amount = approval.get("amount")
        currency = approval.get("currency")
        job = approval.get("job")
        purpose = approval.get("purpose", "")
        session = approval.get("session")
        if not isinstance(host, str) or not host.strip():
            raise DriverError("approval.host must be a non-empty string")
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise DriverError("approval.amount must be a positive number")
        if not isinstance(currency, str) or len(currency.strip()) != 3:
            raise DriverError("approval.currency must be a 3-letter code")
        if not isinstance(job, str) or not job.strip():
            raise DriverError("approval.job must be a non-empty string")
        if not isinstance(purpose, str):
            raise DriverError("approval.purpose must be a string")
        if not isinstance(session, str) or not session:
            raise DriverError("approval.session must be a live session id")
        sess = self._get_session(session)  # raises if unknown/expired
        page_url = sess.page.url
        page_title = self._title(sess.page)
        aid = uuid.uuid4().hex
        created, expires = self._approval_times(1)
        item = {
            "kind": "purchase",
            "id": aid,
            "host": host.strip(),
            "amount": amount,
            "currency": currency.strip().upper(),
            "job": job.strip(),
            # Agent-supplied text, shown labeled as untrusted (finding 49).
            "purpose": purpose,
            "purpose_untrusted": True,
            # bdrive-stamped, not agent-claimed (finding 76).
            "session": session,
            "page_url": page_url,
            "page_title": page_title,
            "summary": "Purchase %.2f %s at %s (job %s)" % (
                amount, currency.strip().upper(), host.strip(),
                job.strip()),
            "created": created,
            "expires": expires,
        }
        return self._write_approval(item, "")


class _NotStarted(Exception):
    def __init__(self, reason, detail=""):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


class _Unknown(Exception):
    def __init__(self, detail=""):
        super().__init__(detail)
        self.detail = detail


def _short(e, n=160):
    return str(e).replace("\n", " ")[:n]


def _pw_reason(e, action):
    """Map a Playwright error to (actionability_reason, detail)."""
    from playwright.sync_api import TimeoutError as PwTimeout
    msg = _short(e)
    low = msg.lower()
    if isinstance(e, PwTimeout) or "timeout" in low:
        return ("timeout", "%s: %s" % (action, msg))
    if "not visible" in low or "hidden" in low:
        return ("not_visible", "%s: %s" % (action, msg))
    if "not enabled" in low or "disabled" in low:
        return ("not_enabled", "%s: %s" % (action, msg))
    if "not editable" in low or "readonly" in low or "not hittable" in low:
        return ("not_editable", "%s: %s" % (action, msg))
    if "strict mode" in low:
        return ("ambiguous", "%s: %s" % (action, msg))
    if "not found" in low or "no element" in low:
        return ("no_such_element", "%s: %s" % (action, msg))
    return ("error", "%s: %s" % (action, msg))
