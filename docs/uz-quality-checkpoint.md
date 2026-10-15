# Uzbek quality work: 0.7.26rc1, not a trained model release

Implemented:
- Shared structure parser for football, hockey and combat without required KIRISH/YAKUN labels.
- Preserve HOOK, accept contextual recap, ignore editorial links, distinguish betting statements from fixture headings.
- Support spoken ordinal introductions and single-fixture thematic scripts.
- Evaluate fallback phrase evidence locally; retain numeric-conflict review.
- Use sport-specific fallback classification.
- Optional local Russian translation of three separate review fields, original text retained. Translation does not alter montage data.
- Expanded football catalog to 264 club/national identities, each with Russian aliases; exact identity collision tests and longer-name protection (Inter Miami, reserve teams).
- Qualified Uzbek KHL club aliases; existing NHL/KHL catalog retained.
- Optional complete section anchors from distinctive spoken body phrases. Ambiguous/repeated or incomplete evidence falls back to existing checks; manual timings take priority.
- Automatic long-form Uzbek overlays no longer overlap. Lower-priority facts are shortened within their own spoken intervals; fully covered cards are omitted with a plan warning, never moved into unrelated speech.
- Missing forecast fallback limited to the final six seconds instead of the entire match block.
- PyAV pinned to 14.4.0 for faster-whisper 1.1.1's metadata_errors argument. Frozen application self-test decodes an actual WAV through faster-whisper.

Corpus inventory: 46 audio files with matching scenarios, 49 scenarios total.
All 46 paired scenarios pass structural parsing. This is not a claim that boundaries,
team identities, ASR, or final renders have passed manual validation.
The corpus is private and is not included in this repository.

Translation uses an opt-in ~3 GB download of MADLAD-400 CT2 int8, pinned revision
and SHA-256 checks. It uses CPU inference and an exact-source local cache.
References:
- https://huggingface.co/google/madlad400-3b-mt (Apache 2.0)
- https://huggingface.co/lifeai-dev/madlad400-3b-mt-ct2-int8
- https://opennmt.net/CTranslate2/guides/transformers.html#t5

Live local MADLAD tests exposed unsafe translations: “mag'lub bo'lmaydi” became
“не побеждает”, and a total-under clause lost its betting meaning. Whole-clause
rules now translate supported exact markets and non-loss statements before neural
translation. Unknown sensitive sports statements carry an explicit unverified
translation warning. Old translation caches are invalidated. This is experimental
review assistance, not a reliable language reviewer.

Pending validation: broader translation quality, low-memory Windows behaviour,
full-corpus speech transcription, verified training segments, held-out evaluation,
training/activation of new ASR weights, and real-user end-to-end montage assessment.
No newly trained weights exist. The four private audio archives were unavailable
after a workspace restart; the 46-script result above describes the earlier run,
not a fresh full-corpus validation of every subsequent change.

Do not train directly on complete scenarios as if they were verbatim speech:
the presenter can omit, reorder and paraphrase written content. Split train/validation/test
by episode/date before producing chunks. Keep test audio out of model fitting and
measure numbers, names and bet direction in addition to WER/CER.
