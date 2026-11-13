# Upload connection repair — 2026-11-13

The screenshot's red toast was thrown after both the original browser request
and its serialized recovery request failed to deliver a usable response. Its
historical network exception is not captured, so a precise historical cause
such as DNS, IPv6, CORS or a server exception cannot be claimed.

Live checks found:

- Direct backend health on localhost:8010 and 127.0.0.1:8010 is HTTP 200.
- POST preflight and a nonexistent-job probe return the correct CORS headers
  and HTTP 404 on both direct addresses.
- The frontend's same-origin /api/health and serialized upload proxy return
  HTTP 502: Backend API is not reachable: All promises were rejected.
- The frontend container's gateway is already 172.18.0.1, which is in its
  configured candidates; simply adding the same gateway would not fix this.
- Chromium from http://localhost:3000 confirmed both direct addresses work
  while the same-origin proxy returns 502. The proxy's network fault remains
  distinct from the historical browser exception; it was not silently called
  fixed or used as the sole explanation for the screenshot.

The exact clip was recovered through the backend's serialized admission check,
with visibility Private. It created a single canonical YouTube upload record
7ecaf7f3f07f489b80cd3e1c86afb825. Its completed state, exact video URL, confirmed
transfer and News playlist are in youtube-confirmed.json:
https://www.youtube.com/watch?v=H6pasroRqpE
TikTok had already completed for that clip; it was not resubmitted.

The frontend fix tries explicit aliases of the same configured backend and
the same-origin proxy for reads/status reconciliation. Failed reads select a
healthy address before the sole original submission. When a submission result
is uncertain, alternate addresses receive only serialized /reconcile calls;
the ordinary POST is never replayed. Existing completed records clear stale
browser guards. Requests have bounded timeouts, failed recovery preserves its
reservation, and the UI names the affected platform without the confusing
"koneksi pemulihan" wording. Binary file transfer remains unchanged.

Validation: 20 submission tests and 3 queue-display tests passed; TypeScript and
a production Next build passed. A real Chromium test deliberately aborted the
primary localhost submission/reconciliation and then used the IPv4 route to
return the already-confirmed video ID. It created no new upload and did not
replay the ordinary POST. Evidence: browser-fallback-verification.json.

Live recovery of the user's clip IS confirmed. The new frontend code is NOT
confirmed active: Docker access is denied and the frontend-only activation
attempt returned "sudo: a password is required". The local build is in
frontend/.next-upload-connection. To activate without restarting backend jobs:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate --no-deps frontend
```

After activation, refresh the browser and verify the served build/new transport
rather than treating the local build as runtime evidence.
