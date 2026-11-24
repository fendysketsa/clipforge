# AI Office 3D diorama — 24 November 2026

Replaced the previous flat office floor with a procedural Three.js office: glass meeting/production/distribution rooms, social desks, lounge, coffee bar, detailed furniture and six articulated employees. Employees travel through doors and corridors, meet in pairs, gesture, and display speech bubbles. Server activity and illustrative office dialogue are labelled separately. Department filtering, operator pauses and incident evidence remain intact.

The full-width scene includes zoom, bubble visibility, day/night lighting and motion pause. Disabled departments remain at their desks. Motion stops for stale observations, hidden tabs, reduced-motion preferences and offscreen scenes. A browser without WebGL keeps the department list available. The scene redraws correctly on resize while motion is paused.

## Validation

- Production build and TypeScript checks passed.
- Existing AI Office tests and new routing/speech tests passed.
- Served production preview assets matched the deployment manifest; readiness passed.
- Browser fixture tests passed at 1440, 1280, 900, 390 and 320 CSS pixels in both themes, with no horizontal overflow or JavaScript errors. Pixel checks confirm a nonempty 3D scene after paused resizing.
- Movement, pause, employee selection, incident filtering, bubble visibility, zoom, lighting, disabled department, stale evidence, reduced motion and WebGL fallback passed.
- Screenshots use fixture data and do not claim current server activity.

## Activation

Deployment was attempted with the required command:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

It did not start: sudo requires a password, and direct Docker access is denied. Production container activation and live backend outcomes are not verified. Source and asset checks for this feature run within the existing Docker build/startup health verification; no separate activation script is required. No persisted settings, holds or remote upload records were edited.

Unrelated in-progress backend changes were left intact.
