# Findings from the actual encoded film

The 135.73-second master is technically decodable, but picture meaning does not
follow the narration. A contact sheet at 15-second intervals shows unexplained
mechanical work, an isolated elderly portrait, changing character appearances,
a river/boat during the road-crossing passage, and a different market woman near
the ending. Nine approved keyframes were copied into eighteen shot files; those
eighteen shots therefore do not establish eighteen distinct pictures.

At source time 35.522–49.652 the narration introduces Dimas returning after buying
breakfast and approaching the elderly woman. The serialized scene instead says:

- VISUAL: `Terima kasih banyak, Nak.`
- ARAHAN SUTRADARA: `blocking, kamera, depth, cahaya`
- PROPERTI ADEGAN: `tangan, posisi, kondisi`
- The global character field says no recurring character is defined.

Root cause: short AI narration was replaced by contiguous source paragraphs while
the old visual, dialogue, directing instructions, and prop list were retained.
The image compiler then trusted those fields as an approved scene. The example
JSON also encouraged the small model to copy placeholder instructions literally.
The character extractor did not recognize `nenek` and `pemuda` as identity cues.
Its one-person default could collapse a helping encounter into a portrait.

Implemented fixes couple source narration substitutions to visual/dialogue/prop
realignment; replace nonvisual dialogue and placeholder instructions; keep named
helper/elderly encounters as two people; recognize the source identities; require
breakfast packets and readable road geography; and start model-facing image copy
with the event rather than internal aspect/layout labels.

The new breakfast keyframe has been visually inspected: a young man with a food
packet faces the elderly woman with a cane and shopping bags, beside the curb in
the same morning market. A 14.13-second sample reuses original speech and phrase
captions. This is one repaired scene. The other eight scenes and the complete
master have not been rerendered or approved. Audio is present and the sample has
been decode-checked; a full listening review was not available in this session.
