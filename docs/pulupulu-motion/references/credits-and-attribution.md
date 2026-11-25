# Credits, watermarks and a real person's portrait

Owner: credits, watermarks and portrait compositing

The last two minutes of a film are where a deliverable becomes publishable or not: the owner's mark, the
licence line for anything borrowed, and — when the film is about a person — a portrait that is lawful to
show. All three are added **after** the render, on the finished file, so a credit costs one encode instead
of a re-render.

Order: render → creator card → watermark → `deliver_check.py` → send. Chain the two overlays so the picture
is compressed twice at most, never three times.

---

## 1. The owner's watermark

```sh
python scripts/add_watermark.py out/film.mp4 deliver/film.mp4 --text "by <owner>" --crf 24
```

It draws with ffmpeg `drawtext` **inside the delivery encode**, so the film gets one generation of
compression rather than a picture pass plus a stamp pass. Being burned into the pixels, it also survives any
player and cannot be removed by editing the HTML.

| Decision | Value that works on a 1080-wide vertical film | Why |
|---|---|---|
| position | bottom-right, 26 px margin | the corner films leave empty; bottom-left collides with caption bands |
| size | 22 px | 30 px is a title, not a credit |
| colour | white at ~46 %, 1 px black shadow | reads on cream and on red without becoming furniture |
| while reviewing | crop the corner and look at it | a film with its own footer or progress bar will collide |

**Check the corner before shipping.** Crop `(520,1750)-(1080,1920)` from a mid-film frame at full size. The
first attempt at 30 px overlapped the film's own timecode — legible on its own, wrong in place.

### A mark in the middle of the film

A request for the watermark "in the middle of the video" is not the corner in a different place: it means the
mark sits **at the centre of the frame, around 45–55 % of the runtime**, for a readable few seconds, and then
leaves. Treat it as a design element the film hands to the viewer — a paper label taped over the evidence, an
archival `VERIFIED` stamp with the name on it, a pixel tape label — rather than a caption floating over the art.

- **Legible at phone size**, which at this position means far larger than the corner mark: it is read once, at
  speed, in the middle of a shot.
- **Design it with the beat it lands on.** A centred mark dropped over a busy scene covers the thing it was
  pointing at; place it on the interval between two beats, or on a deliberate full-frame quiet moment.
- **Verify on the frames around it, not by corner crop.** Sample ~45 %, 50 % and 55 % and look: a corner crop
  cannot show a centred mark, and a mark that animates in early or lingers is only visible in the samples.
- Keep the **end card credit as well** — a mid-film mark is a claim of authorship, not a substitute for the
  closing credit.

---

## 2. `drawtext` inside a filter graph will reject your text

The filter string is not free text: `:` separates options, so a credit containing a colon ends the option
list and the graph fails with `No option name near '…'` and `Error parsing a filter description`.

```sh
# breaks
-f "drawtext=text='Photo: Bill Condo - CC BY 2.0':fontsize=20"
# works
-f "drawtext=text='Photo\\: Bill Condo - CC BY 2.0':fontsize=20"
```

Rules that follow:

- **Escape `\`, `:` , `'` and `%`** in any text that reaches a filter. Build one helper and pass every name,
  role and credit through it rather than hand-escaping at each call site.
- **Keep credit text ASCII.** A middle dot, em dash or curly quote breaks parsing exactly like a colon does;
  write `Photo: Bill Condo - CC BY 2.0` instead of `·`.
- **A Windows font path needs its drive colon escaped**: `fontfile='C\:/Windows/Fonts/arialbd.ttf'`.
- **Isolate the failure on one still.** `-ss <t> -frames:v 1` with the same filter tells you in a second
  whether the graph is wrong; encoding two minutes to discover it costs minutes.
- `enable='gte(t,<start>)'` keeps a credit off the earlier part of the film, and the quoted comma survives
  the graph parser as long as the whole expression stays single-quoted.

---

## 3. Sourcing a portrait that is lawful to show

A real person's face is the one asset this renderer must never fake (see `SKILL.md` §1). Three lawful
outcomes, in order of preference:

