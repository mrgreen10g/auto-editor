# Uzbek quality work: checkpoint, not a trained model release

Implemented:
- Shared structure parser for football, hockey and combat without required KIRISH/YAKUN labels.
- Preserve HOOK, accept contextual recap, ignore editorial links, distinguish betting statements from fixture headings.
- Support spoken ordinal introductions and single-fixture thematic scripts.
- Evaluate fallback phrase evidence locally; retain numeric-conflict review.
- Use sport-specific fallback classification.
- Optional local Russian translation of three separate review fields, original text retained. Translation does not alter montage data.

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

Pending validation: live translation quality on Uzbek sports vocabulary, low-memory
Windows behaviour, full-corpus speech transcription, manually verified training
segments, held-out evaluation, training/activation of new ASR weights, catalog expansion,
and end-to-end overlay timing/collision validation. No newly trained weights exist.

Do not train directly on complete scenarios as if they were verbatim speech:
the presenter can omit, reorder and paraphrase written content. Split train/validation/test
by episode/date before producing chunks. Keep test audio out of model fitting and
measure numbers, names and bet direction in addition to WER/CER.
