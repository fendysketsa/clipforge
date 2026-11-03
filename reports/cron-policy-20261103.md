# Cron YouTube policy — 3 November 2026

The final backend image is deployed and cron is enabled with an active new campaign.

- At most 7 public releases per Jakarta date, shared by Shorts and long videos.
- Slots: 07:00, 09:15, 11:30, 13:45, 16:00, 18:15, 20:30 WIB.
- Minimum gap: 2 hours 15 minutes, including across date boundaries.
- At most 11 future scheduled videos and 5 new cron Private reserves.
- Legacy/manual Private videos remain unchanged and do not belong to the new reserve.
- Private reserves are promoted using the same remote video ID when scheduled capacity opens.
- Full buffers pause discovery until the next release; quality and claim gates remain enforced.
- Studio time-of-day uses seconds since midnight. Calendar/time fields use native input events.
- Schedule persistence waits for the metadata-write server response, then verifies the saved model.
- Already-published videos are saved Private before applying their approved future schedule.

## Verification

- 327 focused upload/policy tests and 78 cron/budget tests passed (405 total).
- All 11 approved schedules were independently checked in fresh Studio tabs.
- All 11 application records are completed, confirmed, and match their approved timestamps.
- Video IDs are unchanged; no video file was uploaded again during rescheduling.
- 7 existing videos are scheduled on 4 November; 4 on 5 November.
- Runtime configuration and active campaign are recorded in cron-policy-runtime-20261103.json.
- Independent Studio evidence is recorded in cron-schedule-verification-20261103.json.
