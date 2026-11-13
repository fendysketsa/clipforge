# Frontend API proxy repair — 2026-11-13

The live frontend still returns HTTP 502 from /api/health while the browser can
reach http://localhost:8010/api/health and http://127.0.0.1:8010/api/health.
The configured container gateways already include 172.18.0.1 and 172.17.0.1;
adding the same candidate or merely rebuilding the old route is insufficient.

The API route now separates discovery from delivery. If every internal health
probe fails, it returns a noncached HTTP 307 to the configured PUBLIC API URL.
This happens before reading or forwarding the caller's body. The browser can
reach that API directly, and 307 preserves method, JSON body and query string.
Invalid public URLs, embedded credentials and same-origin redirect loops are
refused. If forwarding has already started and its response is lost, the proxy
returns an explicit unknown-outcome response and NEVER redirects/replays that
mutation. Upload recovery continues through serialized backend admission.

Validation: 5 proxy tests, 20 submission tests and 3 queue-display tests passed.
TypeScript, a production Next build, source/asset build-manifest verification,
and whitespace checks passed. Native Chromium simulated the observed internal
health failure and followed the new response to the actual backend. GET health
became HTTP 200. A POST to a nonexistent probe job preserved its full body and
returned the real backend HTTP 404, with exactly one POST reaching the backend.
No upload was created. Evidence is in browser-verification.json.

This is source/build/browser verification, NOT activation. The production
frontend at the last check still served an earlier build and returned 502.
The session cannot access Docker and sudo requires an administrator password.
No alternative privilege mechanism or Docker permission change was attempted.
A host administrator must execute the normal frontend-only deployment:

```bash
cd /www/wwwroot/clipper/clipforge
sudo docker-compose --env-file .env up -d --build --force-recreate --no-deps frontend
```

This leaves the currently active backend render running. Its Long QC display
fix remains a separate backend activation after current work finishes. The
Lilang Long's terminal QC refusal is preserved; this proxy repair does not
convert it to PASS_UPLOAD, retry its provider, publish it, or remove its file.

After activation, verify the served deployment release and browser GET
/api/health. Do not claim the problem is fixed in production merely because
this local build passed. The local build ID and current source hashes are
recorded in verification.json.

## Live activation verified on 2026-11-13

The subsequent read-only production check returned HTTP 200 from frontend
`/api/health`. Served deployment release `7d77726baa053786d7d0325711951742b08dfad00cc9c326cf93e02b0ba00696`
matches this proxy repair. The earlier activation-blocked paragraph above is
historical. Evidence: `../cron-long-continuation-20261113/runtime.json`.
The newer cron progress/checkpoint/probe patch remains a separate pending release.
