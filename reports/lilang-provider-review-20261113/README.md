# Lilang provider-review preparation — 2026-11-13

The requested Lilang upload remains blocked by the saved explicit content-review
refusal. Its source ID is `403b1cdef5dd4a669c5af49c40b207f3`. The existing media and
review are preserved; no upload, repeated inference, alternate-provider review
or QC approval change was made during this work.

The old review timestamp is 13 November 2026, 07:30:18 WIB. That record retained
neither the original response nor a request/generation ID. The current model is
recorded in `diagnostic-summary.json`; it is deliberately not presented as proof
of the model used for the original request.

## Completed work

- Prepared `support-request-draft.txt` for the provider's official review/support
  route. It contains an incident time, current model, saved error summary and
  local artifact checksum. It includes no video, prompt, account identifier,
  API key or attachment. It has not been submitted.
- Corrected future error recording in `long_video_qc.py`: terminal refusals now
  retain the HTTP status, review stage, redacted response excerpt and a valid
  provider request ID when supplied. Temporary HTTP errors use the same
  diagnostics. The original refusal remains terminal and cannot become a pass
  through this change.
- 59 QC/operator tests passed, including preservation of a terminal refusal,
  request-ID capture, secret redaction and temporary-error holds.

OpenRouter documents request-level logs and a support-ticket route:

- https://openrouter.ai/docs/guides/features/logs
- https://openrouter.ai/support/new

The direct public support-page HTTP fetch returned 403; no alternate headers,
identity or access-control workaround was attempted. The already-accessible
official documentation was used to prepare the unsent report. No connected
OpenRouter page was found on the available browser endpoints.

## Remaining external step

Submitting a report sends a message to an outside service and needs explicit
user authorization plus legitimate account access. The draft is ready for
review. The new logging code is source/test verified, not runtime activated.
The exact Lilang upload is incomplete while the original refusal remains
unresolved; the separate already-confirmed replacement is not this video.

## Submission confirmed

The user authorized proceeding after the explicit external-submission question.
The prepared diagnostic message was sent through the connected Gmail account to
`support@openrouter.ai` on 2026-11-13 13:34:38 WIB. A separate Gmail read
confirmed the recipient, subject and SENT label for message `1a1d39d859db05b6`.
No attachment or API key was included. See `sent-receipt.json`.

This verifies mail submission only. It does not verify delivery/read by provider
support, receipt of an appeal decision, or upload of Lilang. The content hold and
local artifact remain preserved while the provider response is unresolved.

During initial local investigation a configuration search displayed the API key
in the tool log. The user was informed, subsequent reads were restricted, and
the support body was checked to exclude that credential before it was sent.
