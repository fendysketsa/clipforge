# Handing over a finished film

Path: both
Owner: preview sizing, serving the full file, and proving what the link serves

Two artefacts leave every build: a **chat-sized preview** and the **full delivery file** on disk. A third one
appears when the person wants the full quality on a phone — a **served link** — and that link has to be
verified before it is sent, or the delivery is a rumour.

---

## 1. Two files, and the original is never re-compressed

| artefact | rule |
|---|---|
| delivery file | the graded encode. Full resolution, real bitrate, the only copy that is "the film" |
| chat preview | a **new, separate encode** at 576–720 px on the short side, CRF 33–35, audio 64–96 kbps |

- **Never shrink the delivery file to fit a messenger.** Re-encoding the master for chat throws away the
  quality the whole build was for; make a preview and keep both.
- **Stay at or under ~13 MB for a chat preview.** A 16.6 MB preview was refused by the gateway and cost a
  second full encode.
- **Odd dimensions kill an x264 encode outright** — `scale=720:405` fails with `height not divisible by 2` and
  writes nothing. Use `scale=720:-2` and the even height is computed for you.
- **`-movflags +faststart` keeps the output near zero bytes until the encode finishes.** A 0 MB file is not a
  stalled job; check the process, not the size.
- **Never judge a file that is still being written.** A video whose `ffprobe` says `moov atom not found` is a
  partial write: the index is at the end. Wait until the size stops changing and `ffprobe` returns a duration
  before you run a single gate — otherwise you report a defect that no longer exists.

## 2. Serving the full file

```sh
python scripts/serve_range.py "<dir>" 8899 127.0.0.1          # Range-capable static server
cloudflared tunnel --url http://127.0.0.1:8899 --no-autoupdate > tunnel.log 2>&1
grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" tunnel.log | head -1
```

**`python -m http.server` is the wrong server for this.** It answers a `Range` request with `200` and the whole
file, so the player cannot seek and a phone will not stream; the person gets a download link that stalls. Use
`scripts/serve_range.py`, which returns `206` with `Content-Range`.

### 2b. Send the page, not the bare file

A URL that ends in `.mp4` opens a player and offers **no download control** — on a phone the person is left
looking at a video that plays and cannot be saved, and the next message is "where is the download button".
Serve a small `index.html` beside the film and hand over the **root** URL:

```html
<video src="film.mp4" controls playsinline preload="metadata"></video>
<a href="film.mp4?dl=1">Download video (73,8 MB)</a>
```

- **The `download` attribute alone does not work.** Browsers ignore it for cross-origin media and iOS Safari
  ignores it broadly, so the save has to be requested by the **server**: `?dl=1` answers with
  `Content-Disposition: attachment; filename="film.mp4"`. `scripts/serve_range.py` implements both the page
  root and that flag; keep the flag on a Range-capable handler so the inline player still gets `206`.
- **Put the size in the button label** and keep a second plain link for anyone whose browser misbehaves.
- **Write the iOS fallback into the page**, not into the chat: *tap the button, choose Download Linked File —
  the file lands in Files › Downloads*. It is the difference between a delivery and a support thread.
- **Verify the page, not only the file.** `curl -s "$U/" | grep -c 'download'` proves the button is in the
  response, and opening the page and reading the anchors proves the browser agrees. Three files were called
  delivered before anyone checked that the hand-over page existed at all.

## 3. Verify the link before sending it

Three checks, all cheap, all on the public URL rather than on localhost:

```sh
U=https://<tunnel-host>
curl -sI -H "Range: bytes=0-1023" "$U/film.mp4" | head -3    # expect HTTP/1.1 206 Partial Content
curl -s -r 0-15 "$U/film.mp4" | xxd | head -1              # expect a box header containing 'ftyp'
curl -s -r 40000000-40001023 "$U/film.mp4" | sha256sum     # compare with the same slice on disk
```

A `200` on the Range request means seeking is broken; a missing `ftyp` means you are serving an error page or a
partial file; a hash that differs means the tunnel is serving something other than the file you graded. Any of
the three, fix it before the link goes out.

## 4. Say how long the link lives

- A quick tunnel is **temporary** — it dies with the `cloudflared` process. State that when you hand it over.
- A permanent URL means copying the file to the host that will keep it (a VPS, a static bucket) and linking
  that instead; offer it rather than silently handing over a link that expires.
- Give the **sha256 of the delivery file** with the link. It is the only way the person can prove the copy they
  downloaded is the copy you graded, and it costs one line.
- **Compute that hash and the byte count in the same turn you write them into the page — never type them from
  memory, and never leave a placeholder.** A hand-over page shipped with `sha256 c1a3…` invented on the spot,
  next to a real 113.9 MB file whose hash began `c2f25f28`; the page was public for minutes before anyone
  measured it. `sha256sum <file>` and `stat -c %s <file>` first, paste the real prefix, and re-fetch the served
  page to confirm what the reader will see — the button label's size must match `stat`, not a rounded memory.
  Same rule as any figure in a deliverable: printed this turn, or not printed.
