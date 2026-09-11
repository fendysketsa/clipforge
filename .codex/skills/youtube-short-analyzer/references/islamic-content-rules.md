# Islamic Content Rules

Apply these rules to lectures, Qur'an or hadith discussion, fiqh, aqidah, history, reminders, and advice presented as Islamic teaching.

## Non-negotiable context rules

- Keep a negation, exception, condition, question, answer, and conclusion together when separating them would reverse or distort the meaning.
- Do not cut an ayah, hadith, prayer, Arabic quotation, translation, chain/source attribution, or scholar's qualification in the middle of its semantic unit.
- Do not convert a speaker's uncertainty, quotation, question, analogy, or personal opinion into a definitive religious ruling.
- Preserve who is being quoted. Never make the source speaker appear to claim another person's words.
- Reject excerpts that depend on an unseen earlier definition or a later correction.
- Reject mockery, takfir, sectarian provocation, demeaning labels, or accusations unless the complete excerpt clearly condemns the behavior and delivers a constructive lesson.
- Do not invent dalil, hadith grading, Arabic text, fatwa, scholar names, dates, or citations. Mark uncertain claims for human review.

Set `religious_context_safe=false` if any non-negotiable rule fails. A high engagement score can never override this gate.

## Ethical packaging

- Titles and hooks may create curiosity but must state only what the excerpt supports.
- Avoid absolute spiritual promises or threats such as guaranteed wealth, guaranteed paradise, certain punishment, or claims that a practice is haram/halal unless the excerpt establishes the context and attribution.
- Do not use tragedy, worship, death, or vulnerable people as joke bait.
- Keep subtitles respectful and readable. Avoid comic reaction stickers or sound effects during Qur'an recitation, prayer, grief, or solemn rulings.
- Music and visual treatment must follow the creator's stated policy; do not silently decide a disputed religious preference for them.
- CTA should invite reflection or constructive discussion, not outrage, harassment, or public judgment of an individual.

## Recommended human review flags

Add `REVIEW_REQUIRED` when the clip contains:

- a direct legal ruling or medical/financial advice framed as religion;
- disputed doctrine or criticism of a named person/group;
- an ayah or hadith whose exact wording/source is not visible in reliable metadata;
- claims about current events, statistics, or historical facts that need verification;
- ambiguous pronouns or a cut whose missing context could change the target or meaning.

Human review verifies meaning and attribution. It does not turn an unlicensed source into licensed media.

