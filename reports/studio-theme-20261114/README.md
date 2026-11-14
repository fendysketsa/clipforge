# Compact studio layout and themes — 14 November 2026

The studio now uses a shared semantic palette for dark and light themes, including forms, source warnings, QC details, queue states, platform connections, archive controls, and notifications. The sun/moon control is available in the header of both the production workspace and source archive.

Without a stored preference, the theme follows the device. An explicit selection is stored separately under `clipforge.studio.theme`, survives reload/navigation, and synchronizes across tabs. The head bootstrap applies it before React renders. Switching remains usable when browser storage is unavailable.

Layout changes:

- Results: three explicit columns from 1280px, two on narrower desktop widths, and one below 880px. Preview height is 240px on desktop. Copy-title is a compact icon; full titles remain accessible through the title/copy action. Reviews, QC holds, and upload recovery controls remain available.
- History: four desktop columns with shorter previews, smaller card padding, and visible standalone selection targets of at least 24px.
- Creation: smaller summary tiles and source/status cards. Edit controls expand when needed.
- Automation and connections: smaller padding, shorter empty states, and grouped actions.
- Source archive: consistent theme colors and compact summaries/rows.
- Hover, focus, and short reveal transitions add feedback; reduced-motion preferences are respected.

Validation:

- Production Next.js build and type checking passed.
- All seven frontend test files passed, including theme precedence and blocked-storage bootstrap tests.
- 17 deployment/readiness tests passed. Standard Docker builds now require the theme control, light palette, and three-column result grid in the built/served assets.
- 48 screenshots cover six pages, both themes, and widths 1440, 1280, 390, and 320px. No horizontal overflow or browser runtime errors were found.
- 33 interaction assertions passed: grid breakpoints, keyboard, reload, full archive navigation, cross-tab changes, form persistence, early theme initialization, blocked storage, and review holds.
- Additional upload-state screenshots cover failed, queued, running, completed, and uncertain Post outcomes in both themes. These six checks found no overflow or text-contrast issues. Expanded editor, generator, and QC controls were also checked. Contrast checks are scoped to rendered fixture states, not a certification of every possible future content combination.

The screenshots use controlled example records and a local test video. Browser checks block production mutations.

Activation is not complete: final preview build `YjssnuBQntdzWzCK7kk_1` is verified on port 3038, while production returned build `EZD5pjFRxpF3un-VTYjVL`. Backend health returned `ok`. Noninteractive sudo requires a password.

Use the existing standard deployment command; no extra setup or activation command is needed:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Verify the running services and served build after deployment before treating the final release as active.
