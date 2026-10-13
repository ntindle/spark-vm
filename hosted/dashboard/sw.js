/* Push service worker — reference implementation for the plane (#968 / GP2).

The plane serves this file at /sw.js (same origin, scope "/") so the
dashboard's register flow (PushManager.subscribe, see dashboard.html)
has a service worker to bind the push subscription to. It is shipped
here so the plane's serving is byte-pinned to a reviewed file; the
worker never sees credentials and holds no keys — it only renders
the "go look" payloads the plane already signed and sent.

Payload discipline (D4, push_payload.py): the decrypted JSON is
exactly {aid, ttl_s, summary}. Anything else is a protocol violation
and gets a generic page, never a crash. The notification never
includes the box's raw text beyond the scrubbed summary the plane
built.
*/
"use strict";

self.addEventListener("push", function (event) {
  var title = "spark-vm";
  var summary = "An approval needs your tap";
  try {
    var data = event.data ? event.data.json() : null;
    if (data && typeof data.summary === "string" && data.summary) {
      summary = data.summary.slice(0, 200);
    }
  } catch (e) {
    /* a malformed payload still pages — the owner taps to see */
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body: summary,
      requireInteraction: true, // pages only; the owner dismisses by tapping
      data: { url: "/" }
    })
  );
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  event.waitUntil(self.clients.openWindow(event.notification.data.url || "/"));
});
