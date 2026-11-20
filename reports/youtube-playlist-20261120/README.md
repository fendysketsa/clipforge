# YouTube playlist repair — 20 November 2026 (Asia/Jakarta)

## Findings

The live upload API contained nine completed, upload-confirmed records with an
unconfirmed playlist and a recorded attempt to create a missing playlist. Four
recent examples failed because Studio disabled **Playlist baru** while the search
field contained text. Recovery subsequently confirmed the remote upload without
checking playlist membership. These are local/API observations; playlist
membership on the remote videos has not yet been independently verified.

The source already contains the search-clearing fix, but the live failure logs
show that the runtime used the earlier click sequence. Creation was also enabled
only for cron uploads. A separate source bug waited up to 5,000 seconds rather
than five seconds for the creation submit button and could check the wrapper
instead of the native disabled button.

## Implementation

- Both manual and cron uploads can create a missing destination playlist.
- Reuse existing playlists; unavailable search results do not authorize creation.
- Clear search before opening the creation menu. Read both contenteditable and
  native textarea titles, inspect the actual submit button and its wrapper, and
  bound readiness to five seconds. Do not resubmit an uncertain creation.
- Recovery carries the destination playlist, selects it before finalizing a
  resumed draft, and saves playlist changes on the exact existing video ID.
- Require a successful metadata response and verify the checked playlist after a
  fresh editor load before emitting `SAVED_PLAYLIST_CONFIRMED`.
- Recovery cannot complete without that saved-playlist confirmation. Restart
  loading queues previously completed records with this known creation failure
  for verification of their existing remote IDs, even when local media is gone.
- Existing settings, metadata, publication holds and upload identity remain in
  the persisted records. The existing recovery workflow handles visibility and
  scheduling; this repair does not assign new publication settings.
- Existing Docker source manifests cover the changed Python files. No additional
  dependency, activation script, or deployment command is required.

## Affected existing IDs

| Upload record | Remote video ID | Destination playlist |
| --- | --- | --- |
| `471a73739a9c4daf99bda76781b5ebdb` | `IBSgcUTKQsM` | Keluarga dan Rumah Tangga |
| `aa1618d3ae3c44dca8c12e925af4c0ac` | `_CejE0u0Nhc` | Keluarga dan Rumah Tangga |
| `45bad16613b04727b3420862403c5c59` | `vZY655l5HSU` | Keluarga dan Rumah Tangga |
| `ca894e248243459e9f0c19757554943f` | `ON5RPHp2mFY` | Keluarga dan Rumah Tangga |
| `ac5be3d2802d467d97dd795804e67369` | `K8Kt3qKZ_Xw` | Keluarga dan Rumah Tangga |
| `d5841c84d1f54b5eb0c20c90860dc61e` | `le-kao5zNxY` | Keluarga dan Rumah Tangga |
| `40c6f08fa17f45168d2403754acc9e5b` | `IcM64SoGKIM` | Animasi |
| `e44afe0122534e299301e4eef077bcd5` | `Okv2OMQjE5U` | Animasi |
| `54b15f4a9b3249748e577892875c2eb9` | `MyUKNUt0v90` | Sejarah, Geografi & Budaya Nusantara |

## Verification and activation

426 focused backend tests passed, covering routing, command arguments, metadata,
restart migration, recovery confirmation, exact remote identity, finalization,
browser compatibility and upload spacing. All 15 Chromium integration tests
passed against simulated Studio pages, additionally exercising search/create/select,
disabled controls, uncertain submission, save rejection and membership after
reload. Total: 441 passing tests. Python compilation and `git diff --check`
passed. The host test environment used temporary dependencies under `/tmp`;
production dependencies were not modified.

The standard deployment was attempted:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

It stopped before building because sudo requires a password. The existing
`/api/health` endpoint responded `{"status":"ok"}`, but this does not confirm that
the repaired source is active. Container access also requires privileges.
Runtime activation and the nine remote playlist repairs remain unverified until
the standard deployment succeeds and the resulting recovery jobs are checked.
