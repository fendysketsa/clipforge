# Long production repair, 6 November 2026

Status: implementation validated; runtime activation pending. The operator replied "belum" to the activation instruction. No Long render has started yet.

The live scheduled request disabled paired Long production, the daily Long upload quota was zero, and the Short publication buffer was full. The scheduler waited before reaching paired Long production. Recent campaigns contained no Long job IDs.

The new review lane renders one approximately five-minute Long per Jakarta calendar day independently of the Short publication buffer and Long upload quota. It reuses completed scheduled Short candidates and the persisted operator rights attestation through the existing paired Long builder. News sources are excluded. It does not enable automatic publication or change Short quotas.

A durable checkpoint tracks attempts, completed outputs, source run and paired Short IDs. Three attempts per day cap repeated failures. An unresolved reservation holds production for inspection. Short snapshots preserve authoritative timestamps through verified-upload cleanup. Review outputs are excluded from the generic upload/repair sweeper and automated clip eligibility. Relevance against the original Short is recorded after rendering.

Validation: 110 relevant tests passed, including 16 dedicated Long lane tests and existing paired production, scheduler, upload sweeper, recovery, and deployment checks. Shell syntax, Python compilation, and diff whitespace checks passed. Live read-only preflight confirmed eligible Short `7d07d87619814350a4a9ba1e2d2c5900`, its persisted source metadata and rights attestation, and no active clip or campaign.

Activation:

```sh
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-ryuundy-long.sh
```

The script deploys verified module hashes after active work drains, restores the existing cron switch, persists the daily review production policy, and requests the first Long. Its checkpoint goes to `reports/ryuundy-long-activation.json`. A queued result is not evidence of render completion; verify the actual final MP4, duration, framing, captions, source relevance, and QC before publication.
