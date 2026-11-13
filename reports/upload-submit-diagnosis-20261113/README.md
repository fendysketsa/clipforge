# Upload submission and queue diagnosis — 2026-11-13

The screenshot shows Lilang job `403b1cdef5dd4a669c5af49c40b207f3`.
Its saved audit is terminal DROP_SOURCE, but the running backend still marks
its YouTube button ready and the running frontend lacks the completed QC/status
repair. Served frontend release remains `7d77726baa053786d7d0325711951742b08dfad00cc9c326cf93e02b0ba00696`.
The source changes from earlier repairs are not evidence of their activation.

Safe POST probes from Chromium at `http://localhost:3000` reached the actual
backend through IPv4, localhost and the frontend proxy. Each used a nonexistent
diagnostic job and returned the expected HTTP 404, creating no upload. Thus the
historical fetch failure behind the screenshot was not reproduced; it must not
be confidently labelled DNS, CORS, internet loss or a server exception.

There is a real upload queue: YouTube replacement
`2f546df2dfe545559f12fdd4fd1fc2eb` was waiting for the shared browser turn while
TikTok `ab6ffbbd2fd248b09527f667f8d37ffb` prepared and submitted the same replacement
Long. TikTok then confirmed exact post ID `7707489276685995285`, Only you, and
YouTube advanced to running at 03:15:53 UTC. Queue, logs and process evidence are
saved alongside this report. No additional submission or retry was made.

A separate code defect was found and fixed: the dashboard's manual YouTube
submission omitted visibility. The backend could then use its Public default,
contradicting the Private review interface. Manual submissions and serialized
recovery now explicitly request `private`; TikTok remains `only_you`. Existing
queued records and cron publication policy were not changed. A regression test
covers both original and recovered admission payloads.

Validation: 38 frontend test cases, TypeScript, the production build and
source/asset manifest verification passed. Python/cron and QC repairs remain
as previously tested. The latest build/release and source hashes are recorded
in `verification.json`. No YouTube remote success is claimed before its record
has a confirmed remote video ID.

## Activation

Normal deployment is blocked for this session by Docker permissions and sudo's
administrator password requirement. The user has been asked to run the standard
frontend-only update, which keeps backend rendering and uploads running:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate --no-deps frontend
```

Then verify `/deployment.json` against the latest release and refresh the page.
The UI will show Lilang's exact QC hold instead of offering another submission,
and show replacement progress. The separate backend/niche patches still require
the full normal update after active work finishes. Do not resubmit a terminally
rejected source, erase uncertain remote checkpoints or replay an ordinary POST.

## Remote progress

YouTube assigned `2PRl4z8aSx4`, attached the 1280x720 thumbnail, persisted the
Gaming playlist and reached Checks. The saved request schedules 17 November
2026, 20:30 WIB; that existing request was not changed. Upload confirmation
remains pending while Studio Checks runs. See `youtube-progress.json`.
