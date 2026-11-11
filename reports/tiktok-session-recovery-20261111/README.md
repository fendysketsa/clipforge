# Verified final outcome

Long upload `6a0c263d509749d3ab61e02f67cace3a` is now completed with persisted upload confirmation and remote ID `7706901093179067668`:

https://www.tiktok.com/@titikbalikislami/video/7706901093179067668

An independent authenticated Studio audit matched the full caption, exact ID and Only-me/Only-you privacy. TikTok currently shows Content under review; upload acceptance is confirmed, platform review remains pending. The final recovery reused the original hash-matched draft, performed no new file transfer, and kept retry count 3/3. All fixes are active in source-matching backend/bot release recorded in verification.json, with a healthy scheduler. The history below is retained as diagnostic evidence; its earlier pending/failed activation and upload statements are superseded by this outcome.

# TikTok live upload and privacy repair, 11 November 2026

The first requested rebuild is verified active: backend and bot release `fe645aa46cd4b2c3413e0e58c5661094bc983c675faa574b92e7ac15d24dc949`; healthy scheduler; frontend build `MKj-MyVVIKvLk7EnWNSl-`. The account @titikbalikislami is valid. The session-check isolation, external-browser preference, false-logout recovery and frontend toast repairs were activated.

The explicit retry reused Long upload `6a0c263d509749d3ab61e02f67cace3a`, job `2a08735031e3425faa863fd198665238`, original hash, caption and Only-you visibility. It did not create another upload ID. Retry 2 then reached the file and caption stages but failed privacy readback. The existing bounded policy reserved retry 3 at 19:14 WIB. That retry transferred the same file and selected Only you, yet again failed readback. Post intent and API acceptance are both false, no remote URL exists, and the retry budget remains 3/3.

Live DOM snapshots prove the second bug: the privacy button wraps its label inside `div.Select__triggerInner > div`. Playwright's old `button:text-matches(...)` selector finds zero matches for that real markup because text-matches selects the smallest matching node. Current fixtures had direct button text and did not expose this shape. The replacement matches both direct and descendant labels. A real Chromium reproduction returned old=0/new=1 for nested labels and old=1/new=1 for direct labels. The latest snapshots show the exact file identity and selected Only you; `privacy-live.png` captures the form before selection.

The upload tab was also activated during retry 3 and remained visible/focused. That did not resolve the readback bug, so focus alone is not the repair.

Latest source changes (not yet active):

- Match wrapped and direct privacy labels for initial selection and mandatory readback.
- Recognize the exact current interrupted-upload prompt with a plain Continue button, and wait for the hash-matched draft to finish hydration.
- Add explicit `POST /api/tiktok/uploads/{upload_id}/resume-draft`: one draft-only repair of a pre-Post Only-you privacy failure. It preserves the original ID, retry count, digest, caption, target account, rights/review gates and duplicate protections. The worker is prohibited from transferring a new file or discarding the existing draft. If the exact draft cannot be found, it stops before transfer/Post. A reserved repair cannot schedule another repair or automatic retry.

Validation of the latest changes: 251 backend tests and 32 Chromium browser tests passed. See `privacy-repair-tests.xml` and `privacy-repair-browser.xml`. Earlier frontend typecheck and production build remain successful; no additional frontend source change was needed for the second repair.

The source release expected after the next rebuild is recorded in `verification.json`. Docker access is denied and sudo requires a desktop password, so this second repair awaits activation:

```sh
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

After activation, verify source/release and health, then call the explicit resume-draft endpoint for this exact upload. Do not reset the retry counter or create another upload record. Completion requires persisted `upload_confirmed=true`, exact remote URL and verified Only-you visibility.


## Follow-up after the second rebuild

Release `51b0fe866bb0f654255d69b4ab6ea5588c285c97f20803946533f30fc67223cd` was verified active with healthy backend, bot and scheduler. The draft-only repair retained count 3/3 and performed no new transfer or Post. It stopped because its direct-text Continue selector missed the actual wrapped button. A separate audit confirmed the interrupted-upload banner was still present, so that miss did not prove the draft was absent.

The Continue selector now supports direct and nested text. One explicit `repair_banner=true` continuation is allowed only for that exact pre-draft error, with no Post evidence and with all original identity, digest, preflight and duplicate guards. A durable marker prevents a second banner correction. It preserves the original retry count and the prohibition on file transfer.

Current validation: 256 backend tests plus 33 Chromium tests passed. More importantly, a live check of the real draft returned old Continue selector count 0 and corrected selector count 1, restored `clipforge-2233599bd112696999d618e8063979c05e630b2feaa69aa9b6d498efd43b45f1.mp4`, verified that original hash identity, and read back Only you. It did not transfer a file or press Post. See `live-draft-selector-proof.json`.

This latest Continue correction still requires rebuild; expected source release is in `verification.json`. After activation, use the same resume-draft endpoint with `?repair_banner=true`, once. Do not reset the retry count or mint another upload ID. No successful remote post is claimed until both its exact URL and persisted upload confirmation exist.


## Follow-up after Continue activation

Release `3cb42e07d9e04f15c5440c763d1b30511e561018c513f55807e7674038614633` was verified active. The explicit banner repair reached duplicate preflight and stopped before entering the draft because another post shared the template opening. A loaded Studio audit proved the apparent match was Nadia Omara, source `Jr2AVxsP3Vk`, post `7706894101328809217`, duration 00:41. The requested Long cites BANGJBLOX source `B3anNkNUqrg`; their full captions differ. The existing 00:47 Short from BANGJBLOX has a different opening and is also distinct from this Long.

Latest source allows the shared opening only when every counted matching row belongs to the target account and ends in a different explicit YouTube source credit. Missing/truncated credit, same source ID, unknown owner, incomplete rows or an unmatched count still hold. Exact existing-post identity and privacy checks remain authoritative. The initial Posts 0 placeholder is no longer trusted before its readiness window elapses.

A one-time explicit `repair_caption_collision=true` continuation is limited to that exact pre-Post error and the existing draft-only record. It retains all media, review, rights, account, visibility, duplicate and submission guards. Another durable marker prevents replay; retry count remains 3/3 and new file transfer stays prohibited.

Validation: 274 backend tests and 34 Chromium tests passed. `live-source-collision-proof.json` proves the two source IDs on the actual Studio page. `full-pre-post-proof.json` records a complete live run from account validation through duplicate preflight, hash-matched draft restore, caption readback, Only-you verification, processing readiness and native Post activation readiness. That run deliberately raised a stop immediately before submission intent and real activation. It transferred no file and did not press Post.

The latest source release is in `verification.json`; this comparison correction awaits the requested desktop rebuild. After activation call the same resume-draft endpoint with `?repair_caption_collision=true`. No remote success has yet been confirmed.