1. **A licensed photograph**, credited in the film — §3 below.
2. **No face at all**: name the person in type and show an object, a screen, a place.
3. **A drawn portrait, labelled as a drawing.** When a subject has no photo you can licence — query Wikimedia
   Commons, the Wikipedia API and Openverse first, and record that you did — a stylised illustration is
   honest **only** if the frame says so. Print the label under the name in the film itself, e.g.
   `PIXEL ILLUSTRATION — NOT A PHOTO`, and repeat it in `ADMIT.md`. A drawing presented as a photograph is
   the same provenance failure as a stand-in for archival footage.

**Never put invented words in a real person's mouth.** A portrait may carry only a quote you can source and
attribute, and it must not be lip-synced to those words — no mouth animation on invented lines. A still
portrait with a breathing or tilt motion gives the presence the beat needs without faking a recording;
keep the narrator in the third person throughout.

**Find the licence metadata, not just the file.** Wikimedia Commons exposes it:

```sh
curl -s "https://commons.wikimedia.org/w/api.php?action=query&format=json\
&prop=imageinfo&iiprop=url|extmetadata|size&titles=File:<Name>.jpg"
# extmetadata: LicenseShortName, Artist, Credit, ImageDescription
```

Prefer Public Domain, CC0, CC BY or CC BY-SA. `CC BY-NC` is out of any monetised or client deliverable, same
rule as `asset-sourcing.md` §2.

**Download with a real user agent and a referer:**

```sh
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  -H "Referer: https://commons.wikimedia.org/" -o portrait.jpg "<upload.wikimedia.org URL>"
```

Without them the host answers with an HTML error page that saves with a `.jpg` name and fails later at
`PIL.Image.open` with `UnidentifiedImageError`. **Validate the bytes before doing anything else** — an image
should open and report a size; an HTML page will not.

Then crop head-and-shoulders to a **square, at least 300 px** for a 1080-wide frame. A face centred in a
tight square with the shoulders cut at the bottom is what reads at credit size.

**The attribution is part of the licence, not a nicety.** Render it in the film — `Photo: <author> - <licence>`
— next to the name. CC BY without visible credit is an unlicensed use, and recording it only in
`materials.md` does not discharge it.

---

## 4. The creator card on the end card

```sh
python scripts/add_creator_card.py out/film.mp4 deliver/film.mp4 portrait.jpg \
  --at 0.95 --x 810 --y 1400 --size 380 --tx 810 [--dark] \
  --name "<Name>" --role "<what they did>" --credit "Photo: <author> - <licence>"
```

The portrait is circle-masked with a ring in the film's paper colour so it reads as a designed card rather
than a pasted rectangle. It appears only for the tail of the film.

**Sample the true final frame to place it.** Take `-ss $(duration - 0.15)`; a frame grabbed a second and a
half early can show a layout that is still animating in, and the card lands on the wrong panel.

**Read the panel colour before choosing the text colour.** `--dark` renders ink for a paper panel; the
default cream is for a coloured one. Cream text on a cream end card is invisible, and it is invisible in the
filter log too — only the extracted frame shows it.

**Keep clear of the film's own headline.** Measure the empty region in the final frame (which half, above or
below the title), put the portrait there, and centre the name/role/credit under the portrait with `--tx`
when the portrait is not on the frame's centre line.

**Verify by looking.** Crop the end card out of the delivered file and inspect it: portrait legible, name and
role readable against the actual panel, licence line present, nothing over the headline.

---

## 5. Checklist

1. Watermark present in the delivered file, checked by cropping a corner at full size; a mid-film mark checked by
   sampling 45 %, 50 % and 55 % and looking at them.
2. Credit text ASCII, escaped, and rendered — not only recorded in the manifest.
3. Portrait licence read from source metadata; NC licences refused for anything monetised.
4. Portrait is a licensed photograph, never vector geometry drawn to look like someone.
5. Card placed against the **true** final frame, text colour matched to that panel.
6. Licence line visible in the film next to the name.
7. `python scripts/deliver_check.py deliver/film.mp4 --timeline timeline.json` still passes after the
   overlays, and the duration is unchanged.
