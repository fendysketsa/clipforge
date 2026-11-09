# Shorts curiosity covers, 7 November 2026

The user authorized stronger attention-grabbing Shorts thumbnails. The cinematic-thumbnail-ideator skill guided three distinct concepts, grounded in actual footage and speech.

The previous primary Short cover was a fixed 0.78-second frame. The new system samples seven moments, locates the actual picture within black letterboxing, ranks clarity and real face size, and builds three 1080x1920 layouts. Headlines use 3-6 word verbatim excerpts, prefer complete tension/contradiction, and retain negation and allegation qualifiers. Typography is fitted to two lines in the central safe area. The chosen design becomes the existing `_thumb.jpg` path, alongside variants and an evidence manifest. No expression, person, event, screenshot or outcome is generated. Design scores are editorial heuristics, not CTR predictions.

The renderer can sample the original source inside the selected timestamp range before burned overlays. A pre-upload hook is also available. These backend changes need the normal guarded activation; the host worker provides immediate operation for completed Shorts whose YouTube thumbnail transfer has not started. Existing transferred/confirmed thumbnails are skipped. A second transfer-state check occurs after rendering and before atomic asset replacement. MP4 bytes are unchanged.

`clipforge-shorts-thumbnail-operator.service` is enabled through the user's systemd manager. At activation there were no eligible untransferred Shorts; its live state is waiting for the next one. It performs local processing only and does not export thumbnail media to AI services.

The reviewable preview uses preserved real frames and the authoritative Short snapshot for Nisa. Winner A reads **BUKAN NISA YANG MERUSAK KELUARGA**, supported by the exact line “Bukan Nisa yang merusak keluarga ini.” See `reports/shorts-thumbnail-preview/Nisa_thumbnail_ideas.json` and `comparison.jpg`. The preview is a design artifact; it has not been attached to the already-uploaded video.

Validation: 483 relevant tests passed, covering actual media/cover generation, unchanged MP4 hashes, negation/attribution preservation, safe-area dimensions, staging cancellation, caption styles, deployment idle guards and YouTube upload behavior. Python compilation, shell syntax and diff whitespace checks passed.

For permanent backend integration after active work drains:

```sh
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-short-thumbnails.sh
```

Actual custom-cover selection remains platform-dependent. The manifest retains that limitation; the existing embedded-cover fallback is preserved.
